"""Opt-in existing-session health and human-assistance reconciliation.

The monitor never launches IkaBot, restores credentials, starts tasks or
automatically replays task requests. Its active validation uses only the
restricted existing-session IPC action and a read-only world GET.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from uuid import UUID

from daedalus.account_sessions import SessionPhase
from daedalus.auth_assistance import (
    AssistanceBroker,
    AssistanceConflict,
    AssistanceReason,
    AssistanceState,
)
from daedalus.engine_ipc import EngineIPCUnavailable
from daedalus.task_control import TaskController, TaskUnavailable

logger = logging.getLogger("daedalus.session_monitor")


class MonitoringUnavailable(RuntimeError):
    """The observed session cannot be monitored safely."""


@dataclass(frozen=True)
class MonitorStatus:
    account_id: str
    phase: str

    def to_dict(self) -> dict[str, str]:
        return {"account_id": self.account_id, "session_status": self.phase}


class ExistingSessionRecoveryMonitor:
    """Tracks exact previously attached IkaBot engine sessions under leases.

    A remote GUI can acknowledge a manual step; only this trusted monitor
    validates the actual world page through IPC before the owner transitions.
    """

    def __init__(
        self,
        controller: TaskController,
        broker: AssistanceBroker,
        *,
        interval_seconds: int = 300,
    ) -> None:
        if not isinstance(interval_seconds, int) or not 15 <= interval_seconds <= 3600:
            raise ValueError("Monitoring interval must be between 15 and 3600 seconds")
        if broker.coordinator is not controller._coordinator:
            raise ValueError("Monitor and assistance broker must share one account owner")
        if not controller._active_validation:
            raise ValueError("Monitoring requires active, read-only session validation")
        self.controller = controller
        self.broker = broker
        self.interval_seconds = interval_seconds
        self._halt = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._consumed_recovery_tickets: set[str] = set()

    def observe(self, account_id: str, *, confirmed: bool) -> dict[str, str]:
        """Operator-confirmed lease attachment; never a new Gameforge login."""
        try:
            return self.controller.observe_existing(account_id, confirmed=confirmed)
        except (EngineIPCUnavailable, TaskUnavailable) as exc:
            raise MonitoringUnavailable(
                "A compatible verified existing IkaBot session is required"
            ) from exc

    def _session_valid(self, account) -> bool:
        # ExistingIPCClient performs a fixed allowlisted game page probe. It
        # rejects responses from another account and does not restore sessions.
        try:
            return self.controller._ipc.validate_account(account)
        except (EngineIPCUnavailable, ValueError, OSError):
            return False

    def poll_once(self) -> list[MonitorStatus]:
        """One bounded validation cycle. Never resumes a task on its own."""
        statuses = []
        with self._lock, self.controller._mutex:
            for owned in self.controller.owned_sessions():
                account = owned.account
                phase = owned.phase
                try:
                    if phase is SessionPhase.AUTHENTICATED:
                        # A genuine negative validation may indicate rotation
                        # or expiration. Prompt for a human, holding the lease.
                        if not self._session_valid(account):
                            self.broker.request(owned, AssistanceReason.SESSION_EXPIRED)
                    elif phase is SessionPhase.ASSISTED_LOGIN:
                        ticket = self.broker.snapshot(account.id)["ticket"]
                        if ticket is not None and ticket["state"] == AssistanceState.READY.value:
                            self.broker.begin_validation(owned, ticket["ticket_id"])
                            valid = self._session_valid(account)
                            self.broker.complete_validation(
                                owned, ticket["ticket_id"], valid=valid,
                            )
                    elif phase is SessionPhase.NEEDS_ASSISTANCE:
                        ticket = self.broker.snapshot(account.id)["ticket"]
                        if owned.phase is SessionPhase.NEEDS_ASSISTANCE and (
                            ticket is None or ticket["state"] == AssistanceState.RETRY.value
                        ):
                            self.broker.request(owned, AssistanceReason.SESSION_EXPIRED)
                    # PAUSED/FAILED/VALIDATING_HANDOFF remain blocked until
                    # explicit verification or recovery, never automatic login.
                except AssistanceConflict:
                    logger.warning("Assistance state changed during monitored session")
                except (TaskUnavailable, EngineIPCUnavailable, ValueError):
                    logger.warning("Monitored engine session is unavailable")
                statuses.append(MonitorStatus(account.id, owned.phase.value))
        return statuses

    def resume_verified_task(
        self,
        account_id: str,
        ticket_id: str,
        task: str,
        config: object,
        request_id: str,
        *,
        confirmed: bool,
    ) -> dict[str, object]:
        """One explicitly approved NEW dispatch after trusted worker validation.

        Never replays an old task or its configuration. The recovery ticket is
        consumed before IPC dispatch because a lost response is ambiguous.
        The task ledger separately rejects duplicate request IDs and uncertain
        older dispatches. No HTTP endpoint exposes this internal owner gate.
        """
        if confirmed is not True:
            raise MonitoringUnavailable("Explicit post-recovery task approval is required")
        with self._lock, self.controller._mutex:
            owned = next(
                (session for session in self.controller.owned_sessions()
                 if session.account.id == account_id), None,
            )
            ticket = self.broker.snapshot(account_id)["ticket"]
            if (
                owned is None
                or owned.phase is not SessionPhase.AUTHENTICATED
                or not isinstance(ticket, dict)
                or ticket.get("ticket_id") != ticket_id
                or ticket.get("state") != AssistanceState.VERIFIED.value
                or ticket_id in self._consumed_recovery_tickets
            ):
                raise MonitoringUnavailable("A fresh worker-verified recovery is required")
            if not self._session_valid(owned.account):
                raise MonitoringUnavailable("The recovered game session is no longer valid")
            if self.controller._ledger.unresolved_except(account_id, request_id):
                raise MonitoringUnavailable("Uncertain earlier dispatch requires reconciliation")
            # Reject malformed or unsupported requests before burning the
            # single-use recovery approval. The controller repeats validation.
            from daedalus.task_control import validated_configuration

            if (
                not isinstance(request_id, str)
                or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", request_id)
                or UUID(request_id).version != 4
            ):
                raise ValueError("A fresh UUIDv4 request ID is required")
            if task not in self.controller._supported:
                raise ValueError("Unsupported engine task")
            validated_configuration(config)
            # Once dispatch begins, an IPC timeout cannot establish whether
            # the game accepted it. Never retry this recovery ticket.
            self._consumed_recovery_tickets.add(ticket_id)
            return self.controller.start(
                account_id, task, config, request_id, confirmed=True,
            )

    def pending(self) -> dict[str, object]:
        """Only nonsecret waiting requests, for desktop notifications."""
        results: list[dict[str, str]] = []
        with self._lock:
            for owned in self.controller.owned_sessions():
                snapshot = self.broker.snapshot(owned.account.id)
                ticket = snapshot["ticket"]
                if (
                    isinstance(ticket, dict)
                    and ticket.get("state") == AssistanceState.WAITING.value
                ):
                    results.append({
                        "account_id": owned.account.id,
                        "ticket_id": ticket["ticket_id"],
                        "reason": ticket["reason"],
                        "state": ticket["state"],
                    })
        return {"enabled": True, "tickets": results}

    def start(self) -> None:
        """Start polling only after the operator chose monitoring at startup."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._halt.clear()
            self._thread = threading.Thread(
                target=self._loop,
                daemon=True,
                name="daedalus-existing-session-monitor",
            )
            self._thread.start()

    def _loop(self) -> None:
        while not self._halt.wait(self.interval_seconds):
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 - must never kill the API due to a game worker
                logger.warning("Existing-session monitor cycle was incomplete")

    def stop(self) -> None:
        with self._lock:
            self._halt.set()
            worker = self._thread
            self._thread = None
        if worker is not None:
            worker.join(timeout=12.0)
