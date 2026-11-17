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

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    OwnedAccountSession,
    SessionPhase,
)
from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.engine_registry import inspect_engine

_REQUEST_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_SECRET_WORDS = frozenset({
    "password", "token", "cookie", "authkey", "secret", "gf_token",
    "gameforge_token", "email", "session",
})


class TaskUnavailable(RuntimeError):
    """The task cannot run safely through the currently attached engine."""


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
    ) -> None:
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

    def _lease(self, account: Account) -> tuple[OwnedAccountSession, bool]:
        owned = self._owned.get(account.id)
        if owned is not None:
            return owned, False
        owned = self._coordinator.acquire(account.id)
        try:
            if not self._ipc.has_account(account):
                raise TaskUnavailable("No already-authenticated IkaBot session for this account")
            owned.transition(SessionPhase.AUTHENTICATED)
            self._owned[account.id] = owned
            return owned, True
        except BaseException:
            owned.close()
            raise

    def start(
        self, account_id: str, task: str, config: object,
        request_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not confirmed:
            raise ValueError("Explicit game task confirmation is required")
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            raise ValueError("A valid UUID request_id is required for idempotency")
        if task not in self._supported:
            raise ValueError("Unsupported engine task")
        clean, digest = validated_configuration(config)
        account = self._account(account_id)
        with self._mutex:
            if self._ledger.unresolved_except(account.id, request_id):
                raise TaskUnavailable("An earlier task dispatch is unresolved; reconcile before restarting")
            fresh, receipt = self._ledger.reserve(account.id, request_id, task, digest)
            if not fresh:
                # Never dispatch again after an ambiguous failure or controller restart.
                return receipt
            try:
                self._lease(account)
                started = self._ipc.start_managed_task(account, task, clean)
            except BaseException:
                # Do not retry: the IPC reply may have been lost after game acceptance.
                self._ledger.finish(account.id, request_id, status="unconfirmed")
                raise
            self._ledger.finish(
                account.id, request_id, status="started",
                task_id=str(started["task_id"]), pid=int(started["pid"]),
            )
            return {"account_id": account.id, "request_id": request_id,
                    "task": task, "status": "started",
                    "task_id": started["task_id"], "pid": started["pid"]}

    def list_tasks(self, account_id: str) -> dict[str, object]:
        account = self._account(account_id)
        # Read can discover an already-running task after a backend restart.
        return {"account_id": account.id,
                "engine_tasks": self._ipc.list_managed_tasks(account),
                "requests": self._ledger.entries(account.id)}

    def stop(self, account_id: str, task_id: str) -> dict[str, object]:
        account = self._account(account_id)
        with self._mutex:
            self._lease(account)
            result = self._ipc.stop_managed_task(account, task_id)
            return {"account_id": account.id, **result}

    def acknowledge_uncertain_request(
        self, account_id: str, request_id: str, *, confirmed: bool,
    ) -> dict[str, str]:
        """User asserts they inspected engine/game state; no automatic redispatch."""
        if not confirmed:
            raise ValueError("Explicit manual reconciliation confirmation required")
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
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
