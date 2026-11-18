"""Opt-in existing-session health and human-assistance reconciliation.

The monitor never launches IkaBot, restores credentials, starts tasks or
automatically replays task requests. Its active validation uses only the
restricted existing-session IPC action and a read-only world GET.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

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
