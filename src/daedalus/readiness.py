"""Offline, secret-free setup diagnostics and isolated synthetic API smoke test.

No production account file, keyring value, saved browser cookie, real IPC
socket or Gameforge endpoint is inspected. The optional smoke uses FastAPI's
in-process TestClient and the explicitly synthetic demo account provider.
"""

from __future__ import annotations

import importlib.util
import secrets

from daedalus import __version__
from daedalus.engine_registry import (
    EngineNotFoundError,
    inspect_engine,
    supports_structured_cli,
)


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def offline_readiness() -> dict[str, object]:
    """Report observed installation facts and honest static feature scope."""
    try:
        count = len(inspect_engine())
        available = True
        cli_available = supports_structured_cli()
    except (EngineNotFoundError, OSError, SyntaxError, ValueError):
        count, available, cli_available = 0, False, False
    return {
        "project": "Daedalus",
        "version": __version__,
        "stage": "existing-session-preview",
        "engine_source_available": available,
        "engine_capabilities_found": count,
        "engine_cli_available": cli_available,
        "engine_integrated": bool(available and cli_available),
        "engine_importable": _installed("ikabot"),
        "server_implemented": True,
        "server_dependencies_installed": all(
            _installed(name) for name in ("fastapi", "uvicorn", "filelock")
        ),
        "server_mode": "read_only_by_default",
        "desktop_implemented": True,
        "desktop_dependencies_installed": all(
            _installed(name) for name in ("PySide6", "qfluentwidgets")
        ),
        "keyring_package_installed": _installed("keyring"),
        "synthetic_demo_available": True,
        "existing_session_ipc_opt_in": True,
        "existing_session_task_control_opt_in": True,
        "saved_cookie_worker_bootstrap_opt_in": True,
        "session_monitoring_opt_in": True,
        "host_local_browser_staging_implemented": True,
        "dedicated_worker_remote_rebind_opt_in": True,
        "server_page_player_attestation_implemented": True,
        "real_world_player_attestation_tested": None,
        "cookie_upload_api_supported": False,
        "new_worker_bootstrap_implemented": True,
        "new_worker_bootstrap_scope": "explicit_single_account_saved_cookies_only",
        "automatic_browser_authentication_implemented": False,
        "production_ready": False,
        "live_accounts_configured": None,
        "real_game_session_tested": None,
        "network_requests_performed": 0,
    }


class OfflineSmokeError(RuntimeError):
    """No underlying API exception text or request body is disclosed."""


def synthetic_smoke() -> dict[str, object]:
    """Exercise the real FastAPI route stack with fictional demo data only."""
    try:
        from fastapi.testclient import TestClient

        from daedalus.api import create_app
    except (ImportError, RuntimeError) as exc:
        raise OfflineSmokeError(
            "Install optional server/client test dependencies to run the synthetic smoke"
        ) from exc

    token = secrets.token_urlsafe(48)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        app = create_app(api_token=token, demo_mode=True)
        with TestClient(app) as client:
            denied = client.get("/api/v1/accounts")
            health = client.get("/api/v1/health")
            accounts = client.get("/api/v1/accounts", headers=headers)
            capabilities = client.get("/api/v1/capabilities", headers=headers)
            if any(response.status_code != 200 for response in (health, accounts, capabilities)):
                raise OfflineSmokeError("Synthetic backend failed a health or metadata check")
            payload = accounts.json()
            configured = payload.get("accounts", [])
            if (
                denied.status_code != 401
                or health.json().get("synthetic_demo") is not True
                or not configured
                or not all(account.get("synthetic") is True for account in configured)
                or capabilities.json().get("synthetic_demo") is not True
            ):
                raise OfflineSmokeError("Synthetic backend returned invalid demo isolation")
            account_id = configured[0]["id"]
            warehouses = client.get(f"/api/v1/warehouses/{account_id}", headers=headers)
            if (
                warehouses.status_code != 200
                or warehouses.json().get("synthetic_demo") is not True
                or not warehouses.json().get("cities")
            ):
                raise OfflineSmokeError("Synthetic warehouse report check failed")
        return {
            "status": "passed",
            "scope": "synthetic_in_process_only",
            "authenticated_routes": True,
            "demo_accounts": len(configured),
            "warehouse_reporting": True,
            "game_network_requests": 0,
        }
    except OfflineSmokeError:
        raise
    except Exception as exc:
        raise OfflineSmokeError("Synthetic offline API smoke could not complete") from exc
