"""Credential-free human assistance handshake for a trusted session owner.

The desktop can acknowledge *human completion*, never authentication success.
Only an in-process trusted worker holding the account lease may create and
validate a request. No browser, login, cookie or Gameforge networking lives here.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    OwnedAccountSession,
    SessionPhase,
)


class AssistanceConflict(RuntimeError):
    """The request is stale, owned by another session or in the wrong phase."""


class AssistanceReason(str, Enum):
    SESSION_EXPIRED = "session_expired"
    LOGIN_REQUIRED = "login_required"
    MANUAL_CHALLENGE = "manual_challenge"


class AssistanceState(str, Enum):
    WAITING = "waiting_operator"
    READY = "operator_ready"
    VALIDATING = "validating_session"
    VERIFIED = "verified_by_worker"
    RETRY = "retry_required"
    EXPIRED = "expired"


@dataclass
class _Ticket:
    account_id: str
    ticket_id: str
    reason: AssistanceReason
    state: AssistanceState
    deadline: float
    owner: OwnedAccountSession

    def public(self) -> dict[str, str]:
        return {
            "ticket_id": self.ticket_id,
            "reason": self.reason.value,
            "state": self.state.value,
        }


class AssistanceBroker:
    """Owns nonsecret assistance tickets in the authoritative worker process.

    Tickets deliberately do not survive restarts: a new owner must explicitly
    validate/reconcile the engine session, never replay a browser handoff.
    """

    def __init__(
        self,
        coordinator: AccountSessionCoordinator,
        *,
        ttl_seconds: int = 900,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(ttl_seconds, int) or not 30 <= ttl_seconds <= 3600:
            raise ValueError("Assistance TTL must be between 30 and 3600 seconds")
        self.coordinator = coordinator
        self._clock = clock
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._tickets: dict[str, _Ticket] = {}

    def _require_owner(self, account_id: str, owner: OwnedAccountSession) -> None:
        with self.coordinator._mutex:
            if (
                owner.account.id != account_id
                or owner._closed
                or self.coordinator._active.get(account_id) is not owner
            ):
                raise AssistanceConflict("The account worker does not own this session")

    def _expire(self, ticket: _Ticket) -> None:
        if (
            ticket.state in {AssistanceState.WAITING, AssistanceState.READY}
            and self._clock() >= ticket.deadline
        ):
                ticket.state = AssistanceState.EXPIRED
                self._require_owner(ticket.account_id, ticket.owner)
                # Expiration keeps the lease in place; a trusted supervisor must
                # explicitly decide whether and when the worker may stop.
                if ticket.owner.phase in {
                    SessionPhase.NEEDS_ASSISTANCE,
                    SessionPhase.ASSISTED_LOGIN,
                }:
                    ticket.owner.transition(SessionPhase.PAUSED)

    def request(self, owner: OwnedAccountSession, reason: AssistanceReason) -> dict[str, str]:
        """Trusted worker only: request a human action under the held lease."""
        if not isinstance(reason, AssistanceReason):
            raise TypeError("Reason must be a fixed nonsecret assistance reason")
        account_id = owner.account.id
        with self._lock:
            self._require_owner(account_id, owner)
            prior = self._tickets.get(account_id)
            if prior is not None:
                self._expire(prior)
                if prior.state in {
                    AssistanceState.WAITING,
                    AssistanceState.READY,
                    AssistanceState.VALIDATING,
                }:
                    raise AssistanceConflict("Assistance already pending for this account")
            if owner.phase not in {
                SessionPhase.VALIDATING_SESSION,
                SessionPhase.AUTHENTICATED,
                SessionPhase.NEEDS_ASSISTANCE,
            }:
                raise AssistanceConflict("Worker must validate its session before requesting help")
            if owner.phase is not SessionPhase.NEEDS_ASSISTANCE:
                owner.transition(SessionPhase.NEEDS_ASSISTANCE)
            ticket = _Ticket(
                account_id, str(uuid.uuid4()), reason, AssistanceState.WAITING,
                self._clock() + self._ttl, owner,
            )
            self._tickets[account_id] = ticket
            return ticket.public()

    def snapshot(self, account_id: str) -> dict[str, object]:
        """Safe for bearer-authenticated GUI polling, no login secrets."""
        with self._lock:
            if account_id not in self.coordinator.account_ids:
                raise KeyError("Unknown account")
            ticket = self._tickets.get(account_id)
            if ticket is not None:
                self._expire(ticket)
            return {
                "enabled": True,
                "account_id": account_id,
                "ticket": ticket.public() if ticket is not None else None,
            }

    def approve(
        self, account_id: str, ticket_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        """Operator acknowledges completion, but cannot assert a valid login."""
        if confirmed is not True:
            raise ValueError("Explicit operator confirmation is required")
        try:
            uuid.UUID(ticket_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("Invalid assistance ticket") from exc
        with self._lock:
            ticket = self._tickets.get(account_id)
            if ticket is None or ticket.ticket_id != ticket_id:
                raise AssistanceConflict("Assistance request is no longer current")
            self._expire(ticket)
            self._require_owner(account_id, ticket.owner)
            if ticket.state is not AssistanceState.WAITING:
                raise AssistanceConflict("Assistance request is not waiting for approval")
            ticket.owner.transition(SessionPhase.ASSISTED_LOGIN)
            ticket.state = AssistanceState.READY
            return self.snapshot(account_id)

    def begin_validation(
        self, owner: OwnedAccountSession, ticket_id: str,
    ) -> dict[str, str]:
        """Trusted worker only: wait for user acknowledgment then validate."""
        account_id = owner.account.id
        with self._lock:
            self._require_owner(account_id, owner)
            ticket = self._tickets.get(account_id)
            if ticket is None or ticket.owner is not owner or ticket.ticket_id != ticket_id:
                raise AssistanceConflict("Assistance request has been replaced")
            self._expire(ticket)
            if ticket.state is not AssistanceState.READY:
                raise AssistanceConflict("Operator has not completed the manual step")
            owner.transition(SessionPhase.VALIDATING_HANDOFF)
            ticket.state = AssistanceState.VALIDATING
            return ticket.public()

    def complete_validation(
        self, owner: OwnedAccountSession, ticket_id: str, *, valid: bool,
    ) -> dict[str, str]:
        """Trusted worker assertion after actual session validation, never HTTP."""
        if type(valid) is not bool:
            raise TypeError("Validation outcome must be a boolean")
        account_id = owner.account.id
        with self._lock:
            self._require_owner(account_id, owner)
            ticket = self._tickets.get(account_id)
            if ticket is None or ticket.owner is not owner or ticket.ticket_id != ticket_id:
                raise AssistanceConflict("Assistance request has been replaced")
            if ticket.state is not AssistanceState.VALIDATING:
                raise AssistanceConflict("Assistance has not entered worker validation")
            owner.transition(
                SessionPhase.AUTHENTICATED if valid else SessionPhase.NEEDS_ASSISTANCE
            )
            ticket.state = AssistanceState.VERIFIED if valid else AssistanceState.RETRY
            return ticket.public()
