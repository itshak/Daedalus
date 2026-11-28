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
    restore_saved_world_without_keychain,
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
    from daedalus import shared_keychain

    if shared_keychain.enabled():
        shared_keychain.accept_pipe_state(request.get("local_vault_state"))
        shared_keychain.observe_unlock(lambda state: _emit("local_vault_state", state))
    credentials = None
    remember = request.get("remember") is True
    entered = request.get("credentials")
    server_vault = request.get("sealed_vault")
    has_vault = isinstance(server_vault, dict)
    visible_only = request.get("visible_only") is True
    skip_saved_session = False

    # If the already-bound backend email has a usable saved exact-world
    # session, do not access either Keychain item at all. This is read-only
    # and still requires the independent encrypted backend verification.
    if entered is None and not visible_only:
        bound_email = record.get("email")
        if isinstance(bound_email, str) and "@" in bound_email:
            skip_saved_session = True
            restored = restore_saved_world_without_keychain(
                bound_email, world, notify=lambda stage: _emit("stage", stage),
            )
            if restored is not None:
                _emit("credentials", {"email": bound_email, "remember": False})
                _emit("cookie", restored)
                return 0

    if entered is not None:
        if not isinstance(entered, dict) or set(entered) != {"email", "password"}:
            _emit("error", "Invalid login credentials")
            return 2
        credentials = GameforgeCredentials(entered["email"], entered["password"])
    else:
        _emit("stage", "resolving_saved_login")
        try:
            # The server already retains an encrypted vault? Use its local
            # Mac key once. Do NOT query the other per-account Keychain item
            # first and then reseal the same password after every login.
            if has_vault:
                credentials = unseal_login(origin, aid, world, server_vault)
            else:
                credentials = get_saved_login(origin, aid, world)
            if credentials is None:
                credentials = legacy_warehouse_login(record)
            remember = credentials is not None
        except LoginCredentialError:
            # One failed item access is sufficient. Re-prompting through an
            # additional Keychain item would cause repetitive macOS dialogs.
            _emit("stage", "keychain_unavailable")
            credentials = legacy_warehouse_login(record)
            remember = credentials is not None

    if credentials is None:
        _emit("credentials_required")
        return 0

    # Only the email is returned to the GUI; the password stays in the child.
    _emit("credentials", {"email": credentials.email, "remember": remember})
    _emit("stage", "launching_chrome")
    login_options = {"visible_only": True} if visible_only else {}
    if skip_saved_session:
        login_options["skip_saved_session"] = True
    cookie = login_world(
        credentials, world, notify=lambda stage: _emit("stage", stage), **login_options,
    )

    # Reuse an existing server vault as-is. Generate a new encrypted login
    # only on first backup or when the operator manually changed credentials.
    # This avoids redundant per-account Keychain prompts and writes.
    vault = None
    if remember and (entered is not None or not has_vault):
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
