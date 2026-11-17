"""Account-scoped, cross-process local leases and explicit authentication states.

This module never performs a Gameforge login, starts an engine worker, stores
credentials, or sends game requests. Workers will adopt these leases later.

File locks are intentionally *host-local*: a single authoritative backend is
required per account. Remote desktops are clients, not competing game workers.
"""

from __future__ import annotations

import hashlib
import os
import threading
import unicodedata
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Self

from filelock import FileLock, Timeout

from daedalus.accounts import Account


class SessionBusyError(RuntimeError):
    """Another worker currently holds the local account/world/player lease."""


class SessionDisabledError(RuntimeError):
    """An operator has disabled this account in local configuration."""


class SessionTransitionError(ValueError):
    """An authentication state transition is not permitted."""


class SessionPhase(str, Enum):
    VALIDATING_SESSION = "validating_session"
    AUTHENTICATED = "authenticated"
    NEEDS_ASSISTANCE = "needs_assistance"
    ASSISTED_LOGIN = "assisted_login"
    VALIDATING_HANDOFF = "validating_handoff"
    PAUSED = "paused"
    FAILED = "failed"
    CLOSED = "closed"


_ALLOWED_TRANSITIONS = {
    SessionPhase.VALIDATING_SESSION: frozenset(
        {
            SessionPhase.AUTHENTICATED,
            SessionPhase.NEEDS_ASSISTANCE,
            SessionPhase.PAUSED,
            SessionPhase.FAILED,
        }
    ),
    SessionPhase.AUTHENTICATED: frozenset(
        {SessionPhase.NEEDS_ASSISTANCE, SessionPhase.PAUSED, SessionPhase.FAILED}
    ),
    SessionPhase.NEEDS_ASSISTANCE: frozenset(
        {SessionPhase.ASSISTED_LOGIN, SessionPhase.PAUSED, SessionPhase.FAILED}
    ),
    SessionPhase.ASSISTED_LOGIN: frozenset(
        {
            SessionPhase.VALIDATING_HANDOFF,
            SessionPhase.NEEDS_ASSISTANCE,
            SessionPhase.PAUSED,
            SessionPhase.FAILED,
        }
    ),
    SessionPhase.VALIDATING_HANDOFF: frozenset(
        {SessionPhase.AUTHENTICATED, SessionPhase.NEEDS_ASSISTANCE, SessionPhase.FAILED}
    ),
    SessionPhase.PAUSED: frozenset(
        {SessionPhase.VALIDATING_SESSION, SessionPhase.NEEDS_ASSISTANCE, SessionPhase.FAILED}
    ),
    SessionPhase.FAILED: frozenset({SessionPhase.VALIDATING_SESSION}),
}


def default_session_state_dir() -> Path:
    """Return a writable user-owned state path, never the project checkout."""
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        parent = Path(os.environ["LOCALAPPDATA"])
    elif os.environ.get("XDG_STATE_HOME"):
        parent = Path(os.environ["XDG_STATE_HOME"])
    else:
        parent = Path.home() / ".local" / "state"
    return parent.expanduser() / "daedalus" / "session-locks"


def _identity_key(account: Account) -> str:
    # Account ID is intentionally omitted: two local profiles for the same
    # in-game world/player must not obtain independent leases.
    world = unicodedata.normalize("NFC", account.world).casefold()
    player = unicodedata.normalize("NFC", account.player).casefold()
    return hashlib.sha256((world + "\0" + player).encode("utf-8")).hexdigest()


class OwnedAccountSession:
    """Holds an OS-backed lease until explicitly closed, including CAPTCHA wait."""

    def __init__(
        self,
        account: Account,
        file_lock: FileLock,
        coordinator: AccountSessionCoordinator,
    ) -> None:
        self.account = account
        self._file_lock = file_lock
        self._coordinator = coordinator
        self._phase = SessionPhase.VALIDATING_SESSION
        self._closed = False

    @property
    def phase(self) -> SessionPhase:
        with self._coordinator._mutex:
            return self._phase

    def transition(self, next_phase: SessionPhase) -> None:
        """Validate a state change; successful login must be confirmed externally."""
        if not isinstance(next_phase, SessionPhase):
            raise SessionTransitionError("Expected a SessionPhase value")
        with self._coordinator._mutex:
            if self._closed:
                raise SessionTransitionError("Cannot transition a closed account session")
            if next_phase not in _ALLOWED_TRANSITIONS.get(self._phase, frozenset()):
                raise SessionTransitionError(
                    f"Cannot change session state from {self._phase.value} to {next_phase.value}"
                )
            self._phase = next_phase

    def close(self) -> None:
        """Release the lease; calling close repeatedly is safe."""
        with self._coordinator._mutex:
            if self._closed:
                return
            self._closed = True
            self._phase = SessionPhase.CLOSED
            try:
                self._file_lock.release()
            finally:
                if self._coordinator._active.get(self.account.id) is self:
                    del self._coordinator._active[self.account.id]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


class AccountSessionCoordinator:
    """Single host-local owner per account identity, safe across processes."""

    def __init__(
        self,
        accounts: Sequence[Account],
        *,
        state_dir: str | Path | None = None,
    ) -> None:
        by_id: dict[str, Account] = {}
        by_identity: set[str] = set()
        for account in accounts:
            if account.id in by_id:
                raise ValueError("Duplicate account id")
            identity = _identity_key(account)
            if identity in by_identity:
                raise ValueError("Duplicate world/player identity")
            by_id[account.id] = account
            by_identity.add(identity)
        self._accounts = by_id
        self._state_dir = (
            Path(state_dir).expanduser() if state_dir is not None else default_session_state_dir()
        )
        self._mutex = threading.RLock()
        self._active: dict[str, OwnedAccountSession] = {}

    def _ensure_private_directory(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self._state_dir.is_symlink() or not self._state_dir.is_dir():
            raise RuntimeError("Session lock directory must be a real directory")
        if os.name != "nt":
            # The directory contains only opaque SHA-256 lock names, no tokens.
            os.chmod(self._state_dir, 0o700)

    def acquire(self, account_id: str) -> OwnedAccountSession:
        """Claim an account. This does not attempt to authenticate to the game."""
        with self._mutex:
            account = self._accounts.get(account_id)
            if account is None:
                raise KeyError("Unknown account")
            if not account.enabled:
                raise SessionDisabledError("This account is disabled")
            if account_id in self._active:
                raise SessionBusyError("This account already has a session owner")
            self._ensure_private_directory()
            lock_path = self._state_dir / f"{_identity_key(account)}.lock"
            file_lock = FileLock(str(lock_path))
            try:
                file_lock.acquire(timeout=0)
            except Timeout as exc:
                raise SessionBusyError(
                    "This account already has a session owner on this host"
                ) from exc
            if os.name != "nt":
                os.chmod(lock_path, 0o600)
            try:
                owned = OwnedAccountSession(account, file_lock, self)
                self._active[account_id] = owned
                return owned
            except BaseException:
                file_lock.release()
                raise

    def status(self, account_id: str) -> str:
        """Read-only, nonsecret state for an account status dashboard."""
        with self._mutex:
            account = self._accounts.get(account_id)
            if account is None:
                raise KeyError("Unknown account")
            if not account.enabled:
                return "disabled"
            owned = self._active.get(account_id)
            return owned.phase.value if owned is not None else "not_connected"

    def matches_accounts(self, accounts: Sequence[Account]) -> bool:
        """Refuse to attach a status coordinator configured for different identities."""
        incoming = {account.id: account for account in accounts}
        return len(incoming) == len(accounts) and incoming == self._accounts

    @property
    def account_ids(self) -> frozenset[str]:
        return frozenset(self._accounts)
