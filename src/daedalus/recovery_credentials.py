"""Host-only protected Gameforge lobby credential eligibility.

The HTTP controller never accepts raw cookies/passwords or returns lobby tokens.
A deliberate import reads the existing private IkaBot registry ON THE SERVER
and stores the lobby credential in the host's encrypted credential provider.
"""
from __future__ import annotations

import re

from daedalus.accounts import Account
from daedalus.saved_session_recovery import (
    CredentialStore,
    SavedSessionUnavailable,
    _account_key,
    _email_binding,
    _store,
    bind_saved_email,
    unbind_saved_email,
)

_SERVICE = "io.github.itshak.daedalus.gameforge-lobby-token"
_WORLD = re.compile(r"s([0-9]{1,6})-([a-z]{2,4})\Z")
_MAX_TOKEN = 4096


class RecoveryCredentialsUnavailable(RuntimeError):
    """No usable, explicitly approved host-protected lobby credentials."""


def _validated_token(token: object) -> str:
    if (
        not isinstance(token, str) or not 16 <= len(token) <= _MAX_TOKEN
        or not token.isascii() or not token.isprintable()
        or any(char.isspace() for char in token) or any(char in token for char in "'\"\\;")
    ):
        raise RecoveryCredentialsUnavailable("Saved lobby token format is invalid")
    return token


class RecoveryCredentials:
    def __init__(self, store: CredentialStore | None = None) -> None:
        self._store_override = store

    def _provider(self) -> CredentialStore:
        try:
            return _store(self._store_override)
        except SavedSessionUnavailable as exc:
            raise RecoveryCredentialsUnavailable("Protected credential store is unavailable") from exc

    def available(self, account: Account) -> bool:
        if not account.enabled:
            return False
        try:
            token = self._provider().get_password(_SERVICE, _account_key(account))
            if token is None:
                return False
            _validated_token(token)
            _email_binding(account, self._store_override)
            return True
        except (SavedSessionUnavailable, RecoveryCredentialsUnavailable):
            return False
        except Exception:  # noqa: BLE001 - sanitized boundary or independent recovery loop
            return False

    def retrieve(self, account: Account) -> tuple[str, str]:
        """Only call within the trusted worker-launch boundary; never log result."""
        if not account.enabled:
            raise RecoveryCredentialsUnavailable("Account is disabled")
        try:
            store = self._provider()
            email = _email_binding(account, self._store_override)
            token = store.get_password(_SERVICE, _account_key(account))
            return email, _validated_token(token)
        except (SavedSessionUnavailable, RecoveryCredentialsUnavailable) as exc:
            raise RecoveryCredentialsUnavailable("Protected lobby credential unavailable") from exc
        except Exception as exc:
            raise RecoveryCredentialsUnavailable("Unable to access protected lobby credential") from exc

    def import_saved(self, account: Account, *, confirmed: bool) -> bool:
        """One explicit server-local migration from IkaBot's existing saved-user file.

        Does not print/read back token values to a client, and never imports
        if the file fails exact mailbox and world/player identity checks.
        """
        if confirmed is not True or not account.enabled:
            raise RecoveryCredentialsUnavailable("Explicit local saved-login consent required")
        try:
            from ikabot.helpers.sessionStorage import (
                find_user_file_for_email,
                get_saved_users,
                read_json_file,
            )
            provider = self._provider()
            matched = _WORLD.fullmatch(account.world)
            if matched is None:
                raise RecoveryCredentialsUnavailable("Unsupported account world format")

            def checked_file(email: str) -> dict | None:
                path, ambiguous = find_user_file_for_email(email)
                if not path or ambiguous:
                    return None
                data = read_json_file(path, {})
                if (
                    not isinstance(data, dict)
                    or not isinstance(data.get("email"), str)
                    or data["email"].casefold() != email.casefold()
                ):
                    return None
                players = data.get("players")
                if not isinstance(players, dict):
                    return None
                selected = players.get(account.player)
                if not isinstance(selected, dict):
                    return None
                world_record = selected.get(matched.group(1))
                if not isinstance(world_record, dict):
                    return None
                if matched.group(2) not in world_record:
                    return None
                return data

            # If an exact private email binding already exists, NEVER silently
            # change it. Otherwise find exactly one saved IkaBot identity whose
            # player/world is the configured account, and bind it securely.
            newly_bound = False
            try:
                email = _email_binding(account, self._store_override)
                data = checked_file(email)
                if data is None:
                    raise RecoveryCredentialsUnavailable("Protected email does not match saved player/world")
            except SavedSessionUnavailable:
                candidates = []
                for saved_email in get_saved_users():
                    if not isinstance(saved_email, str):
                        continue
                    data = checked_file(saved_email)
                    if data is not None:
                        candidates.append((saved_email, data))
                if len(candidates) != 1:
                    raise RecoveryCredentialsUnavailable(
                        "Exact saved account could not be resolved unambiguously"
                    )
                email, data = candidates[0]
                newly_bound = True

            shared = data.get("shared", {})
            if not isinstance(shared, dict):
                raise RecoveryCredentialsUnavailable("Saved lobby state is unavailable")
            lobby = shared.get("lobby", {})
            if not isinstance(lobby, dict):
                raise RecoveryCredentialsUnavailable("No saved Gameforge lobby token")
            token = _validated_token(lobby.get("gf-token-production"))
            if newly_bound:
                bind_saved_email(account, email, credential_store=self._store_override)
            try:
                provider.set_password(_SERVICE, _account_key(account), token)
            except Exception:
                if newly_bound:
                    unbind_saved_email(account, credential_store=self._store_override)
                raise
            return True
        except RecoveryCredentialsUnavailable:
            raise
        except Exception as exc:
            raise RecoveryCredentialsUnavailable("Saved lobby credential import failed safely") from exc

    def forget(self, account: Account, *, confirmed: bool) -> None:
        if confirmed is not True:
            raise RecoveryCredentialsUnavailable("Explicit credential removal approval required")
        try:
            self._provider().delete_password(_SERVICE, _account_key(account))
        except Exception as exc:
            raise RecoveryCredentialsUnavailable("Unable to remove protected lobby credential") from exc
