"""Minimal authenticated, read-only control API for desktop and remote clients.

No live account worker or game login is launched by this module. Warehouse
snapshots require an explicitly injected provider; until then the API honestly
returns 503 rather than fabricated values.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

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
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient
from daedalus.engine_registry import inspect_engine
from daedalus.login_vault import (
    LoginVaultUnavailable,
    read_login_vault,
    validate_login_vault,
    write_login_vault,
)
from daedalus.native_browser_handoff import NativeBrowserHandoff, NativeHandoffUnavailable
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
        or native_browser_handoff.monitor is not recovery_monitor
        or enable_account_editing
    ):
        raise ValueError("Native browser handoff needs the exact fixed authoritative owner")
    store = AccountMetadataStore(accounts_path) if enable_account_editing else None
    if store is not None:
        saved = store.snapshot()
        if [Account(**row) for row in saved["accounts"]] != configured_accounts:
            raise ValueError("Account metadata and controller configuration differ")
    @asynccontextmanager
    async def monitor_lifespan(_app: FastAPI):
        if recovery_monitor is not None:
            recovery_monitor.start()
        try:
            yield
        finally:
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
        lifespan=monitor_lifespan if recovery_monitor is not None else None,
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
        return {
            "service": "daedalus",
            "version": __version__,
            "mode": (
                "synthetic_demo" if demo_mode else
                "task_control_opt_in" if task_controller is not None else "read_only"
            ),
            "synthetic_demo": demo_mode,
            "authenticated_workers": sum(
                owner.status(account.id) == SessionPhase.AUTHENTICATED.value
                for account in configured_accounts
            ),
        }

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
            "operations": [item.to_dict() for item in operations],
            "structured_engine_dispatch": task_controller is not None,
            "session_monitoring": recovery_monitor is not None,
            "synthetic_demo": demo_mode,
        }

    @app.get("/api/v1/engine/connected-accounts", dependencies=[Depends(authorized)])
    def connected_accounts() -> dict[str, object]:
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
        if (set(payload) != {"upgrades"}
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
            return ipc_client.construction_preview(account, city_id, upgrades)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Construction preview rejected invalid city or targets"
            ) from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="Authenticated construction preview unavailable"
            ) from exc

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

    @app.get("/api/v1/accounts/{account_id}/tasks/preflight", dependencies=[Depends(authorized)])
    def task_preflight(account_id: str, task: str) -> dict[str, object]:
        controller = require_task_controller(account_id)
        try:
            return controller.preflight(account_id, task)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (TaskUnavailable, EngineIPCUnavailable, SessionBusyError) as exc:
            raise HTTPException(status_code=503, detail="Task prerequisites unavailable") from exc

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
