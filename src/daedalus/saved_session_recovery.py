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
        return keyring
    except ImportError as exc:
        raise SavedSessionUnavailable(
            "Install Daedalus recovery extras to enable OS-keyring bindings"
        ) from exc


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


def _real_restore(account: Account, email: str) -> object:
    try:
        from ikabot.web.session import Session
    except ImportError as exc:
        raise SavedSessionUnavailable("Install the vendored IkaBot engine to probe saved cookies") from exc
    # Only the Daedalus-maintained, cookie-only engine overlay may be used.
    # This mode cannot issue a lobby loginLink or launch a new Gameforge login.
    return Session.from_saved(
        mail=email, world=account.world, player=account.player, cookies_only=True,
    )


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
    try:
        with coordinator.acquire(account.id):
            session = None
            try:
                try:
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
