"""Private Selenium helper: all browser and Keychain work runs outside the Qt GUI.

Invoked only by SeleniumLoginWorker. Credentials arrive via an anonymous stdin
pipe, never command-line arguments, files, environment variables, or server API.
A parent-owned process group makes a stuck ChromeDriver and its Chrome children
killable even while an individual WebDriver call refuses to return.
"""
from __future__ import annotations

import json
import sys

from daedalus.desktop.selenium_auth import (
    GameforgeCredentials,
    SeleniumLoginUnavailable,
    login_world,
)
from daedalus.desktop.selenium_credentials import (
    LoginCredentialError,
    get_saved_login,
    legacy_warehouse_login,
)
from daedalus.desktop.selenium_vault import seal_login, unseal_login


def _emit(kind: str, value: object = None) -> None:
    print(json.dumps({"kind": kind, "value": value}, separators=(",", ":")), flush=True)


def execute(request: dict[str, object]) -> int:
    """Process exactly one account. Do not start more accounts from the child."""
    aid, world, origin, record = (
        request.get("account_id"), request.get("world"),
        request.get("origin"), request.get("record"),
    )
    if not all(isinstance(v, str) and v for v in (aid, world, origin)):
        _emit("error", "Invalid login request")
        return 2
    if not isinstance(record, dict) or record.get("id") != aid or record.get("world") != world:
        _emit("error", "Invalid account selection")
        return 2
    credentials = None
    remember = request.get("remember") is True
    entered = request.get("credentials")
    if entered is not None:
        if not isinstance(entered, dict) or set(entered) != {"email", "password"}:
            _emit("error", "Invalid login credentials")
            return 2
        credentials = GameforgeCredentials(entered["email"], entered["password"])
    else:
        _emit("stage", "resolving_saved_login")
        try:
            credentials = get_saved_login(origin, aid, world)
            if credentials is None:
                envelope = request.get("sealed_vault")
                if isinstance(envelope, dict):
                    credentials = unseal_login(origin, aid, world, envelope)
            if credentials is None:
                credentials = legacy_warehouse_login(record)
            remember = credentials is not None
        except LoginCredentialError:
            # Keychain may be locked/unavailable. The GUI can offer manual input.
            _emit("stage", "keychain_unavailable")
    if credentials is None:
        _emit("credentials_required")
        return 0

    # Do not send a saved password back to the GUI. Only an email address
    # is required to bind the resulting world cookie to the chosen account.
    _emit("credentials", {"email": credentials.email, "remember": remember})
    _emit("stage", "launching_chrome")
    login_options = {"visible_only": True} if request.get("visible_only") is True else {}
    cookie = login_world(
        credentials, world, notify=lambda stage: _emit("stage", stage), **login_options,
    )

    # Only the client-sealed login envelope is prepared here. The server may
    # persist it ONLY after independent account verification. Never persist
    # the plaintext password before that authenticated receipt.
    vault = None
    if remember:
        try:
            vault = seal_login(origin, aid, world, credentials)
        except LoginCredentialError:
            _emit("stage", "keychain_save_failed")
    if vault is not None:
        _emit("vault", vault)
    _emit("cookie", cookie)
    return 0


def main() -> int:
    try:
        raw = sys.stdin.buffer.readline(16385)
        if len(raw) > 16384:
            _emit("error", "Login request too large")
            return 2
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise TypeError("Expected login request object")
        return execute(request)
    except SeleniumLoginUnavailable as exc:
        _emit("error", str(exc))
        return 1
    except Exception:  # noqa: BLE001 - never leak credentials or WebDriver tracebacks
        # Deliberately do not print tracebacks or credentials to stderr.
        _emit("error", "Automatic sign-in failed; no session was imported")
        return 1


if __name__ == "__main__":
    sys.exit(main())
