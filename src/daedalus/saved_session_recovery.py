"""Explicit, credential-free probe of previously saved IkaBot world cookies.

Never attempts a new lobby login or CAPTCHA, never puts emails or saved cookies
in the controller API, logs or TOML. Only a single user-confirmed local probe
may invoke the underlying engine's existing Session.from_saved(cookies_only=True).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError
from daedalus.accounts import Account

_SERVICE = "io.github.itshak.daedalus.saved-account-reference"
_COOKIE_SERVICE = "io.github.itshak.daedalus.world-cookie"
_EMAIL = re.compile(r"[^\s@]{1,120}@[^\s@]{1,120}\.[^\s@]{2,63}\Z")
_WORLD = re.compile(r"s([0-9]{1,6})-([a-z]{2,4})\Z", re.IGNORECASE)


class SavedSessionUnavailable(RuntimeError):
    """Only generic, nonsecret probe failures are exposed to the caller."""


class CredentialStore(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def get_password(self, service: str, username: str) -> str | None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def _store(provided: CredentialStore | None) -> CredentialStore:
    if provided is not None:
        return provided
    try:
        import keyring
    except ImportError as exc:
        raise SavedSessionUnavailable(
            "Install Daedalus recovery extras to enable OS-keyring bindings"
        ) from exc

    # Some optional keyring packages provide unencrypted plain-text or file
    # storage. World cookies must never fall back to such a provider.
    safe_backends = (
        "keyring.backends.macOS", "keyring.backends.Windows",
        "keyring.backends.SecretService", "keyring.backends.kwallet",
        "keyring.backends.libsecret",
    )

    def backend_is_safe(backend: object) -> bool:
        qualified = type(backend).__module__
        if qualified.startswith(safe_backends):
            return True
        if qualified == "keyring.backends.chainer":
            members = getattr(backend, "backends", ())
            return bool(members) and all(backend_is_safe(member) for member in members)
        return False

    try:
        backend = keyring.get_keyring()
    except Exception as exc:
        raise SavedSessionUnavailable("No protected OS keyring is available") from exc
    if not backend_is_safe(backend):
        raise SavedSessionUnavailable(
            "A protected operating-system credential backend is required"
        )
    return keyring


def _account_key(account: Account) -> str:
    # Include the normalized world/player to invalidate bindings after metadata
    # identity changes; never key a secret to a mutable display label alone.
    import hashlib

    material = (
        account.id + "\0" + account.world.casefold() + "\0" + account.player.casefold()
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def bind_saved_email(
    account: Account, email: str, *, credential_store: CredentialStore | None = None,
) -> None:
    """Associate an already configured IkaBot saved-user identity in OS keyring.

    No email is printed, returned, written to TOML, passed in CLI args or sent
    through the HTTP API. The actual cookies remain owned by IkaBot.
    """
    if not account.enabled:
        raise SavedSessionUnavailable("The account is disabled")
    if not isinstance(email, str) or _EMAIL.fullmatch(email.strip()) is None:
        raise SavedSessionUnavailable("Enter a valid email address in the protected prompt")
    try:
        _store(credential_store).set_password(_SERVICE, _account_key(account), email.strip())
    except Exception as exc:
        raise SavedSessionUnavailable("Unable to store account binding in the OS keyring") from exc


def unbind_saved_email(
    account: Account, *, credential_store: CredentialStore | None = None,
) -> None:
    try:
        provider = _store(credential_store)
        key = _account_key(account)
        if provider.get_password(_SERVICE, key) is not None:
            provider.delete_password(_SERVICE, key)
    except Exception as exc:
        raise SavedSessionUnavailable("Unable to remove account binding from keyring") from exc


def _email_binding(
    account: Account, credential_store: CredentialStore | None,
) -> str:
    try:
        value = _store(credential_store).get_password(_SERVICE, _account_key(account))
    except Exception as exc:
        raise SavedSessionUnavailable("Unable to read the saved account keyring binding") from exc
    if not isinstance(value, str) or not _EMAIL.fullmatch(value):
        raise SavedSessionUnavailable("Bind an existing saved IkaBot account in the keyring first")
    return value


def _validated_world_cookie(value: object) -> str:
    if (
        not isinstance(value, str) or not 16 <= len(value) <= 4096
        or not value.isascii() or not value.isprintable()
        or any(char in value for char in " ;\\")
    ):
        raise SavedSessionUnavailable("A valid browser world cookie is required")
    return value


def _world_cookie_binding(
    account: Account, credential_store: CredentialStore | None,
) -> str | None:
    try:
        value = _store(credential_store).get_password(
            _COOKIE_SERVICE, _account_key(account),
        )
    except Exception as exc:
        raise SavedSessionUnavailable("Unable to access protected world cookie") from exc
    if value is None:
        return None
    return _validated_world_cookie(value)


def _real_restore(
    account: Account, email: str, world_cookie: str | None = None,
) -> object:
    try:
        from ikabot.web.session import Session
    except ImportError as exc:
        raise SavedSessionUnavailable("Install the vendored IkaBot engine to probe saved cookies") from exc
    # Only the Daedalus-maintained, cookie-only engine overlay may be used.
    # This mode cannot issue a lobby loginLink or launch a new Gameforge login.
    options: dict[str, object] = {
        "mail": email, "world": account.world,
        "player": account.player, "cookies_only": True,
    }
    if world_cookie is not None:
        options["world_cookie_override"] = _validated_world_cookie(world_cookie)
    return Session.from_saved(**options)


def verify_restored_identity(session: object, account: Account) -> None:
    """Require exact world/player and authenticated session before success."""
    match = _WORLD.fullmatch(account.world)
    if match is None:
        raise SavedSessionUnavailable(
            "Safe restoration requires an explicit world identifier such as s301-en"
        )
    world_number, language = match.groups()
    if (
        getattr(session, "logged", False) is not True
        or str(getattr(session, "mundo", "")) != str(int(world_number))
        or str(getattr(session, "servidor", "")).casefold() != language.casefold()
        or str(getattr(session, "username", "")).casefold() != account.player.casefold()
    ):
        raise SavedSessionUnavailable("The saved session did not verify the configured identity")


def probe_saved_cookies(
    account: Account,
    coordinator: AccountSessionCoordinator,
    *,
    confirmed: bool,
    credential_store: CredentialStore | None = None,
    restore: Callable[[Account, str], object] = _real_restore,
) -> dict[str, str]:
    """One explicitly confirmed, lease-guarded probe, never a new login.

    Uses the same local world/player lease as Daedalus task dispatch. Releases
    it and closes the ephemeral HTTP session, successful or not. No production
    bot or stored cookies are modified by Daedalus itself.
    """
    if confirmed is not True:
        raise SavedSessionUnavailable("Explicit confirmation for a read-only game probe is required")
    if not account.enabled or account.id not in coordinator.account_ids:
        raise SavedSessionUnavailable("Account is disabled or not configured")
    # Scope and identity must match, not merely an account id string.
    if coordinator._accounts[account.id] != account:
        raise SavedSessionUnavailable("Saved account identity has changed")
    if _WORLD.fullmatch(account.world) is None:
        raise SavedSessionUnavailable(
            "Explicit canonical world identifier required, for example s301-en"
        )
    email = _email_binding(account, credential_store)
    current_cookie = (
        _world_cookie_binding(account, credential_store)
        if restore is _real_restore else None
    )
    try:
        with coordinator.acquire(account.id):
            session = None
            try:
                try:
                    if restore is _real_restore:
                        session = _real_restore(account, email, current_cookie)
                    else:
                        session = restore(account, email)
                except SavedSessionUnavailable:
                    raise
                except Exception as exc:
                    raise SavedSessionUnavailable(
                        "Saved cookies did not validate; manual recovery is required"
                    ) from exc
                verify_restored_identity(session, account)
                return {"account_id": account.id, "status": "saved_session_valid"}
            finally:
                if session is not None:
                    # A probe must never leave a game worker or HTTP connection alive.
                    http = getattr(session, "s", None)
                    if http is not None and callable(getattr(http, "close", None)):
                        try:
                            http.close()
                        except (OSError, ValueError):
                            import logging

                            logging.getLogger("daedalus.recovery").warning(
                                "Ephemeral session connection cleanup was incomplete"
                            )
    except SessionBusyError as exc:
        raise SavedSessionUnavailable(
            "Another Daedalus worker currently owns this account on the host"
        ) from exc



def _verify_and_save_world_cookie(
    account: Account,
    cookie: str,
    *,
    credential_store: CredentialStore | None,
    restore: Callable[[Account, str, str], object],
) -> dict[str, str]:
    """Caller MUST hold the account lease through validation and keyring save."""
    email = _email_binding(account, credential_store)
    session = None
    try:
        try:
            session = restore(account, email, cookie)
            verify_restored_identity(session, account)
        except Exception as exc:
            raise SavedSessionUnavailable(
                "Browser world session could not verify the selected account"
            ) from exc
        try:
            _store(credential_store).set_password(
                _COOKIE_SERVICE, _account_key(account), cookie,
            )
        except Exception as exc:
            raise SavedSessionUnavailable("Unable to store verified world cookie in keyring") from exc
        return {"account_id": account.id, "status": "world_cookie_bound"}
    finally:
        if session is not None:
            http = getattr(session, "s", None)
            if callable(getattr(http, "close", None)):
                try:
                    http.close()
                except (OSError, ValueError):
                    import logging
                    logging.getLogger("daedalus.recovery").warning(
                        "Ephemeral browser verification cleanup was incomplete"
                    )


def _require_cookie_account(account: Account, coordinator: AccountSessionCoordinator) -> None:
    if (
        not account.enabled
        or account.id not in coordinator.account_ids
        or coordinator._accounts[account.id] != account
        or _WORLD.fullmatch(account.world) is None
    ):
        raise SavedSessionUnavailable("A matching enabled account with canonical world is required")


def bind_world_cookie(
    account: Account,
    coordinator: AccountSessionCoordinator,
    value: str,
    *,
    confirmed: bool,
    credential_store: CredentialStore | None = None,
    restore: Callable[[Account, str, str], object] | None = None,
) -> dict[str, str]:
    """Validate a manually obtained cookie under one lease, then store privately."""
    if confirmed is not True:
        raise SavedSessionUnavailable("Import requires explicit network confirmation")
    cookie = _validated_world_cookie(value)
    _require_cookie_account(account, coordinator)
    _email_binding(account, credential_store)
    try:
        with coordinator.acquire(account.id):
            return _verify_and_save_world_cookie(
                account, cookie, credential_store=credential_store,
                restore=restore or _real_restore,
            )
    except SessionBusyError as exc:
        raise SavedSessionUnavailable("Another worker owns this account on the host") from exc


def assisted_browser_cookie_login(
    account: Account,
    coordinator: AccountSessionCoordinator,
    *,
    confirmed: bool,
    credential_store: CredentialStore | None = None,
    browser_open: Callable[[str], bool] | None = None,
    read_cookie: Callable[[], str] | None = None,
    restore: Callable[[Account, str, str], object] | None = None,
) -> dict[str, str]:
    """Human-operated browser recovery; no CAPTCHA solving or credential capture.

    A host-local lease is held before the browser opens, through the user's
    manual login/challenge and verified cookie persistence. No Daedalus HTTP
    endpoint, environment variable or command argument receives the cookie.
    """
    if confirmed is not True:
        raise SavedSessionUnavailable("Explicit browser recovery approval is required")
    _require_cookie_account(account, coordinator)
    _email_binding(account, credential_store)
    if browser_open is None:
        import webbrowser
        browser_open = webbrowser.open
    if read_cookie is None:
        import getpass
        read_cookie = lambda: getpass.getpass("Authenticated world ikariam cookie (hidden): ")
    try:
        with coordinator.acquire(account.id):
            # Fixed official lobby origin, never user-provided URLs or redirects.
            if browser_open("https://lobby.ikariam.gameforge.com/") is not True:
                raise SavedSessionUnavailable("Could not open the official browser lobby")
            # The operator handles login and any CAPTCHA in their own browser.
            # Only the world cookie is accepted; no passwords/GF tokens.
            cookie = _validated_world_cookie(read_cookie())
            return _verify_and_save_world_cookie(
                account, cookie, credential_store=credential_store,
                restore=restore or _real_restore,
            )
    except SessionBusyError as exc:
        raise SavedSessionUnavailable("Another worker owns this account on the host") from exc


def unbind_world_cookie(
    account: Account, *, credential_store: CredentialStore | None = None,
) -> None:
    """Forget only the exact current account/world/player cookie reference."""
    try:
        provider = _store(credential_store)
        key = _account_key(account)
        if provider.get_password(_COOKIE_SERVICE, key) is not None:
            provider.delete_password(_COOKIE_SERVICE, key)
    except Exception as exc:
        raise SavedSessionUnavailable("Unable to remove protected world cookie") from exc
