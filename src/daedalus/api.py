"""Minimal authenticated, read-only control API for desktop and remote clients.

No live account worker or game login is launched by this module. Warehouse
snapshots require an explicitly injected provider; until then the API honestly
returns 503 rather than fabricated values.
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from daedalus import __version__
from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
from daedalus.accounts import Account, load_accounts
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient, ExistingTaskIPCClient
from daedalus.engine_registry import inspect_engine
from daedalus.warehouse import CityWarehouseSnapshot

SnapshotProvider = Callable[[str], list[CityWarehouseSnapshot]]


class TaskStartRequest(BaseModel):
    """Validated caller-selected operation; the engine validates each task schema."""

    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=80)
    config: dict[str, object] = Field(default_factory=dict)
    request_id: UUID


def create_app(
    *,
    accounts_path: str | Path | None = None,
    api_token: str | None = None,
    snapshot_provider: SnapshotProvider | None = None,
    session_coordinator: AccountSessionCoordinator | None = None,
    ipc_client: ExistingIPCClient | None = None,
    task_controller: ExistingTaskIPCClient | None = None,
) -> FastAPI:
    """Create an API with mandatory bearer authentication and no game side effects."""
    token = api_token if api_token is not None else os.environ.get("DAEDALUS_API_TOKEN")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("DAEDALUS_API_TOKEN must be a secret of at least 32 characters")
    if task_controller is not None and ipc_client is None:
        ipc_client = task_controller
    configured_accounts: list[Account] = load_accounts(accounts_path)
    account_by_id = {account.id: account for account in configured_accounts}
    owner = session_coordinator or AccountSessionCoordinator(configured_accounts)
    if not owner.matches_accounts(configured_accounts):
        raise ValueError("Session coordinator and configuration must contain the same accounts")
    # Account workers may use this in-process coordinator later; startup never acquires a lease.
    app = FastAPI(
        title="Daedalus Controller API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

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
            "mode": "task_control" if task_controller is not None else "read_only",
            "authenticated_workers": sum(
                owner.status(account.id) == SessionPhase.AUTHENTICATED.value
                for account in configured_accounts
            ),
        }

    @app.get("/api/v1/accounts", dependencies=[Depends(authorized)])
    def accounts() -> dict[str, object]:
        entries = []
        for account in configured_accounts:
            entry = account.to_dict()
            entry["session_status"] = owner.status(account.id)
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
        if ipc_client is None:
            raise HTTPException(status_code=503, detail="Existing IPC attachment is disabled")
        try:
            cities = ipc_client.cities(account)
        except (EngineIPCUnavailable, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Authenticated IkaBot session unavailable") from exc
        return {"account_id": account_id, "cities": cities}

    @app.get("/api/v1/task-control", dependencies=[Depends(authorized)])
    def task_control_status() -> dict[str, bool]:
        return {"enabled": task_controller is not None, "requires_existing_session": True}

    def require_task_controller() -> ExistingTaskIPCClient:
        if task_controller is None:
            raise HTTPException(status_code=503, detail="Task control is disabled")
        return task_controller

    def require_account(account_id: str) -> Account:
        account = account_by_id.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return account

    @app.get("/api/v1/accounts/{account_id}/tasks", dependencies=[Depends(authorized)])
    def managed_tasks(account_id: str) -> dict[str, object]:
        account = require_account(account_id)
        controller = require_task_controller()
        try:
            rows = controller.list_tasks(account)
        except (EngineIPCUnavailable, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Managed engine tasks unavailable") from exc
        return {"account_id": account_id, "tasks": rows}

    @app.post("/api/v1/accounts/{account_id}/tasks", dependencies=[Depends(authorized)])
    def start_managed_task(account_id: str, body: TaskStartRequest) -> dict[str, object]:
        account = require_account(account_id)
        controller = require_task_controller()
        if not account.enabled:
            raise HTTPException(status_code=409, detail="Account is disabled")
        if body.request_id.version != 4:
            raise HTTPException(status_code=422, detail="Request id must be UUID4")
        if len(json.dumps(body.config, allow_nan=False)) > 65536 or "session" in body.config:
            raise HTTPException(status_code=422, detail="Invalid or oversized task configuration")
        # The registry is sourced from the checked-out public IkaBot built-in modules.
        allowed = {cap.name for cap in inspect_engine() if cap.kind == "background_task"}
        if body.task not in allowed:
            raise HTTPException(status_code=422, detail="Task is not a built-in background operation")
        try:
            result = controller.start_task(account, body.task, body.config, str(body.request_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid task request") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Task execution unavailable") from exc
        return {"account_id": account_id, **result}

    @app.delete("/api/v1/accounts/{account_id}/tasks/{pid}", dependencies=[Depends(authorized)])
    def stop_managed_task(account_id: str, pid: int) -> dict[str, object]:
        account = require_account(account_id)
        controller = require_task_controller()
        try:
            result = controller.stop_task(account, pid)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid managed task PID") from exc
        except EngineIPCUnavailable as exc:
            raise HTTPException(status_code=503, detail="Task stop unavailable") from exc
        return {"account_id": account_id, **result}

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
        return {"account_id": account_id, "cities": [snapshot.to_dict() for snapshot in snapshots]}

    return app
