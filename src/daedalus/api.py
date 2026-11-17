"""Minimal authenticated, read-only control API for desktop and remote clients.

No live account worker or game login is launched by this module. Warehouse
snapshots require an explicitly injected provider; until then the API honestly
returns 503 rather than fabricated values.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status

from daedalus import __version__
from daedalus.accounts import Account, load_accounts
from daedalus.engine_registry import inspect_engine
from daedalus.warehouse import CityWarehouseSnapshot

SnapshotProvider = Callable[[str], list[CityWarehouseSnapshot]]


def create_app(
    *,
    accounts_path: str | Path | None = None,
    api_token: str | None = None,
    snapshot_provider: SnapshotProvider | None = None,
) -> FastAPI:
    """Create an API with mandatory bearer authentication and no game side effects."""
    token = api_token if api_token is not None else os.environ.get("DAEDALUS_API_TOKEN")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("DAEDALUS_API_TOKEN must be a secret of at least 32 characters")
    configured_accounts: list[Account] = load_accounts(accounts_path)
    account_by_id = {account.id: account for account in configured_accounts}
    app = FastAPI(
        title="Daedalus Read-only API",
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
            "mode": "read_only",
            "authenticated_workers": 0,
        }

    @app.get("/api/v1/accounts", dependencies=[Depends(authorized)])
    def accounts() -> dict[str, object]:
        return {"accounts": [account.to_dict() for account in configured_accounts]}

    @app.get("/api/v1/capabilities", dependencies=[Depends(authorized)])
    def capabilities() -> dict[str, object]:
        operations = inspect_engine()
        return {
            "operations": [item.to_dict() for item in operations],
            "structured_engine_dispatch": False,
        }

    @app.get("/api/v1/warehouses/{account_id}", dependencies=[Depends(authorized)])
    def warehouses(account_id: str) -> dict[str, object]:
        if account_id not in account_by_id:
            raise HTTPException(status_code=404, detail="Account not found")
        if snapshot_provider is None:
            raise HTTPException(
                status_code=503, detail="No authenticated account snapshot provider is connected"
            )
        try:
            snapshots = snapshot_provider(account_id)
        except Exception as exc:
            # Do not expose session internals or authentication material to clients.
            raise HTTPException(status_code=503, detail="Warehouse snapshots unavailable") from exc
        return {"account_id": account_id, "cities": [snapshot.to_dict() for snapshot in snapshots]}

    return app
