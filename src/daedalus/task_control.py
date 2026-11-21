"""Opt-in, session-scoped task controller with durable retry suppression.

No login is possible here. The worker must already hold an authenticated
engine session, verified over protected IPC. Every start requires explicit
confirmation and a caller-generated idempotency key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import UUID

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    OwnedAccountSession,
    SessionPhase,
)
from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineTaskRejected
from daedalus.engine_registry import inspect_engine

_REQUEST_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_SECRET_WORDS = frozenset({
    "password", "token", "cookie", "authkey", "secret", "gf_token",
    "gameforge_token", "email", "session",
})


class TaskUnavailable(RuntimeError):
    """The task cannot run safely through the currently attached engine."""


class TaskRejected(TaskUnavailable):
    """Game task was provably not launched; retry only with new user approval."""

    def __init__(self, reason: str) -> None:
        if reason != "invalid_configuration":
            raise ValueError("Unknown deterministic rejection")
        self.reason = reason
        super().__init__("Invalid automation parameters. Review the fields and try again.")


class TaskPrerequisiteMissing(TaskUnavailable):
    """A known, deterministic nonsecret prerequisite failed before dispatch."""

    def __init__(self, reason: str) -> None:
        if reason != "notifications_required":
            raise ValueError("Unknown task prerequisite")
        self.reason = reason
        super().__init__("Configure Telegram or Discord notifications before starting this alert")


class TaskConflict(RuntimeError):
    """A duplicate request ID was reused with different task contents."""


def default_task_ledger_path() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    elif os.environ.get("XDG_STATE_HOME"):
        base = Path(os.environ["XDG_STATE_HOME"])
    else:
        base = Path.home() / ".local" / "state"
    return base / "daedalus" / "task-requests.sqlite3"


def validated_configuration(config: object) -> tuple[dict[str, Any], str]:
    """Validate a small, structured, secret-free engine task configuration."""
    if not isinstance(config, dict):
        raise TypeError("Task configuration must be a JSON object")

    def walk(item: Any, depth: int) -> None:
        if depth > 8:
            raise ValueError("Task configuration is nested too deeply")
        if isinstance(item, dict):
            for key, value in item.items():
                if not isinstance(key, str) or not key or len(key) > 100:
                    raise ValueError("Task config keys must be short strings")
                normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
                if any(word in normalized for word in _SECRET_WORDS):
                    raise ValueError("Authentication data is not permitted in task configuration")
                walk(value, depth + 1)
        elif isinstance(item, list):
            if len(item) > 200:
                raise ValueError("Task configuration contains too many list entries")
            for value in item:
                walk(value, depth + 1)
        elif item is None or type(item) in (str, bool, int, float):
            if isinstance(item, str) and len(item) > 2000:
                raise ValueError("Task configuration string is too long")
        else:
            raise ValueError("Unsupported value type in task configuration")

    walk(config, 0)
    try:
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Task configuration must contain finite JSON values") from exc
    if len(canonical.encode("utf-8")) > 16 * 1024:
        raise ValueError("Task configuration exceeds 16 KB")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return config, digest


class TaskLedger:
    """No config contents or game credentials are saved, only task metadata."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path is not None else default_task_ledger_path()
        self._mutex = threading.RLock()

    def _database(self) -> sqlite3.Connection:
        base = self.path.parent
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        if base.is_symlink() or self.path.is_symlink():
            raise TaskUnavailable("Task state must not be a symlink")
        if os.name != "nt":
            os.chmod(base, 0o700)
        conn = sqlite3.connect(self.path, timeout=8, isolation_level=None)
        if os.name != "nt":
            os.chmod(self.path, 0o600)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                account_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                task TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                engine_task_id TEXT,
                pid INTEGER,
                PRIMARY KEY(account_id, request_id)
            )
        """)
        return conn

    def reserve(self, account_id: str, request_id: str, task: str, digest: str) -> tuple[bool, dict[str, object]]:
        with self._mutex, closing(self._database()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT task, payload_hash, status, engine_task_id, pid FROM requests "
                "WHERE account_id = ? AND request_id = ?",
                (account_id, request_id),
            ).fetchone()
            if prior is not None:
                if prior[0] != task or prior[1] != digest:
                    raise TaskConflict("Request ID already refers to a different task")
                return False, {"account_id": account_id, "request_id": request_id,
                               "task": prior[0], "status": prior[2],
                               "task_id": prior[3], "pid": prior[4]}
            conn.execute(
                "INSERT INTO requests (account_id, request_id, task, payload_hash, status) "
                "VALUES (?, ?, ?, ?, 'dispatching')",
                (account_id, request_id, task, digest),
            )
            return True, {"account_id": account_id, "request_id": request_id,
                          "task": task, "status": "dispatching", "task_id": None, "pid": None}

    def existing(self, account_id: str, request_id: str, task: str,
                 digest: str) -> dict[str, object] | None:
        """Return the original result before new preflight; never replay it."""
        with self._mutex, closing(self._database()) as conn:
            prior = conn.execute(
                "SELECT task, payload_hash, status, engine_task_id, pid FROM requests "
                "WHERE account_id = ? AND request_id = ?", (account_id, request_id),
            ).fetchone()
        if prior is None:
            return None
        if prior[0] != task or prior[1] != digest:
            raise TaskConflict("Request ID already refers to a different task")
        return {"account_id": account_id, "request_id": request_id,
                "task": task, "status": prior[2], "task_id": prior[3], "pid": prior[4]}

    def has_unresolved(self, account_id: str) -> bool:
        """Nonsecret read-only check that never reserves a dispatch."""
        with self._mutex, closing(self._database()) as conn:
            row = conn.execute(
                "SELECT 1 FROM requests WHERE account_id = ? "
                "AND status IN ('dispatching', 'unconfirmed') LIMIT 1", (account_id,),
            ).fetchone()
        return row is not None

    def unresolved_except(self, account_id: str, request_id: str) -> bool:
        with self._mutex, closing(self._database()) as conn:
            row = conn.execute(
                "SELECT 1 FROM requests WHERE account_id = ? AND request_id != ? "
                "AND status IN ('dispatching', 'unconfirmed') LIMIT 1",
                (account_id, request_id),
            ).fetchone()
        return row is not None

    def acknowledge(self, account_id: str, request_id: str) -> None:
        with self._mutex, closing(self._database()) as conn, conn:
            updated = conn.execute(
                "UPDATE requests SET status = 'operator_reconciled' "
                "WHERE account_id = ? AND request_id = ? "
                "AND status IN ('dispatching', 'unconfirmed')",
                (account_id, request_id),
            ).rowcount
            if updated != 1:
                raise ValueError("No unresolved task request matches this ID")

    def finish(
        self, account_id: str, request_id: str, *, status: str,
        task_id: str | None = None, pid: int | None = None,
    ) -> None:
        with self._mutex, closing(self._database()) as conn, conn:
            conn.execute(
                "UPDATE requests SET status = ?, engine_task_id = ?, pid = ? "
                "WHERE account_id = ? AND request_id = ?",
                (status, task_id, pid, account_id, request_id),
            )

    def entries(self, account_id: str) -> list[dict[str, object]]:
        with self._mutex, closing(self._database()) as conn, conn:
            rows = conn.execute(
                "SELECT request_id, task, status, engine_task_id, pid FROM requests "
                "WHERE account_id = ? ORDER BY rowid DESC LIMIT 100",
                (account_id,),
            ).fetchall()
        return [
            {"account_id": account_id, "request_id": row[0], "task": row[1],
             "status": row[2], "task_id": row[3], "pid": row[4]}
            for row in rows
        ]


class TaskController:
    """One local owner per account with conservative, nonreplaying task dispatch."""

    def __init__(
        self,
        accounts: Sequence[Account],
        coordinator: AccountSessionCoordinator,
        ipc_client: ControlledIPCClient,
        *,
        ledger_path: str | Path | None = None,
        active_validation: bool = False,
        recovery_store: Any | None = None,
    ) -> None:
        self._active_validation = active_validation
        self._recovery_store = recovery_store
        self._accounts = {a.id: a for a in accounts}
        if not coordinator.matches_accounts(accounts):
            raise ValueError("Account coordinator and task controller must use identical accounts")
        self._coordinator = coordinator
        self._ipc = ipc_client
        self._ledger = TaskLedger(ledger_path)
        self._owned: dict[str, OwnedAccountSession] = {}
        self._mutex = threading.RLock()
        self._supported = {
            capability.name for capability in inspect_engine()
            if capability.kind == "background_task"
        }

    def _account(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account is None:
            raise KeyError("Account not found")
        if not account.enabled:
            raise TaskUnavailable("Account is disabled")
        return account

    def _is_validated(self, account: Account) -> bool:
        if self._active_validation:
            # Requires the extended Daedalus IPC action: an actual read-only
            # game world GET with no loginLink or session restoration.
            return self._ipc.validate_account(account)
        return self._ipc.has_account(account)

    def _lease(self, account: Account) -> tuple[OwnedAccountSession, bool]:
        owned = self._owned.get(account.id)
        if owned is not None:
            if owned.phase is not SessionPhase.AUTHENTICATED:
                raise TaskUnavailable("Account needs explicit session recovery")
            if self._active_validation and not self._is_validated(account):
                owned.transition(SessionPhase.NEEDS_ASSISTANCE)
                raise TaskUnavailable("Existing game session requires assistance")
            return owned, False
        owned = self._coordinator.acquire(account.id)
        try:
            if not self._is_validated(account):
                raise TaskUnavailable("No verified already-authenticated IkaBot session")
            owned.transition(SessionPhase.AUTHENTICATED)
            self._owned[account.id] = owned
            return owned, True
        except BaseException:
            owned.close()
            raise

    def adopt_verified_saved_worker(
        self, account_id: str, lease: OwnedAccountSession,
    ) -> None:
        """Share the same lease held by an explicitly restored local worker.

        Never treat an arbitrary lease or an IPC identity claim as evidence
        of ownership. The same in-process coordinator must own the exact
        authenticated account and the protected IPC must confirm the worker.
        """
        with self._mutex:
            account = self._account(account_id)
            if (
                lease.account != account
                or lease._coordinator is not self._coordinator
                or self._coordinator._active.get(account_id) is not lease
                or lease.phase is not SessionPhase.AUTHENTICATED
                or account_id in self._owned
            ):
                raise TaskUnavailable("Worker lease is not a verified local account owner")
            if not self._is_validated(account):
                raise TaskUnavailable("Restored session does not match protected engine IPC")
            self._owned[account_id] = lease

    def observe_existing(self, account_id: str, *, confirmed: bool) -> dict[str, str]:
        """Explicitly attach to a verified existing worker; never create a login."""
        if confirmed is not True:
            raise ValueError("Explicit monitoring confirmation is required")
        account = self._account(account_id)
        with self._mutex:
            owned = self._owned.get(account.id)
            if owned is not None and owned.phase is SessionPhase.PAUSED:
                if not self._is_validated(account):
                    raise TaskUnavailable("Existing session has not been revalidated")
                owned.transition(SessionPhase.VALIDATING_SESSION)
                owned.transition(SessionPhase.AUTHENTICATED)
            else:
                self._lease(account)
            return {"account_id": account.id, "status": "monitoring_existing_session"}

    def owned_sessions(self) -> tuple[OwnedAccountSession, ...]:
        """Immutable snapshot for the opt-in trusted monitor; no IPC request."""
        with self._mutex:
            return tuple(self._owned.values())

    def preflight(self, account_id: str, task: str) -> dict[str, object]:
        """Never reserve a dispatch; return only checked prerequisites."""
        if task not in self._supported:
            raise ValueError("Unsupported engine task")
        account = self._account(account_id)
        result = self._ipc.preflight_task(account, task)
        return {"account_id": account_id, **result,
                "unresolved_request": self._ledger.has_unresolved(account_id)}

    def start(
        self, account_id: str, task: str, config: object,
        request_id: str, *, confirmed: bool, track_desired: bool = True,
    ) -> dict[str, object]:
        if not confirmed:
            raise ValueError("Explicit game task confirmation is required")
        if (
            not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id)
            or UUID(request_id).version != 4
        ):
            raise ValueError("A valid UUID request_id is required for idempotency")
        if task not in self._supported:
            raise ValueError("Unsupported engine task")
        clean, _ = validated_configuration(config)
        clean = dict(clean)
        is_fixed = False
        if task == "sendResources" and self._recovery_store is not None:
            from daedalus.recovery_reconcile import canonical_fixed_transfer
            if track_desired:
                if "transfer_id" in clean:
                    raise ValueError("Fixed transfer journal key is server-owned")
                if canonical_fixed_transfer(clean) is not None:
                    clean["transfer_id"] = request_id
                    is_fixed = True
            else:
                is_fixed = "transfer_id" in clean
        clean, digest = validated_configuration(clean)
        account = self._account(account_id)
        with self._mutex:
            if self._ledger.unresolved_except(account.id, request_id):
                raise TaskUnavailable("An earlier task dispatch is unresolved; reconcile before restarting")
            existing = self._ledger.existing(account.id, request_id, task, digest)
            if existing is not None:
                return existing
            # Preflight happens BEFORE durable dispatch reservation. A known
            # prerequisite failure is not an uncertain in-game launch.
            # Unknown/unavailable preflight also refuses dispatch, fail closed.
            prereq = self._ipc.preflight_task(account, task)
            if not prereq["ready"]:
                raise TaskPrerequisiteMissing(prereq["reason"])
            if is_fixed and track_desired:
                # Record the immutable original intent before engine dispatch.
                try:
                    self._recovery_store.prepare_fixed_transfer(account, clean)
                except (ValueError, OSError, sqlite3.Error) as exc:
                    raise TaskUnavailable("Unable to persist fixed transfer intent") from exc
            fresh, receipt = self._ledger.reserve(account.id, request_id, task, digest)
            if not fresh:
                # Never dispatch again after an ambiguous failure or controller restart.
                return receipt
            try:
                self._lease(account)
                started = self._ipc.start_managed_task(account, task, clean, request_id)
            except EngineTaskRejected as exc:
                # This specific typed IPC reply proves there was no process
                # start. Do not block a corrected future request.
                self._ledger.finish(account.id, request_id, status="rejected")
                if is_fixed and track_desired:
                    self._recovery_store.finish_fixed_transfer(
                        account, request_id, status="rejected",
                    )
                if exc.reason == "notifications_required":
                    raise TaskPrerequisiteMissing(exc.reason) from exc
                raise TaskRejected(exc.reason) from exc
            except BaseException:
                # Unknown IPC results could have started a real game operation.
                self._ledger.finish(account.id, request_id, status="unconfirmed")
                if is_fixed and track_desired:
                    self._recovery_store.finish_fixed_transfer(
                        account, request_id, status="unconfirmed",
                    )
                raise
            self._ledger.finish(
                account.id, request_id, status="started",
                task_id=str(started["task_id"]), pid=int(started["pid"]),
            )
            receipt = {"account_id": account.id, "request_id": request_id,
                       "task": task, "status": "started",
                       "task_id": started["task_id"], "pid": started["pid"]}
            if track_desired and self._recovery_store is not None:
                try:
                    if is_fixed:
                        self._recovery_store.finish_fixed_transfer(
                            account, request_id, status="started",
                            task_id=str(started["task_id"]),
                        )
                        receipt["desired_job_id"] = request_id
                    else:
                        receipt["desired_job_id"] = self._recovery_store.capture_started(
                            account, task, clean, str(started["task_id"]),
                        )
                except (OSError, ValueError, sqlite3.Error):
                    # The task did start; losing its optional recovery journal
                    # must never misreport the engine dispatch as unconfirmed.
                    receipt["recovery_tracking"] = "unavailable"
            return receipt

    def list_tasks(self, account_id: str) -> dict[str, object]:
        account = self._account(account_id)
        # Read can discover an already-running task after a backend restart.
        return {"account_id": account.id,
                "engine_tasks": self._ipc.list_managed_tasks(account),
                "requests": self._ledger.entries(account.id)}

    def stop(self, account_id: str, task_id: str) -> dict[str, object]:
        account = self._account(account_id)
        with self._mutex:
            # User's stop intention wins even during a rotation grace period:
            # never restart this task later if the IPC stop was interrupted.
            if self._recovery_store is not None:
                try:
                    self._recovery_store.stop_task(account, task_id)
                except (OSError, ValueError, sqlite3.Error) as exc:
                    raise TaskUnavailable("Unable to persist desired task stop") from exc
            self._lease(account)
            result = self._ipc.stop_managed_task(account, task_id)
            return {"account_id": account.id, **result}

    def acknowledge_uncertain_request(
        self, account_id: str, request_id: str, *, confirmed: bool,
    ) -> dict[str, str]:
        """User asserts they inspected engine/game state; no automatic redispatch."""
        if not confirmed:
            raise ValueError("Explicit manual reconciliation confirmation required")
        if (
            not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id)
            or UUID(request_id).version != 4
        ):
            raise ValueError("A valid request ID is required")
        account = self._account(account_id)
        self._ledger.acknowledge(account.id, request_id)
        return {"account_id": account.id, "request_id": request_id,
                "status": "operator_reconciled"}

    def close(self) -> None:
        """Release controller leases on shutdown (engine task state persists separately)."""
        with self._mutex:
            for owned in self._owned.values():
                owned.close()
            self._owned.clear()
