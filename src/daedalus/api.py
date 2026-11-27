"""Minimal authenticated, read-only control API for desktop and remote clients.

No live account worker or game login is launched by this module. Warehouse
snapshots require an explicitly injected provider; until then the API honestly
returns 503 rather than fabricated values.
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, status

from daedalus import __version__
from daedalus.account_editor import (
    AccountEditConflict,
    AccountEditUnavailable,
    AccountMetadataStore,
)
from daedalus.account_sessions import (
    AccountSessionCoordinator,
    SessionBusyError,
    SessionPhase,
)
from daedalus.accounts import Account, AccountConfigError, load_accounts
from daedalus.auth_assistance import AssistanceBroker, AssistanceConflict
from daedalus.demo import demo_accounts, demo_cities, demo_warehouses
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient, FillPreviewUnavailable
from daedalus.engine_registry import inspect_engine
from daedalus.login_vault import (
    LoginVaultUnavailable,
    read_login_vault,
    validate_login_vault,
    write_login_vault,
)
from daedalus.native_browser_handoff import NativeBrowserHandoff, NativeHandoffUnavailable
from daedalus.operation_manifest import MANIFEST_VERSION, operation_workflow
from daedalus.operation_previews import OperationPreviews, PreviewUnavailable
from daedalus.recovery_credentials import RecoveryCredentials, RecoveryCredentialsUnavailable
from daedalus.recovery_runtime import RecoverySupervisor, RecoveryWorkerError
from daedalus.recovery_state import RecoveryConflict, RecoveryStore
from daedalus.reviewed_operations import (
    WORKER_TASKS,
    validated_attack_draft,
    validated_build_draft,
    validated_grind_draft,
    validated_layout_draft,
    validated_shipment_draft,
    validated_station_draft,
    validated_worker_draft,
)
from daedalus.saved_session_recovery import SavedSessionUnavailable, _email_binding
from daedalus.saved_worker import SavedCookieWorker
from daedalus.session_monitor import ExistingSessionRecoveryMonitor, MonitoringUnavailable
from daedalus.task_control import (
    TaskConflict,
    TaskController,
    TaskPrerequisiteMissing,
    TaskRejected,
    TaskUnavailable,
)
from daedalus.warehouse import CityWarehouseSnapshot

logger = logging.getLogger("daedalus.api")

SnapshotProvider = Callable[[str], list[CityWarehouseSnapshot]]


def create_app(
    *,
    accounts_path: str | Path | None = None,
    api_token: str | None = None,
    snapshot_provider: SnapshotProvider | None = None,
    session_coordinator: AccountSessionCoordinator | None = None,
    ipc_client: ExistingIPCClient | None = None,
    task_controller: TaskController | None = None,
    enable_account_editing: bool = False,
    assistance_broker: AssistanceBroker | None = None,
    recovery_monitor: ExistingSessionRecoveryMonitor | None = None,
    saved_worker: SavedCookieWorker | None = None,
    native_browser_handoff: NativeBrowserHandoff | None = None,
    browser_cookie_workers: object | None = None,
    recovery_store: RecoveryStore | None = None,
    recovery_credentials: RecoveryCredentials | None = None,
    recovery_supervisor: RecoverySupervisor | None = None,
    demo_mode: bool = False,
) -> FastAPI:
    """Create an API with mandatory bearer authentication and no game side effects."""
    token = api_token if api_token is not None else os.environ.get("DAEDALUS_API_TOKEN")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("DAEDALUS_API_TOKEN must be a secret of at least 32 characters")
    if demo_mode and (
        accounts_path is not None or snapshot_provider is not None
        or session_coordinator is not None or ipc_client is not None
        or task_controller is not None or enable_account_editing
        or assistance_broker is not None or recovery_monitor is not None
        or saved_worker is not None or native_browser_handoff is not None
        or browser_cookie_workers is not None
        or recovery_store is not None or recovery_credentials is not None
        or recovery_supervisor is not None
    ):
        raise ValueError("Synthetic demo cannot connect to real accounts, IPC or task controls")
    if demo_mode:
        configured_accounts: list[Account] = demo_accounts()
        snapshot_provider = demo_warehouses
    elif enable_account_editing and accounts_path is not None and not Path(accounts_path).expanduser().exists():
        configured_accounts: list[Account] = []
    else:
        configured_accounts = load_accounts(accounts_path)
    account_by_id = {account.id: account for account in configured_accounts}
    operation_previews = OperationPreviews()
    owner = session_coordinator or AccountSessionCoordinator(configured_accounts)
    if not owner.matches_accounts(configured_accounts):
        raise ValueError("Session coordinator and configuration must contain the same accounts")
    if enable_account_editing and task_controller is not None:
        raise ValueError("Account editing and task dispatch cannot run together")
    if assistance_broker is not None and (
        assistance_broker.coordinator is not owner or enable_account_editing
    ):
        raise ValueError("Assistance must use the authoritative fixed account owner")
    if recovery_monitor is not None and (
        recovery_monitor.controller is not task_controller
        or recovery_monitor.broker is not assistance_broker
        or recovery_monitor.broker.coordinator is not owner
        or enable_account_editing
    ):
        raise ValueError("Recovery monitor must share the opted-in task owner and broker")
    if saved_worker is not None:
        if (
            saved_worker.coordinator is not owner
            or saved_worker.account.id not in account_by_id
            or account_by_id[saved_worker.account.id] != saved_worker.account
        ):
            raise ValueError("Dedicated saved worker must be the configured authoritative owner")
        if recovery_monitor is not None:
            # CLI must pre-attach the worker before constructing encrypted
            # native handoff; direct API callers may still attach here.
            attached = recovery_monitor._dedicated_worker
            if attached is None:
                recovery_monitor.attach_dedicated_worker(saved_worker)
            elif attached is not saved_worker:
                raise ValueError("Dedicated recovery monitor is owned by a different worker")
    if native_browser_handoff is not None and (
        native_browser_handoff.owner is not owner
        or not native_browser_handoff.owner.matches_accounts(configured_accounts)
        or native_browser_handoff.worker is not saved_worker
        # A session monitor may exist with zero attached workers, such as
        # after a saved world cookie expires. A new account's encrypted Mac
        # handoff must still be available without claiming a monitor lease.
        or native_browser_handoff.monitor is not (
            recovery_monitor if saved_worker is not None else None
        )
        or enable_account_editing
    ):
        raise ValueError("Native browser handoff needs the exact fixed authoritative owner")
    if browser_cookie_workers is not None and (
        native_browser_handoff is None
        or native_browser_handoff.cookie_workers is not browser_cookie_workers
        or browser_cookie_workers.owner is not owner
        or browser_cookie_workers.router is not ipc_client
        or enable_account_editing
    ):
        raise ValueError("Cookie workers require the exact browser handoff and IPC owner")
    if recovery_supervisor is not None and (
        recovery_store is None or recovery_credentials is None
        or recovery_supervisor.store is not recovery_store
        or recovery_supervisor.controller is not task_controller
    ):
        raise ValueError("Auto recovery must use the same single authoritative task controller")
    if recovery_store is not None and (task_controller is None or enable_account_editing):
        raise ValueError("Recovery journal requires the fixed authoritative task controller")
    store = AccountMetadataStore(accounts_path) if enable_account_editing else None
    if store is not None:
        saved = store.snapshot()
        if [Account(**row) for row in saved["accounts"]] != configured_accounts:
            raise ValueError("Account metadata and controller configuration differ")
    @asynccontextmanager
    async def monitor_lifespan(_app: FastAPI):
        if recovery_monitor is not None:
            recovery_monitor.start()
        if recovery_supervisor is not None:
            recovery_supervisor.start()
        try:
            yield
        finally:
            if recovery_supervisor is not None:
                recovery_supervisor.stop()
            if browser_cookie_workers is not None:
                browser_cookie_workers.close()
            if recovery_monitor is not None:
                recovery_monitor.stop()
            if task_controller is not None:
                task_controller.close()

    # Default startup remains read-only; a monitor never restores a game login.
    app = FastAPI(
        title="Daedalus Read-only API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=monitor_lifespan if (
            recovery_monitor is not None or recovery_supervisor is not None
            or browser_cookie_workers is not None
        ) else None,
    )

    @app.middleware("http")
    async def private_api_no_cache(request: Request, call_next):
        """Keep game/account snapshots out of browser and intermediary caches.

        TLS terminates at a trusted HTTPS ingress for remote clients; this
        middleware does not alter the API's required Bearer authorization.
        """
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def authorized(authorization: str | None = Header(default=None)) -> None:
        if (
            not authorization
            or not authorization.startswith("Bearer ")
            or not secrets.compare_digest(authorization[7:], token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        if browser_cookie_workers is not None:
            browser_cookie_workers.reap()
        return {
            "service": "daedalus",
            "version": __version__,
            "mode": (
                "synthetic_demo" if demo_mode else
                "task_control_opt_in" if task_controller is not None else "read_only"
            ),
            "synthetic_demo": demo_mode,
            # Nonsecret visibility into read-only saved-cookie restoration.
            # No account identity, world hostname, token or cookie is exposed.
            "saved_worker_retry": (
                browser_cookie_workers.recovery_status()
                if browser_cookie_workers is not None
                and callable(getattr(browser_cookie_workers, "recovery_status", None))
                else {"enabled": False}
            ),
            "authenticated_workers": sum(
                owner.status(account.id) == SessionPhase.AUTHENTICATED.value
                for account in configured_accounts
            ),
        }

    @app.get("/api/v1/release-status", dependencies=[Depends(authorized)])
    def available_release() -> dict[str, object]:
        from daedalus.release_catalog import release_status

        return release_status(offline=demo_mode)

    @app.get("/api/v1/login-vaults", dependencies=[Depends(authorized)])
    def login_vaults() -> dict[str, object]:
        """Return opaque ciphertext only; the decryption key stays on the Mac."""
        if demo_mode or native_browser_handoff is None:
            return {"vaults": {}}
        result: dict[str, dict[str, object]] = {}
        try:
            for account in configured_accounts:
                sealed = read_login_vault(
                    account, credential_store=native_browser_handoff.credentials,
                )
                if sealed is not None:
                    result[account.id] = sealed
        except LoginVaultUnavailable as exc:
            raise HTTPException(status_code=503, detail="Protected login vault unavailable") from exc
        return {"vaults": result}

    @app.post("/api/v1/accounts/{account_id}/login-vault",
              dependencies=[Depends(authorized)])
    def save_login_vault(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, bool]:
        """Persist client-sealed credentials only after verified email binding."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if native_browser_handoff is None or demo_mode:
            raise HTTPException(status_code=503, detail="Protected login vault is disabled")
        try:
            validate_login_vault(payload, confirmed=True)
        except LoginVaultUnavailable as exc:
            raise HTTPException(status_code=422, detail="Invalid sealed login material") from exc
        try:
            write_login_vault(
                account, payload, credential_store=native_browser_handoff.credentials,
            )
        except LoginVaultUnavailable as exc:
            raise HTTPException(status_code=409, detail="Verified login binding unavailable") from exc
        return {"saved": True}

    @app.get("/api/v1/account-config", dependencies=[Depends(authorized)])
    def account_config() -> dict[str, object]:
        if store is None:
            return {"enabled": False, "revision": None, "accounts": []}
        try:
            return store.snapshot()
        except (AccountConfigError, AccountEditUnavailable) as exc:
            raise HTTPException(status_code=503, detail="Account metadata is unavailable") from exc

    @app.put("/api/v1/account-config", dependencies=[Depends(authorized)])
    def update_account_config(payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        nonlocal configured_accounts, account_by_id
        if store is None:
            raise HTTPException(status_code=503, detail="Account editing is disabled")
        if payload.keys() != {"revision", "accounts", "confirmed"} or payload["confirmed"] is not True:
            raise HTTPException(status_code=422, detail="Explicit confirmation and valid metadata are required")
        try:
            with owner._mutex:
                result = store.update(payload["revision"], payload["accounts"], owner)
                updated = [Account(**row) for row in result["accounts"]]
                configured_accounts = updated
                account_by_id = {account.id: account for account in updated}
            return result
        except (SessionBusyError, AccountEditConflict) as exc:
            raise HTTPException(status_code=409, detail="Account configuration is busy or changed") from exc
        except AccountConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AccountEditUnavailable as exc:
            raise HTTPException(status_code=503, detail="Account metadata cannot be edited safely") from exc

    @app.get(
        "/api/v1/accounts/{account_id}/auth-assistance",
        dependencies=[Depends(authorized)],
    )
    def auth_assistance_status(account_id: str) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if assistance_broker is None:
            return {"enabled": False, "account_id": account_id, "ticket": None}
        try:
            return assistance_broker.snapshot(account_id)
        except AssistanceConflict as exc:
            raise HTTPException(status_code=409, detail="Session ownership changed") from exc

    @app.post(
        "/api/v1/accounts/{account_id}/auth-assistance/{ticket_id}/approve",
        dependencies=[Depends(authorized)],
    )
    def approve_auth_assistance(
        account_id: str, ticket_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if assistance_broker is None:
            raise HTTPException(status_code=503, detail="Manual assistance is not available")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit human confirmation is required")
        try:
            return assistance_broker.approve(account_id, ticket_id, confirmed=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid assistance request") from exc
        except AssistanceConflict as exc:
            raise HTTPException(status_code=409, detail="Assistance request is stale or busy") from exc

    @app.get("/api/v1/native-browser-login", dependencies=[Depends(authorized)])
    def native_browser_login_capabilities() -> dict[str, object]:
        return {"enabled": native_browser_handoff is not None,
                "mode": "mac_ephemeral_encrypted", "client_side_browser": True,
                "ttl_seconds": 600}

    @app.post("/api/v1/accounts/{account_id}/browser-login/start",
              dependencies=[Depends(authorized)])
    def start_native_browser_login(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if native_browser_handoff is None:
            raise HTTPException(status_code=503, detail="Native browser recovery is not enabled")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit browser-login consent required")
        try:
            return native_browser_handoff.start(account_id, confirmed=True)
        except NativeHandoffUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/browser-login/{ticket_id}/cancel",
              dependencies=[Depends(authorized)])
    def cancel_native_browser_login(
        account_id: str, ticket_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, str]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if native_browser_handoff is None:
            raise HTTPException(status_code=503, detail="Native browser recovery is not enabled")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit cancellation required")
        try:
            return native_browser_handoff.cancel(account_id, ticket_id, confirmed=True)
        except NativeHandoffUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/browser-login/{ticket_id}/complete",
              dependencies=[Depends(authorized)])
    def complete_native_browser_login(
        account_id: str, ticket_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, str]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if native_browser_handoff is None:
            raise HTTPException(status_code=503, detail="Native browser recovery is not enabled")
        # This endpoint accepts *only* the encrypted envelope. Not a raw cookie,
        # Gameforge password, browser profile, token or URL.
        try:
            return native_browser_handoff.complete(account_id, ticket_id, payload)
        except NativeHandoffUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/v1/accounts/{account_id}/recovery-guide",
        dependencies=[Depends(authorized)],
    )
    def recovery_guide(account_id: str) -> dict[str, object]:
        """Only a fixed nonsecret host-local workflow, never browser control.

        Neither a URL of the authenticated browser nor any cookie, token,
        credential, profile or arbitrary command is sent over HTTP.
        """
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        ticket = None
        if assistance_broker is not None:
            try:
                ticket = assistance_broker.snapshot(account_id)["ticket"]
            except AssistanceConflict as exc:
                raise HTTPException(status_code=409, detail="Recovery session changed") from exc
        dedicated = bool(
            recovery_monitor is not None and saved_worker is not None
            and saved_worker.account.id == account_id
        )
        return {
            "enabled": recovery_monitor is not None,
            "account_id": account_id,
            "mode": "host_local_only",
            "requires_trusted_host_session": True,
            "allow_http_cookie_transfer": False,
            "dedicated_rebind_supported": dedicated,
            "session_status": owner.status(account_id),
            "ticket": ticket,
        }

    @app.post(
        "/api/v1/accounts/{account_id}/recovery/prepare",
        dependencies=[Depends(authorized)],
    )
    def prepare_dedicated_recovery(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit preparation consent required")
        if recovery_monitor is None or saved_worker is None:
            raise HTTPException(status_code=503, detail="Dedicated recovery is disabled")
        try:
            return recovery_monitor.prepare_dedicated_recovery(
                account_id, confirmed=True,
            )
        except (MonitoringUnavailable, AssistanceConflict, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail="Dedicated worker is not safely idle or owned",
            ) from exc

    @app.post(
        "/api/v1/accounts/{account_id}/recovery/{ticket_id}/rebind-worker",
        dependencies=[Depends(authorized)],
    )
    def rebind_dedicated_worker(
        account_id: str, ticket_id: str,
        payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, str]:
        """Approve only a SAME-HOST staged cookie under existing worker lease.

        The endpoint cannot upload credentials or browser cookies; a host-only
        interactive command must stage them before this request is accepted.
        """
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit recovery consent required")
        if recovery_monitor is None or saved_worker is None:
            raise HTTPException(status_code=503, detail="Dedicated recovery is disabled")
        try:
            return recovery_monitor.rebind_dedicated_worker(
                account_id, ticket_id, confirmed=True,
            )
        except (MonitoringUnavailable, AssistanceConflict, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail="Host-local staged recovery is unavailable or unverified",
            ) from exc

    @app.get("/api/v1/auth-assistance/pending", dependencies=[Depends(authorized)])
    def pending_assistance() -> dict[str, object]:
        if recovery_monitor is None:
            return {"enabled": False, "tickets": []}
        return recovery_monitor.pending()

    @app.post(
        "/api/v1/accounts/{account_id}/monitor",
        dependencies=[Depends(authorized)],
    )
    def observe_account(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, str]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if recovery_monitor is None:
            raise HTTPException(status_code=503, detail="Session monitoring is disabled")
        if payload != {"confirmed": True}:
            raise HTTPException(status_code=422, detail="Explicit monitoring confirmation required")
        try:
            return recovery_monitor.observe(account_id, confirmed=True)
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail="Another account session owner is active") from exc
        except (MonitoringUnavailable, TaskUnavailable) as exc:
            raise HTTPException(status_code=503, detail="No verified existing IkaBot session") from exc

    @app.post(
        "/api/v1/accounts/{account_id}/recovery/{ticket_id}/resume-task",
        dependencies=[Depends(authorized)],
    )
    def resume_task_after_recovery(
        account_id: str, ticket_id: str,
        payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if recovery_monitor is None:
            raise HTTPException(status_code=503, detail="Verified recovery is disabled")
        if payload.keys() != {"confirmed", "task", "config", "request_id"} or payload["confirmed"] is not True:
            raise HTTPException(status_code=422, detail="Explicit approval and a new task request are required")
        try:
            return recovery_monitor.resume_verified_task(
                account_id, ticket_id, payload["task"], payload["config"],
                payload["request_id"], confirmed=True,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Invalid new task request") from exc
        except (MonitoringUnavailable, TaskUnavailable, TaskConflict,
                EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=409, detail="Verified recovery or safe task dispatch unavailable") from exc

    @app.get("/api/v1/accounts", dependencies=[Depends(authorized)])
    def accounts() -> dict[str, object]:
        if browser_cookie_workers is not None:
            browser_cookie_workers.reap()
        entries = []
        for account in configured_accounts:
            entry = account.to_dict()
            entry["session_status"] = owner.status(account.id)
            if not demo_mode:
                # Only the already-bound email is exposed to authenticated
                # clients for identity display and login prefill; no password.
                credentials = (
                    native_browser_handoff.credentials if native_browser_handoff is not None
                    else saved_worker._credentials if saved_worker is not None
                    else None
                )
                try:
                    entry["email"] = _email_binding(account, credentials)
                except SavedSessionUnavailable:
                    pass
            if demo_mode:
                entry["synthetic"] = True
            entries.append(entry)
        return {"accounts": entries}

    @app.get("/api/v1/accounts/{account_id}/session", dependencies=[Depends(authorized)])
    def account_session(account_id: str) -> dict[str, str]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"account_id": account_id, "session_status": owner.status(account_id)}

    @app.get("/api/v1/capabilities", dependencies=[Depends(authorized)])
    def capabilities() -> dict[str, object]:
        operations = inspect_engine()
        return {
            "operations": [{**item.to_dict(), "workflow": operation_workflow(item.name)}
                           for item in operations],
            "operation_manifest_version": MANIFEST_VERSION,
            "structured_engine_dispatch": task_controller is not None,
            "session_monitoring": recovery_monitor is not None,
            "synthetic_demo": demo_mode,
        }

    @app.get("/api/v1/engine/connected-accounts", dependencies=[Depends(authorized)])
    def connected_accounts() -> dict[str, object]:
        if browser_cookie_workers is not None:
            browser_cookie_workers.reap()
        if ipc_client is None:
            raise HTTPException(status_code=503, detail="Existing IPC attachment is disabled")
        try:
            live = ipc_client.list_sessions()
        except (EngineIPCUnavailable, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Existing IkaBot IPC is unavailable") from exc
        # Only configured identities; never enumerate unrelated engine accounts.
        attached = [
            account.id for account in configured_accounts
            if account.enabled and sum(
                item["world"].casefold() == account.world.casefold()
                and item["player"].casefold() == account.player.casefold()
                for item in live
            ) == 1
        ]
        return {"connected_account_ids": attached, "engine_mode": "existing_session_only"}

    @app.get("/api/v1/accounts/{account_id}/cities", dependencies=[Depends(authorized)])
    def account_cities(account_id: str) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode:
            return {"account_id": account_id, "cities": demo_cities(account_id),
                    "synthetic_demo": True}
        if ipc_client is None:
            raise HTTPException(status_code=503, detail="Existing IPC attachment is disabled")
        try:
            cities = ipc_client.cities(account)
        except (EngineIPCUnavailable, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Authenticated IkaBot session unavailable") from exc
        return {"account_id": account_id, "cities": cities}

    @app.post("/api/v1/accounts/{account_id}/reward-distribution-plan", dependencies=[Depends(authorized)])
    def reward_distribution_plan(account_id: str, payload: Annotated[dict[str, object], Body()]):
        from daedalus.daily_distribution_review import (
            daily_draft,
            distribution_draft,
            validate_daily,
            validate_distribution,
        )
        from daedalus.market_review import market_draft, validate_market_observation
        from daedalus.native_policy_review import POLICY_TASKS, observe_policy, policy_draft

        controller = require_task_controller(account_id)
        task = payload.get("task")
        if set(payload) != {"task", "draft"} or not isinstance(task, str) or task not in POLICY_TASKS | {"loginDaily", "distributeResources", "buyResources", "sellResources"}:
            raise HTTPException(status_code=422, detail="Invalid operation preview")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Operation preview unavailable")
        try:
            draft = (daily_draft(payload["draft"]) if task == "loginDaily" else distribution_draft(payload["draft"])
                     if task == "distributeResources" else policy_draft(task, payload["draft"]) if task in POLICY_TASKS
                     else market_draft(task, payload["draft"]))
            try:
                preflight = controller.preflight(account_id, task)
            except (EngineIPCUnavailable, TaskUnavailable, SessionBusyError):
                if task == "fillCityWarehouse":
                    raise FillPreviewUnavailable("fill_session_unavailable") from None
                raise
            if preflight.get("ready") is not True or preflight.get("unresolved_request") is not False:
                if task == "fillCityWarehouse":
                    raise FillPreviewUnavailable("fill_preflight_unavailable")
                raise ValueError("Prerequisites unavailable")
            account = account_by_id[account_id]
            observed = (observe_policy(ipc_client, account, task, draft) if task in POLICY_TASKS
                        else ipc_client.native_reward_distribution_preview(account, task, draft))
            config = dict(draft)
            if task == "fillCityWarehouse":
                config["reviewed_sources"] = [{"city_id": r["city_id"], "amount": r["amount"]}
                                              for r in observed["sources"] if r["amount"]]
            elif task == "loginDaily":
                validate_daily(draft, observed)
            elif task == "distributeResources":
                config["reviewed_routes"] = validate_distribution(draft, observed)
                if observed["ready"] is not True:
                    raise ValueError("No usable fleet")
            elif task in {"buyResources", "sellResources"}:
                validate_market_observation(task, draft, observed)
                config["reviewed_market"] = True
            ticket = operation_previews.issue(account_id, task, config)
            return {"account_id": account_id, "task": task, "draft": draft, "observation": observed,
                    "preview_id": ticket, "expires_in": operation_previews.ttl}
        except FillPreviewUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Operation preview rejected") from exc
        except (EngineIPCUnavailable, TaskUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Operation preview unavailable") from exc

    @app.post("/api/v1/accounts/{account_id}/shipment-plan", dependencies=[Depends(authorized)])
    def shipment_plan(account_id: str, payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        require_task_controller(account_id)
        account = account_by_id[account_id]
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Shipment planner unavailable")
        try:
            draft = validated_shipment_draft(payload)
            plan = ipc_client.shipment_preview(account, draft)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Shipment draft or stock rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Shipment preview unavailable") from exc
        ticket = operation_previews.issue(account_id, "sendResources", draft) if plan["ready"] else None
        return {**plan, "preview_id": ticket, "expires_in": operation_previews.ttl if ticket else None}

    @app.get("/api/v1/accounts/{account_id}/island-destinations", dependencies=[Depends(authorized)])
    def island_destinations(account_id: str, x: int, y: int) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 1 <= x <= 100 or not 1 <= y <= 100:
            raise HTTPException(status_code=422, detail="Invalid coordinates")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Island lookup unavailable")
        try:
            return ipc_client.island_destinations(account, x, y)
        except (ValueError, EngineIPCUnavailable) as exc:
            raise HTTPException(status_code=503, detail="Island lookup unavailable") from exc

    @app.get("/api/v1/accounts/{account_id}/cities/{city_id}/production", dependencies=[Depends(authorized)])
    def account_production(account_id: str, city_id: int) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid city")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Production inventory unavailable")
        try:
            inventory = ipc_client.production_inventory(account, city_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Owned city not found") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Authenticated production data unavailable") from exc
        return {"account_id": account_id, **inventory}

    @app.get("/api/v1/accounts/{account_id}/cities/{city_id}/buildings", dependencies=[Depends(authorized)])
    def account_buildings(account_id: str, city_id: int) -> dict[str, object]:
        """Safe, read-only actual building rows; not an executable construction plan."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid city")
        if demo_mode:
            # Never invent game building levels, even in demo. Present empty as no data.
            return {"account_id": account_id, "city_id": city_id,
                    "buildings": [], "synthetic_demo": True, "available": False}
        if ipc_client is None:
            raise HTTPException(status_code=503, detail="Existing IPC attachment is disabled")
        try:
            buildings = ipc_client.buildings(account, city_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Owned city not found") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Authenticated building data unavailable") from exc
        return {"account_id": account_id, "city_id": city_id,
                "buildings": buildings, "available": True}

    @app.post(
        "/api/v1/accounts/{account_id}/cities/{city_id}/construction-preview",
        dependencies=[Depends(authorized)],
    )
    def preview_construction(
        account_id: str, city_id: int,
        payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        """Prepare a read-only IkaBot construction queue, never perform upgrades."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if type(city_id) is not int or not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid city")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real construction planner unavailable")
        upgrades = payload.get("upgrades")
        if (set(payload) not in ({"upgrades"}, {"upgrades", "supply"})
                or not isinstance(upgrades, list) or not 0 < len(upgrades) <= 12):
            raise HTTPException(status_code=422, detail="Choose valid building targets")
        for upgrade in upgrades:
            if (not isinstance(upgrade, dict)
                    or set(upgrade) != {"position", "target_level"}
                    or type(upgrade["position"]) is not int
                    or type(upgrade["target_level"]) is not int
                    or not 0 <= upgrade["position"] <= 80
                    or not 1 <= upgrade["target_level"] <= 150):
                raise HTTPException(status_code=422, detail="Invalid building target")
        try:
            if "supply" in payload:
                from daedalus.reviewed_operations import validated_construction_supply

                supply = validated_construction_supply(city_id, payload["supply"])
                plan = ipc_client.construction_preview(account, city_id, upgrades, supply=supply)
            else:
                plan = ipc_client.construction_preview(account, city_id, upgrades)
            ticket = (operation_previews.issue(account_id, "constructionList", plan["config"])
                      if plan.get("ready") is True and task_controller is not None else None)
            return {**plan, "preview_id": ticket,
                    "expires_in": operation_previews.ttl if ticket else None}
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Construction preview rejected invalid city or targets"
            ) from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated construction preview unavailable"
            ) from exc

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/vacation-plan",
              dependencies=[Depends(authorized)])
    def vacation_plan(account_id: str, city_id: int,
                      payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if payload:
            raise HTTPException(status_code=422, detail="Unexpected vacation parameters")
        if demo_mode or ipc_client is None or task_controller is None:
            raise HTTPException(status_code=503, detail="Vacation planner unavailable")
        try:
            plan = ipc_client.vacation_preview(account, city_id)
            managed_active = any(row.get("status") in {"running", "stopping"}
                                 for row in task_controller.list_tasks(account_id)["engine_tasks"])
            recovery_disabled = recovery_store is None or not recovery_store.policy(account)["enabled"]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Vacation preview rejected") from exc
        except (EngineIPCUnavailable, TaskUnavailable) as exc:
            raise HTTPException(status_code=503, detail="Vacation preview unavailable") from exc
        config = plan.pop("config")
        plan["managed_active"] = managed_active
        plan["recovery_disabled"] = recovery_disabled
        plan["ready"] = plan["ready"] and not managed_active and recovery_disabled
        ticket = operation_previews.issue(account_id, "vacationMode", config) if plan["ready"] else None
        return {**plan, "preview_id": ticket, "expires_in": operation_previews.ttl if ticket else None}

    @app.get("/api/v1/accounts/{account_id}/cities/{city_id}/attack-options",
             dependencies=[Depends(authorized)])
    def attack_options(account_id: str, city_id: int) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real troop inventory unavailable")
        try:
            return ipc_client.attack_inventory(account, city_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Troop inventory rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Troop inventory unavailable") from exc

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/attack-plan",
              dependencies=[Depends(authorized)])
    def attack_plan(account_id: str, city_id: int,
                     payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real manual attack planner unavailable")
        try:
            plan = ipc_client.attack_preview(account, city_id, validated_attack_draft(city_id, payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Manual attack preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Manual attack preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "attackBarbarians", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/grind-plan",
              dependencies=[Depends(authorized)])
    def grind_plan(account_id: str, city_id: int,
                     payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real automatic attack planner unavailable")
        try:
            plan = ipc_client.grind_preview(account, city_id, validated_grind_draft(city_id, payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Automatic attack preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Automatic attack preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "autoBarbarians", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/station-plan",
              dependencies=[Depends(authorized)])
    def station_plan(account_id: str, city_id: int,
                     payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real deployment planner unavailable")
        try:
            plan = ipc_client.station_preview(account, city_id, validated_station_draft(city_id, payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Deployment preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Deployment preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "stationArmy", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.get("/api/v1/accounts/{account_id}/cities/{city_id}/build-options",
             dependencies=[Depends(authorized)])
    def build_options(account_id: str, city_id: int) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real building options unavailable")
        try:
            return ipc_client.build_options(account, city_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Building inventory rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Building inventory unavailable") from exc

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/build-plan",
              dependencies=[Depends(authorized)])
    def build_plan(account_id: str, city_id: int,
                   payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real building planner unavailable")
        try:
            plan = ipc_client.build_preview(account, city_id, validated_build_draft(payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Building preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Building preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "constructBuilding", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post(
        "/api/v1/accounts/{account_id}/cities/{city_id}/layout-plan",
        dependencies=[Depends(authorized)],
    )
    def layout_plan(account_id: str, city_id: int,
                    payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real layout planner unavailable")
        try:
            template = validated_layout_draft(city_id, payload)
            plan = ipc_client.layout_preview(account, city_id, template)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Layout preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Layout preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "reorganizeCityBuildings", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post(
        "/api/v1/accounts/{account_id}/cities/{city_id}/worker-plan",
        dependencies=[Depends(authorized)],
    )
    def worker_plan(account_id: str, city_id: int,
                    payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real worker planner unavailable")
        if set(payload) != {"task", "draft"} or not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid worker draft")
        task = payload["task"]
        try:
            clean = validated_worker_draft(task, payload["draft"])
            plan = ipc_client.worker_preview(account, city_id, task, clean)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Worker preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Worker preview unavailable") from exc
        config = plan.pop("config")
        ticket = None
        if plan["ready"] and task_controller is not None:
            if "production_plans" in config and task_controller._recovery_store is None:
                raise HTTPException(status_code=503, detail="Protected production journal unavailable")
            ticket = operation_previews.issue(account_id, task, config)
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post(
        "/api/v1/accounts/{account_id}/cities/{city_id}/donation-plan",
        dependencies=[Depends(authorized)],
    )
    def donation_plan(account_id: str, city_id: int,
                      payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Real donation planner unavailable")
        project, amount = payload.get("project"), payload.get("amount")
        if (set(payload) != {"project", "amount"} or project not in ("resource", "tradegood")
                or type(amount) is not int or not 1 <= amount <= 10**9
                or not 0 < city_id < 10**12):
            raise HTTPException(status_code=422, detail="Invalid donation draft")
        try:
            plan = ipc_client.donation_preview(account, city_id, project, amount)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Donation preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Donation preview unavailable") from exc
        config = plan.pop("config")
        ticket = None
        if plan["ready"] and task_controller is not None:
            ticket = operation_previews.issue(account_id, "donate", config)
        return {**plan, "preview_id": ticket,
                "expires_in": operation_previews.ttl if ticket else None}

    @app.post(
        "/api/v1/accounts/{account_id}/cities/{city_id}/construction-plan",
        dependencies=[Depends(authorized)],
    )
    def construction_plan(
        account_id: str, city_id: int,
        payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        """Return display data and a short-lived opaque review ticket, not a task payload."""
        plan = preview_construction(account_id, city_id, payload)
        config = plan.get("config")
        if not isinstance(config, dict):
            raise HTTPException(status_code=503, detail="Construction plan unavailable")
        buildings = config.get("buildings")
        if not isinstance(buildings, list) or not buildings:
            raise HTTPException(status_code=503, detail="Construction targets unavailable")
        ticket = plan.get("preview_id")
        return {
            "account_id": account_id, "city_id": city_id,
            "city_name": config.get("city_name"),
            "ready": plan.get("ready") is True,
            "costs": plan.get("costs"), "available": plan.get("available"),
            "missing": plan.get("missing"), "estimated_seconds": plan.get("estimated_seconds"),
            "buildings": [
                {"name": row["name"], "current_level": row["level"],
                 "target_level": row["upgradeTo"], "position": row["position"]}
                for row in buildings
            ],
            **({"supply": plan["supply"]} if "supply" in plan else {}),
            "preview_id": ticket, "expires_in": operation_previews.ttl if ticket else None,
        }

    @app.get(
        "/api/v1/accounts/{account_id}/cities/{city_id}/workshop-upgrades",
        dependencies=[Depends(authorized)],
    )
    def workshop_upgrades(account_id: str, city_id: int) -> dict[str, object]:
        """Discover verified unit/ship workshop upgrades without game mutations."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid city")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated workshop inventory unavailable")
        try:
            return ipc_client.workshop_upgrades(account, city_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Owned workshop city unavailable") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated workshop inventory unavailable"
            ) from exc

    @app.post("/api/v1/accounts/{account_id}/cities/{city_id}/training-plan",
              dependencies=[Depends(authorized)])
    def training_plan(account_id: str, city_id: int,
                      payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        from daedalus.training_contract import build_training_review, training_draft

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Recruitment inventory unavailable")
        try:
            draft = training_draft(payload)
            if draft["city_ids"][0] != city_id:
                raise ValueError("Recruitment origin mismatch")
            owned = {r["id"] for r in ipc_client.cities(account)}
            if not set(draft["city_ids"]) <= owned:
                raise ValueError("Recruitment city not owned")
            catalogs = [ipc_client.trainable_units(account, cid, train_troops=draft["train_troops"])
                        for cid in draft["city_ids"]]
            plan = build_training_review(account_id, draft, catalogs)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Recruitment preview rejected") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Recruitment preview unavailable") from exc
        config = plan.pop("config")
        ticket = operation_previews.issue(account_id, "trainArmy", config) if plan["ready"] and task_controller is not None else None
        return {**plan, "preview_id": ticket, "expires_in": operation_previews.ttl if ticket else None}

    @app.get(
        "/api/v1/accounts/{account_id}/cities/{city_id}/trainable-units",
        dependencies=[Depends(authorized)],
    )
    def trainable_units(
        account_id: str, city_id: int, train_troops: bool = True,
    ) -> dict[str, object]:
        """Read-only, source-validated barracks/shipyard training choices."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 0 < city_id < 10**12:
            raise HTTPException(status_code=422, detail="Invalid city")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated unit catalog unavailable")
        try:
            return ipc_client.trainable_units(account, city_id, train_troops=train_troops)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Owned barracks or shipyard unavailable") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Authenticated unit catalog unavailable") from exc

    @app.get(
        "/api/v1/accounts/{account_id}/cities/{city_id}/market-quotes",
        dependencies=[Depends(authorized)],
    )
    def market_quotes(
        account_id: str, city_id: int, resource_type: int, side: str,
    ) -> dict[str, object]:
        """Read source-verified offers/price bounds, not a game transaction."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if not 0 < city_id < 10**12 or not 0 <= resource_type <= 4:
            raise HTTPException(status_code=422, detail="Invalid market city or resource")
        if side not in {"buy", "sell_to_offers", "create_offer"}:
            raise HTTPException(status_code=422, detail="Invalid market action")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated market unavailable")
        try:
            return ipc_client.market_quotes(account, city_id, resource_type, side)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Owned market unavailable") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Authenticated market unavailable") from exc

    @app.get(
        "/api/v1/accounts/{account_id}/academies",
        dependencies=[Depends(authorized)],
    )
    def academy_research_inventory(account_id: str) -> dict[str, object]:
        """Read current academy stock and cooldowns, without spending crystal."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated academy inventory unavailable")
        try:
            return ipc_client.academies(account)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Academy read rejected invalid account") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated academy inventory unavailable"
            ) from exc

    @app.get(
        "/api/v1/accounts/{account_id}/taverns",
        dependencies=[Depends(authorized)],
    )
    def tavern_inventory(account_id: str) -> dict[str, object]:
        """Current city wine, tavern servings and population for safe review."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated tavern inventory unavailable")
        try:
            return ipc_client.taverns(account)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid tavern account context") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated tavern inventory unavailable"
            ) from exc

    @app.get(
        "/api/v1/accounts/{account_id}/miracles",
        dependencies=[Depends(authorized)],
    )
    def miracle_inventory(account_id: str) -> dict[str, object]:
        """Read only real activated temples and available wonder cooldowns."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated wonder inventory unavailable")
        try:
            return ipc_client.miracles(account)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid wonder account context") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated wonder inventory unavailable"
            ) from exc

    @app.get("/api/v1/accounts/{account_id}/administrative-status",
             dependencies=[Depends(authorized)])
    def administrative_status(account_id: str) -> dict[str, object]:
        """No provider keys, endpoints, cookie data or custom module paths."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Administrative status unavailable")
        try:
            from daedalus.admin_status import validate_admin_status

            response = ipc_client.administrative_status(account)
            if response.get("account_id") != account_id:
                raise ValueError("Account changed")
            return {"account_id": account_id,
                    "settings": validate_admin_status(response.get("settings"))}
        except (ValueError, EngineIPCUnavailable):
            raise HTTPException(status_code=503, detail="Administrative status unavailable") from None

    def scoped_world_reports(account_id, report_id=None, offset=0):
        from daedalus.world_reports import validate_world_page, validate_world_reports

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Aggregate map report unavailable")
        try:
            value = ipc_client.world_reports(account, report_id, offset)
            return (validate_world_reports(value, account_id) if report_id is None else
                    validate_world_page(value, account_id, report_id, offset))
        except (EngineIPCUnavailable, ValueError):
            raise HTTPException(status_code=503, detail="Aggregate map report unavailable") from None

    @app.get("/api/v1/accounts/{account_id}/world-reports", dependencies=[Depends(authorized)])
    def list_world_reports(account_id: str):
        return scoped_world_reports(account_id)

    @app.get("/api/v1/accounts/{account_id}/world-reports/{report_id}", dependencies=[Depends(authorized)])
    def read_world_report(account_id: str, report_id: str, offset: int = 0):
        from daedalus.world_reports import REPORT_ID

        if not REPORT_ID.fullmatch(report_id) or not 0 <= offset <= 10201:
            raise HTTPException(status_code=422, detail="Invalid map report request")
        return scoped_world_reports(account_id, report_id, offset)

    def reviewed_proxy_profiles(account_id, draft=None):
        from daedalus.proxy_profiles import validate_proxy_result

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account disabled")
        if demo_mode or ipc_client is None or (draft is not None and task_controller is None):
            raise HTTPException(status_code=503, detail="Approved network profiles unavailable")
        try:
            return validate_proxy_result(ipc_client.proxy_profiles(account, draft), account_id, draft)
        except (EngineIPCUnavailable, ValueError):
            raise HTTPException(status_code=503, detail="Network profile unavailable or outcome uncertain") from None

    @app.get("/api/v1/accounts/{account_id}/proxy-settings", dependencies=[Depends(authorized)])
    def get_proxy_profiles(account_id: str):
        return reviewed_proxy_profiles(account_id)

    @app.post("/api/v1/accounts/{account_id}/proxy-settings", dependencies=[Depends(authorized)])
    def set_proxy_profile(account_id: str, payload: Annotated[dict[str, object], Body()]):
        from daedalus.proxy_profiles import validate_proxy_draft

        try:
            draft = validate_proxy_draft(payload)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid network profile review") from None
        return reviewed_proxy_profiles(account_id, draft)

    def human_challenge_policy(account_id, draft=None):
        from daedalus.challenge_policy import validate_challenge_policy

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account disabled")
        if demo_mode or ipc_client is None or (draft is not None and task_controller is None):
            raise HTTPException(status_code=503, detail="Human challenge policy unavailable")
        try:
            return validate_challenge_policy(ipc_client.challenge_policy(account, draft), account_id)
        except (EngineIPCUnavailable, ValueError):
            raise HTTPException(status_code=503, detail="Human challenge policy unavailable or changed") from None

    @app.get("/api/v1/accounts/{account_id}/challenge-policy", dependencies=[Depends(authorized)])
    def get_human_challenge_policy(account_id: str):
        return human_challenge_policy(account_id)

    @app.post("/api/v1/accounts/{account_id}/challenge-policy", dependencies=[Depends(authorized)])
    def set_human_challenge_policy(account_id: str, payload: Annotated[dict[str, object], Body()]):
        from daedalus.challenge_policy import validate_challenge_policy_draft

        try:
            draft = validate_challenge_policy_draft(payload)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid human challenge policy") from None
        return human_challenge_policy(account_id, draft)

    def reviewed_extensions(account_id, draft=None):
        from daedalus.extension_settings import validate_extension_status

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account disabled")
        if demo_mode or ipc_client is None or (draft is not None and task_controller is None):
            raise HTTPException(status_code=503, detail="Protected extension settings unavailable")
        try:
            return validate_extension_status(ipc_client.extension_settings(account, draft), account_id)
        except (EngineIPCUnavailable, ValueError):
            raise HTTPException(status_code=503, detail="Extension settings unavailable or changed") from None

    @app.get("/api/v1/accounts/{account_id}/extensions", dependencies=[Depends(authorized)])
    def extension_status(account_id: str):
        return reviewed_extensions(account_id)

    @app.post("/api/v1/accounts/{account_id}/extensions", dependencies=[Depends(authorized)])
    def extension_registration(account_id: str, payload: Annotated[dict[str, object], Body()]):
        from daedalus.extension_settings import validate_extension_draft

        try:
            draft = validate_extension_draft(payload)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid extension registration") from None
        return reviewed_extensions(account_id, draft)

    def notification_account(account_id, provider):
        from daedalus.notification_settings import PROVIDERS

        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if provider not in PROVIDERS:
            raise HTTPException(status_code=404, detail="Unsupported notification provider")
        if demo_mode or ipc_client is None or task_controller is None:
            raise HTTPException(status_code=503, detail="Protected provider configuration unavailable")
        return account

    @app.post("/api/v1/accounts/{account_id}/notifications/{provider}/begin",
              dependencies=[Depends(authorized)])
    def notification_settings_begin(account_id: str, provider: str,
                                    payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        from daedalus.notification_settings import validate_challenge

        account = notification_account(account_id, provider)
        if set(payload) != {"confirmed_global"} or payload["confirmed_global"] is not True:
            raise HTTPException(status_code=422, detail="Explicit worker-global consent required")
        try:
            return validate_challenge(ipc_client.notification_settings_begin(account, provider), account_id, provider)
        except Exception:  # noqa: BLE001 - redact all provider/IPC failures
            raise HTTPException(status_code=503, detail="Protected provider configuration unavailable") from None

    @app.post("/api/v1/accounts/{account_id}/notifications/{provider}/complete",
              dependencies=[Depends(authorized)])
    def notification_settings_complete(account_id: str, provider: str,
                                       payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        from daedalus.notification_settings import validate_envelope, validate_receipt

        account = notification_account(account_id, provider)
        try:
            envelope = validate_envelope(payload)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid encrypted provider configuration") from None
        try:
            return validate_receipt(ipc_client.notification_settings_complete(account, provider, envelope),
                                    account_id, provider)
        except Exception:  # noqa: BLE001 - redact all provider/IPC failures
            raise HTTPException(status_code=503, detail="Provider configuration unavailable or outcome uncertain") from None

    @app.get(
        "/api/v1/accounts/{account_id}/shrine-status",
        dependencies=[Depends(authorized)],
    )
    def olympus_shrine_status(account_id: str) -> dict[str, object]:
        """Read the selected account's Shrine of Olympus and current favour."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated shrine status unavailable")
        try:
            return ipc_client.shrine_status(account)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid shrine account context") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated shrine status unavailable"
            ) from exc

    @app.get(
        "/api/v1/accounts/{account_id}/pirate-fortresses",
        dependencies=[Depends(authorized)],
    )
    def pirate_fortresses(account_id: str) -> dict[str, object]:
        """Real fortress levels and capture mission timing, no piracy action."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated piracy inventory unavailable")
        try:
            return ipc_client.pirate_fortresses(account)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Piracy account data invalid") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated piracy inventory unavailable"
            ) from exc

    @app.get(
        "/api/v1/accounts/{account_id}/military",
        dependencies=[Depends(authorized)],
    )
    def account_military(account_id: str) -> dict[str, object]:
        """Current owned-city troops and fleets; never issue a military order."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated military data unavailable")
        try:
            data = ipc_client.military_overview(account)
        except (EngineIPCUnavailable, ValueError) as exc:
            logger.warning("Authenticated military read failed for account %s (%s)",
                           account_id, type(exc).__name__)
            raise HTTPException(
                status_code=503, detail="Authenticated military data unavailable"
            ) from exc
        return {"account_id": account_id, **data}

    @app.get(
        "/api/v1/accounts/{account_id}/ship-movements",
        dependencies=[Depends(authorized)],
    )
    def account_ship_movements(account_id: str) -> dict[str, object]:
        """Read-only current ship/military movements, never dispatch a ship."""
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if demo_mode or ipc_client is None:
            raise HTTPException(status_code=503, detail="Authenticated movement data unavailable")
        try:
            data = ipc_client.ship_movements(account)
        except (EngineIPCUnavailable, ValueError) as exc:
            logger.warning("Authenticated ship movements read failed for account %s (%s)",
                           account_id, type(exc).__name__)
            raise HTTPException(
                status_code=503, detail="Authenticated movement data unavailable"
            ) from exc
        return {"account_id": account_id, **data}

    @app.get("/api/v1/task-control", dependencies=[Depends(authorized)])
    def task_control_status() -> dict[str, bool]:
        """Read-only opt-in status for clients; never exposes task management itself."""
        return {"enabled": task_controller is not None, "requires_existing_session": True,
                "session_monitoring": recovery_monitor is not None}

    def require_task_controller(account_id: str) -> TaskController:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if task_controller is None:
            raise HTTPException(status_code=503, detail="Task dispatch is not enabled")
        return task_controller

    def require_recovery_store(account_id: str) -> RecoveryStore:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if recovery_store is None:
            raise HTTPException(status_code=503, detail="Recovery policy is not available")
        return recovery_store

    @app.get("/api/v1/recovery", dependencies=[Depends(authorized)])
    def all_account_recovery() -> dict[str, object]:
        if recovery_store is None:
            return {"enabled": False, "accounts": []}
        return {"enabled": True, "supervisor_enabled": recovery_supervisor is not None,
                "accounts": [{
                    **recovery_store.summary(account),
                    "server_token_available": bool(
                        recovery_credentials and recovery_credentials.available(account)),
                    "session_status": owner.status(account.id),
                } for account in configured_accounts]}

    @app.get("/api/v1/accounts/{account_id}/recovery", dependencies=[Depends(authorized)])
    def account_recovery(account_id: str) -> dict[str, object]:
        journal = require_recovery_store(account_id)
        account=account_by_id[account_id]
        return {**journal.summary(account),
                "server_token_available": bool(
                    recovery_credentials and recovery_credentials.available(account)),
                "supervisor_enabled": recovery_supervisor is not None,
                "session_status": owner.status(account.id)}

    @app.put("/api/v1/accounts/{account_id}/recovery/policy",
             dependencies=[Depends(authorized)])
    def set_account_recovery_policy(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        journal = require_recovery_store(account_id)
        if (set(payload) - {"enabled","auto_resume","grace_seconds",
                            "expected_revision","confirmed"}
                or payload.get("confirmed") is not True):
            raise HTTPException(status_code=422, detail="Explicit approved recovery policy required")
        if (payload.get("enabled") is True and (
            recovery_credentials is None or
            not recovery_credentials.available(account_by_id[account_id])
        )):
            raise HTTPException(status_code=409,detail="Import an exact protected lobby token first")
        try:
            return journal.set_policy(
                account_by_id[account_id],
                enabled=payload.get("enabled"),
                auto_resume=payload.get("auto_resume",False),
                grace_seconds=payload.get("grace_seconds",300),
                expected_revision=payload.get("expected_revision"),
            )
        except RecoveryConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/recovery/pause",
              dependencies=[Depends(authorized)])
    def pause_account_recovery(
        account_id: str, payload: Annotated[dict[str,object],Body()],
    ) -> dict[str,object]:
        journal=require_recovery_store(account_id)
        if set(payload)-{"seconds","confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422,detail="Explicit browser-use pause approval required")
        try:
            return journal.pause(account_by_id[account_id],seconds=payload.get("seconds"))
        except RecoveryConflict as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/recovery/unpause",
              dependencies=[Depends(authorized)])
    def unpause_account_recovery(
        account_id: str, payload: Annotated[dict[str,object],Body()],
    ) -> dict[str,object]:
        journal=require_recovery_store(account_id)
        if set(payload)!={"confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422,detail="Explicit browser-resume approval required")
        try:
            return journal.unpause(account_by_id[account_id])
        except RecoveryConflict as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/recovery/import-saved-token",
              dependencies=[Depends(authorized)])
    def import_saved_recovery_token(
        account_id: str, payload: Annotated[dict[str, object],Body()],
    ) -> dict[str,object]:
        require_recovery_store(account_id)
        if set(payload)!={"confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422,detail="Exact account credential import consent required")
        if recovery_credentials is None:
            raise HTTPException(status_code=503,detail="Protected credential import unavailable")
        try:
            recovery_credentials.import_saved(account_by_id[account_id],confirmed=True)
        except RecoveryCredentialsUnavailable as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from exc
        return {"account_id":account_id,"server_token_available":True,"status":"imported"}

    @app.post("/api/v1/accounts/{account_id}/recovery/resume-now",
              dependencies=[Depends(authorized)])
    def resume_account_recovery(
        account_id: str, payload: Annotated[dict[str, object],Body()],
    ) -> dict[str,str]:
        require_recovery_store(account_id)
        if set(payload)!={"confirmed"} or payload.get("confirmed") is not True:
            raise HTTPException(status_code=422,detail="Explicit browser-session interruption consent required")
        if recovery_supervisor is None:
            raise HTTPException(status_code=503,detail="Automatic recovery supervisor is disabled")
        try:
            return recovery_supervisor.request_now(account_by_id[account_id])
        except (RecoveryWorkerError,RecoveryConflict) as exc:
            raise HTTPException(status_code=409,detail=str(exc)) from exc

    @app.post("/api/v1/recovery/policy/bulk",dependencies=[Depends(authorized)])
    def bulk_recovery_policy(
        payload: Annotated[dict[str,object],Body()],
    ) -> dict[str,object]:
        if recovery_store is None:
            raise HTTPException(status_code=503,detail="Recovery policy unavailable")
        if (set(payload)-{"account_ids","enabled","auto_resume","grace_seconds","confirmed"}
                or payload.get("confirmed") is not True):
            raise HTTPException(status_code=422,detail="Explicit bulk policy approval required")
        ids=payload.get("account_ids")
        if not isinstance(ids,list) or not 1<=len(ids)<=len(configured_accounts) or any(
            not isinstance(aid,str) for aid in ids
        ) or len(set(ids))!=len(ids):
            raise HTTPException(status_code=422,detail="Select unique configured account IDs")
        results=[]
        for aid in ids:
            account=account_by_id.get(aid)
            if account is None:
                results.append({"account_id":aid,"status":"unknown_account"})
                continue
            if (payload.get("enabled") is True and
                    (recovery_credentials is None or not recovery_credentials.available(account))):
                results.append({"account_id":aid,"status":"token_unavailable"})
                continue
            try:
                policy=recovery_store.set_policy(
                    account, enabled=payload.get("enabled"),
                    auto_resume=payload.get("auto_resume",False),
                    grace_seconds=payload.get("grace_seconds",300),
                )
                results.append({"account_id":aid,"status":"saved","policy":policy})
            except RecoveryConflict:
                results.append({"account_id":aid,"status":"conflict"})
        return {"results":results}

    @app.get("/api/v1/accounts/{account_id}/recovery/jobs",
             dependencies=[Depends(authorized)])
    def desired_account_jobs(account_id: str) -> dict[str,object]:
        journal=require_recovery_store(account_id)
        account = account_by_id[account_id]
        jobs = journal.desired(account, include_config=True)
        for job in jobs:
            if job["restart_class"] == "fixed_transfer":
                try:
                    job["transfer_progress"] = journal.fixed_transfer_progress(
                        account, job["config"],
                    )
                except RecoveryConflict:
                    # Missing or corrupt progress must be visible as uncertain,
                    # not silently interpreted as zero shipments.
                    job["transfer_progress"] = {"uncertain": True}
        return {"account_id":account_id,
                "jobs":jobs,
                "receipts":journal.receipts(account)}

    @app.get("/api/v1/accounts/{account_id}/tasks/preflight", dependencies=[Depends(authorized)])
    def task_preflight(account_id: str, task: str) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.preflight(account_id, task)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (TaskUnavailable, EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Task prerequisites unavailable") from exc

    @app.get("/api/v1/accounts/{account_id}/activity", dependencies=[Depends(authorized)])
    def account_activity(account_id: str, before: int | None = None,
                         limit: int = 50, status: str = "all") -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.activity(account_id, before=before, limit=limit, status=status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid activity filter") from exc
        except (TaskUnavailable, OSError) as exc:
            raise HTTPException(status_code=503, detail="Activity unavailable") from exc

    @app.get("/api/v1/accounts/{account_id}/tasks", dependencies=[Depends(authorized)])
    def list_account_tasks(account_id: str) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.list_tasks(account_id)
        except (TaskUnavailable, EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Existing task owner unavailable") from exc

    @app.post("/api/v1/accounts/{account_id}/tasks", dependencies=[Depends(authorized)])
    def start_account_task(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        from daedalus.reviewed_batch import BATCH_REVIEW_TASKS

        if isinstance(payload.get("task"), str) and payload["task"] in BATCH_REVIEW_TASKS - {"constructionList", "sendResources"}:
            raise HTTPException(status_code=422, detail="Use the reviewed operation endpoint")
        if payload.get("task") == "constructionList":
            config = payload.get("config")
            if isinstance(config, dict) and ("supply_review" in config or config.get("shipments")):
                raise HTTPException(status_code=422, detail="Review construction supplies first")
        if payload.get("task") == "sendResources":
            config = payload.get("config")
            routes = config.get("routes") if isinstance(config, dict) else None
            if isinstance(routes, list) and any(isinstance(r, dict) and
                    ("island" in r or "recipient" in r) for r in routes):
                raise HTTPException(status_code=422, detail="Review external shipments first")
        if payload.get("task") == "resourceTransportManager":
            config = payload.get("config")
            if (isinstance(config, dict) and ("recipient" in config or "island" in config)
                    and (config.get("mode") != "consolidate" or any(
                        type(config.get(k)) is not int or not 0 < config[k] < 10**12
                        for k in ("recipient", "island", "destination_city")))):
                raise HTTPException(status_code=422, detail="Choose a verified external recipient")
        return dispatch_account_task(account_id, payload)

    def dispatch_account_task(account_id: str, payload: dict[str, object]) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            confirmed = payload.get("confirmed") is True
            return controller.start(
                account_id, payload.get("task"), payload.get("config"),
                payload.get("request_id"), confirmed=confirmed,
            )
        except TaskPrerequisiteMissing as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TaskRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except TaskConflict as exc:
            raise HTTPException(status_code=409, detail="Conflicting task request ID") from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (TaskUnavailable, EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Existing authenticated task worker unavailable") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Task dispatch status is unconfirmed") from exc

    @app.post("/api/v1/tasks/reviewed-batch-check", dependencies=[Depends(authorized)])
    def reviewed_batch_check(payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        from daedalus.reviewed_batch import validated_batch_entries

        if set(payload) != {"entries"}:
            raise HTTPException(status_code=422, detail="Invalid independent reviews")
        try:
            entries = validated_batch_entries(payload["entries"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid independent reviews") from exc
        blocked = []
        for row in entries:
            aid, task = row["account_id"], row["task"]
            try:
                operation_previews.check_unused(row["preview_id"], aid, task)
                controller = require_task_controller(aid)
                readiness = controller.preflight(aid, task)
                if readiness.get("ready") is not True or readiness.get("unresolved_request") is not False:
                    blocked.append({"account_id": aid, "reason": "prerequisites"})
            except PreviewUnavailable:
                blocked.append({"account_id": aid, "reason": "review_unavailable"})
            except (HTTPException, ValueError, TaskUnavailable, EngineIPCUnavailable, SessionBusyError):
                blocked.append({"account_id": aid, "reason": "unavailable"})
        # A long preflight must not silently leave earlier tickets expired.
        blocked_ids = {row["account_id"] for row in blocked}
        for row in entries:
            if row["account_id"] not in blocked_ids:
                try:
                    operation_previews.check_unused(row["preview_id"], row["account_id"], row["task"])
                except PreviewUnavailable:
                    blocked.append({"account_id": row["account_id"], "reason": "review_unavailable"})
        # No claims or game writes. Every eventual start still claims its own
        # ticket, checks prerequisites and revalidates its game data.
        return {"account_ids": [r["account_id"] for r in entries], "blocked": blocked}

    @app.post(
        "/api/v1/accounts/{account_id}/tasks/construction-start",
        dependencies=[Depends(authorized)],
    )
    def start_reviewed_construction(
        account_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        return start_reviewed_operation(account_id, "constructionList", payload)

    @app.post(
        "/api/v1/accounts/{account_id}/tasks/donation-start",
        dependencies=[Depends(authorized)],
    )
    def start_reviewed_donation(account_id: str,
                               payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "donate", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/fill-warehouse-start", dependencies=[Depends(authorized)])
    def start_fill_warehouse(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "fillCityWarehouse", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/consolidate-start", dependencies=[Depends(authorized)])
    def start_reviewed_consolidate(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "consolidateResources", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/transport-policy-start", dependencies=[Depends(authorized)])
    def start_reviewed_transport_policy(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "resourceTransportManager", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/donation-policy-start", dependencies=[Depends(authorized)])
    def start_reviewed_donation_policy(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "donationBot", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/island-monitor-start", dependencies=[Depends(authorized)])
    def start_reviewed_island_monitor(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "searchForIslandSpaces", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/world-report-start", dependencies=[Depends(authorized)])
    def start_reviewed_world_report(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "dumpWorld", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/piracy-start", dependencies=[Depends(authorized)])
    def start_reviewed_piracy(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "autoPirate", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/research-start", dependencies=[Depends(authorized)])
    def start_reviewed_research(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "research", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/tavern-start", dependencies=[Depends(authorized)])
    def start_reviewed_tavern(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "tavernManager", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/miracle-start", dependencies=[Depends(authorized)])
    def start_reviewed_miracle(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "activateMiracle", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/shrine-start", dependencies=[Depends(authorized)])
    def start_reviewed_shrine(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "activateShrine", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/workshop-start", dependencies=[Depends(authorized)])
    def start_reviewed_workshop(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "UpgradeUnits", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/buy-start", dependencies=[Depends(authorized)])
    def start_reviewed_buy(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "buyResources", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/sell-start", dependencies=[Depends(authorized)])
    def start_reviewed_sell(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "sellResources", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/distribution-start", dependencies=[Depends(authorized)])
    def start_distribution(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "distributeResources", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/daily-start", dependencies=[Depends(authorized)])
    def start_daily(account_id: str, payload: Annotated[dict[str, object], Body()]):
        return start_reviewed_operation(account_id, "loginDaily", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/shipment-start", dependencies=[Depends(authorized)])
    def start_reviewed_shipment(account_id: str, payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "sendResources", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/vacation-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_vacation(account_id: str,
                                payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "vacationMode", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/attack-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_attack(account_id: str,
                               payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "attackBarbarians", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/grind-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_grind(account_id: str,
                               payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "autoBarbarians", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/training-start", dependencies=[Depends(authorized)])
    def start_reviewed_training(account_id: str,
                               payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "trainArmy", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/station-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_station(account_id: str,
                               payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "stationArmy", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/build-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_build(account_id: str,
                             payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "constructBuilding", payload)

    @app.post("/api/v1/accounts/{account_id}/tasks/layout-start",
              dependencies=[Depends(authorized)])
    def start_reviewed_layout(account_id: str,
                              payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        return start_reviewed_operation(account_id, "reorganizeCityBuildings", payload)

    @app.post(
        "/api/v1/accounts/{account_id}/tasks/worker-start",
        dependencies=[Depends(authorized)],
    )
    def start_reviewed_worker(account_id: str,
                             payload: Annotated[dict[str, object], Body()]) -> dict[str, object]:
        task = payload.get("task")
        if not isinstance(task, str) or task not in WORKER_TASKS:
            raise HTTPException(status_code=422, detail="Invalid worker operation")
        return start_reviewed_operation(
            account_id, task, {k: v for k, v in payload.items() if k != "task"},
        )

    def start_reviewed_operation(account_id: str, task: str,
                                 payload: dict[str, object]) -> dict[str, object]:
        require_task_controller(account_id)
        key, request_id = payload.get("preview_id"), payload.get("request_id")
        if (
            set(payload) != {"preview_id", "request_id", "confirmed"}
            or payload.get("confirmed") is not True
            or not isinstance(key, str) or len(key) != 43
            or not isinstance(request_id, str)
        ):
            raise HTTPException(status_code=422, detail="Explicit operation review required")
        try:
            parsed = UUID(request_id)
            if parsed.version != 4 or str(parsed) != request_id:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Valid request ID required") from exc
        try:
            config = operation_previews.claim(key, account_id, task, request_id)
        except PreviewUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return dispatch_account_task(account_id, {
            "task": task, "config": config,
            "request_id": request_id, "confirmed": True,
        })

    @app.post(
        "/api/v1/accounts/{account_id}/tasks/{task_id}/stop",
        dependencies=[Depends(authorized)],
    )
    def stop_account_task(account_id: str, task_id: str) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.stop(account_id, task_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (TaskUnavailable, EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Managed engine task unavailable") from exc

    @app.post(
        "/api/v1/accounts/{account_id}/tasks/requests/{request_id}/acknowledge",
        dependencies=[Depends(authorized)],
    )
    def acknowledge_task_request(
        account_id: str, request_id: str, payload: Annotated[dict[str, object], Body()],
    ) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.acknowledge_uncertain_request(
                account_id, request_id, confirmed=payload.get("confirmed") is True,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/warehouses/{account_id}", dependencies=[Depends(authorized)])
    def warehouses(account_id: str) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if snapshot_provider is None and ipc_client is None:
            raise HTTPException(
                status_code=503, detail="No authenticated account snapshot provider is connected"
            )
        try:
            if snapshot_provider is not None:
                snapshots = snapshot_provider(account_id)
            else:
                snapshots = ipc_client.warehouses(account_by_id[account_id])
        except Exception as exc:
            # Do not expose session internals or authentication material to clients.
            raise HTTPException(status_code=503, detail="Warehouse snapshots unavailable") from exc
        return {"account_id": account_id,
                "cities": [snapshot.to_dict() for snapshot in snapshots],
                "synthetic_demo": demo_mode}

    return app
