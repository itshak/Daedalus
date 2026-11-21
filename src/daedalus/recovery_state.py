"""Private, durable recovery policy and desired task journal.

This module is intentionally network-free. Recording an intent never performs
a Gameforge login or task dispatch. All credentials live outside this database.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from daedalus.accounts import Account
from daedalus.recovery_reconcile import canonical_fixed_transfer, restart_class_for
from daedalus.task_control import validated_configuration

# Only continuously observing tasks with no in-game state-changing operation may
# auto-resume without a game-state-specific reconciliation adapter.
RESTART_SAFE_TASKS = frozenset({"alertAttacks"})
DEFAULT_GRACE_SECONDS = 300
MAX_GRACE_SECONDS = 3600


def default_recovery_path() -> Path:
    home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return home / "daedalus" / "recovery.sqlite3"


def identity(account: Account) -> str:
    material = f"{account.id}\x00{account.world.casefold()}\x00{account.player.casefold()}"
    return hashlib.sha256(material.encode()).hexdigest()


class RecoveryConflict(ValueError):
    """A policy, receipt or identity conflicts with current state."""


class RecoveryStore:
    """Single SQLite authority for approval, deadlines and logical jobs."""

    def __init__(self, path: str | Path | None = None, *, clock=None) -> None:
        self.path = Path(path or default_recovery_path()).expanduser()
        self._clock = clock or time.time
        # Caller-injected clock is also used for deterministic fake-time tests.
        self._mono = clock or time.monotonic
        self._anchors: dict[str,tuple[str,float]] = {}
        self._mutex = threading.RLock()
        with self._db() as conn:
            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if schema_version not in (0, 1, 2):
                raise RecoveryConflict("Recovery journal schema requires a newer Daedalus")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS policies(
                    account_id TEXT PRIMARY KEY, identity TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    auto_resume INTEGER NOT NULL DEFAULT 0,
                    grace INTEGER NOT NULL DEFAULT 300,
                    pause_until REAL, pause_indefinite INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    account_id TEXT PRIMARY KEY, identity TEXT NOT NULL,
                    epoch TEXT NOT NULL, state TEXT NOT NULL,
                    lost_at REAL NOT NULL, due_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_reason TEXT, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS desired_jobs(
                    logical_id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                    identity TEXT NOT NULL, task TEXT NOT NULL,
                    config_json TEXT NOT NULL, digest TEXT NOT NULL,
                    restart_class TEXT NOT NULL,
                    desired_state TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    last_task_id TEXT, approved_at REAL NOT NULL,
                    UNIQUE(account_id, logical_id)
                );
                CREATE INDEX IF NOT EXISTS desired_by_account
                    ON desired_jobs(account_id, desired_state);
                CREATE TABLE IF NOT EXISTS login_attempts(
                    account_id TEXT NOT NULL, identity TEXT NOT NULL,
                    attempted_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS attempts_window
                    ON login_attempts(account_id,attempted_at);
                CREATE TABLE IF NOT EXISTS fixed_transfers(
                    transfer_id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                    identity TEXT NOT NULL, world TEXT NOT NULL, player TEXT NOT NULL,
                    intent_json TEXT NOT NULL, dispatched_json TEXT NOT NULL,
                    status TEXT NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fixed_transfer_chunks(
                    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transfer_id TEXT NOT NULL, route_index INTEGER NOT NULL,
                    cargo_json TEXT NOT NULL, status TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS fixed_transfer_pending
                    ON fixed_transfer_chunks(transfer_id, status);
                CREATE TABLE IF NOT EXISTS resume_receipts(
                    account_id TEXT NOT NULL, logical_id TEXT NOT NULL,
                    epoch TEXT NOT NULL, request_id TEXT NOT NULL,
                    status TEXT NOT NULL, engine_task_id TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(account_id,logical_id,epoch),
                    UNIQUE(account_id,request_id)
                );
            """)
            conn.execute("PRAGMA user_version=2")

    def _db(self):
        base = self.path.parent
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        if base.is_symlink() or self.path.is_symlink():
            raise RecoveryConflict("Private recovery state path must not be a symlink")
        if os.name == "posix":
            os.chmod(base, 0o700)
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=8)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=8000")
        if os.name == "posix":
            os.chmod(self.path, 0o600)
        return closing(conn)

    def _policy(self, conn, account: Account) -> dict[str, object]:
        row = conn.execute("SELECT * FROM policies WHERE account_id=?", (account.id,)).fetchone()
        if row is None or row["identity"] != identity(account):
            return {
                "account_id": account.id, "enabled": False, "auto_resume": False,
                "grace_seconds": DEFAULT_GRACE_SECONDS, "pause_until": None,
                "pause_indefinite": False, "revision": 0,
            }
        return {
            "account_id": account.id, "enabled": bool(row["enabled"]),
            "auto_resume": bool(row["auto_resume"]), "grace_seconds": row["grace"],
            "pause_until": row["pause_until"],
            "pause_indefinite": bool(row["pause_indefinite"]), "revision": row["revision"],
        }

    def policy(self, account: Account) -> dict[str, object]:
        with self._mutex, self._db() as conn:
            return self._policy(conn, account)

    def set_policy(self, account: Account, *, enabled: bool, auto_resume: bool,
                   grace_seconds: int = DEFAULT_GRACE_SECONDS,
                   expected_revision: int | None = None) -> dict[str, object]:
        if not account.enabled:
            raise RecoveryConflict("Disabled account cannot enable recovery")
        if type(enabled) is not bool or type(auto_resume) is not bool:
            raise RecoveryConflict("Recovery policy choices must be boolean")
        if auto_resume and not enabled:
            raise RecoveryConflict("Job auto-resume requires automatic session recovery")
        if type(grace_seconds) is not int or not 60 <= grace_seconds <= MAX_GRACE_SECONDS:
            raise RecoveryConflict("Grace period must be between 60 and 3600 seconds")
        now = self._clock()
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = self._policy(conn, account)
            if expected_revision is not None and prior["revision"] != expected_revision:
                raise RecoveryConflict("Recovery policy changed; refresh before saving")
            next_rev = int(prior["revision"]) + 1
            # Any identity change invalidates earlier opt-in and pause state.
            conn.execute("""
                INSERT INTO policies(account_id,identity,enabled,auto_resume,grace,
                                     revision,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    identity=excluded.identity, enabled=excluded.enabled,
                    auto_resume=excluded.auto_resume, grace=excluded.grace,
                    pause_until=NULL, pause_indefinite=0,
                    revision=excluded.revision,updated_at=excluded.updated_at
            """, (account.id, identity(account), int(enabled), int(auto_resume),
                  grace_seconds, next_rev, now))
            if not enabled:
                conn.execute("DELETE FROM events WHERE account_id=?", (account.id,))
                self._anchors.pop(account.id,None)
            conn.commit()
            return self._policy(conn, account)

    def pause(self, account: Account, *, seconds: int | None) -> dict[str, object]:
        if seconds is not None and (type(seconds) is not int or seconds not in (900,1800,3600)):
            raise RecoveryConflict("Pause must be 15, 30, 60 minutes, or indefinitely")
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = self._policy(conn, account)
            if not p["enabled"]:
                raise RecoveryConflict("Automatic recovery must be enabled first")
            conn.execute("""UPDATE policies SET pause_until=?,pause_indefinite=?,
                             revision=revision+1,updated_at=? WHERE account_id=?""",
                         (self._clock()+seconds if seconds else None,
                          int(seconds is None), self._clock(), account.id))
            conn.commit()
            return self._policy(conn, account)

    def unpause(self, account: Account) -> dict[str, object]:
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = self._policy(conn, account)
            if not p["enabled"]:
                raise RecoveryConflict("Automatic recovery must be enabled first")
            conn.execute("""UPDATE policies SET pause_until=NULL,pause_indefinite=0,
                             revision=revision+1,updated_at=? WHERE account_id=?""",
                         (self._clock(), account.id))
            conn.commit()
            return self._policy(conn, account)

    def record_loss(self, account: Account) -> dict[str, object] | None:
        """Idempotent confirmation: repeated probes never postpone the deadline."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = self._policy(conn, account)
            if not p["enabled"]:
                conn.rollback()
                return None
            row = conn.execute("SELECT * FROM events WHERE account_id=?", (account.id,)).fetchone()
            if row is None or row["identity"] != identity(account) or row["state"]=="restored":
                now = self._clock()
                epoch=str(uuid4())
                conn.execute("""INSERT OR REPLACE INTO events(
                    account_id,identity,epoch,state,lost_at,due_at,attempts,last_reason,updated_at)
                    VALUES(?,?,?,?,?,?,0,NULL,?)""",
                    (account.id, identity(account), epoch, "grace", now,
                     now + p["grace_seconds"], now))
                self._anchors[account.id]=(epoch,self._mono())
            conn.commit()
            return self._event(conn, account)

    def _event(self, conn, account: Account) -> dict[str, object] | None:
        row = conn.execute("SELECT * FROM events WHERE account_id=?", (account.id,)).fetchone()
        if row is None or row["identity"] != identity(account):
            return None
        return {
            "epoch": row["epoch"], "phase": row["state"], "lost_at": row["lost_at"],
            "due_at": row["due_at"], "attempts": row["attempts"],
            "last_reason": row["last_reason"],
        }

    def event(self, account: Account) -> dict[str, object] | None:
        with self._mutex, self._db() as conn:
            return self._event(conn, account)

    def protect_after_restart(self, accounts: list[Account]) -> None:
        """Restart cannot shorten countdown even with forward system clock shifts."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            now = self._clock()
            for a in accounts:
                p = self._policy(conn, a)
                if not p["enabled"]:
                    continue
                conn.execute("""UPDATE events SET due_at=MAX(due_at,?),
                    state='grace',updated_at=? WHERE account_id=? AND identity=?
                    AND state IN ('grace','attempting','retry')""",
                    (now + p["grace_seconds"], now, a.id, identity(a)))
                e=self._event(conn,a)
                if e and e["phase"]=="grace":
                    self._anchors[a.id]=(e["epoch"],self._mono())
            conn.commit()

    def reset_failed_for_manual_retry(self, account: Account) -> None:
        """User-approved fresh retry after fixing credentials or inspecting state."""
        with self._mutex,self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p=self._policy(conn,account)
            e=self._event(conn,account)
            if not p["enabled"]:
                raise RecoveryConflict("Automatic recovery must be enabled")
            if e and e["phase"]=="failed":
                conn.execute("DELETE FROM events WHERE account_id=?",(account.id,))
                self._anchors.pop(account.id,None)
            conn.commit()

    def claim_due(self, account: Account, *, force: bool = False) -> dict[str, object] | None:
        """Persist an exclusive attempt receipt, never two concurrent logins."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            p = self._policy(conn, account)
            e = self._event(conn, account)
            now = self._clock()
            if (not p["enabled"] or not e or e["phase"] not in ("grace","retry")
                    or p["pause_indefinite"] or
                    (p["pause_until"] is not None and p["pause_until"] > now)
                    or (not force and e["due_at"] > now)):
                conn.rollback()
                return None
            anchor=self._anchors.get(account.id)
            if (not force and anchor and anchor[0]==e["epoch"]
                    and self._mono()-anchor[1]<p["grace_seconds"]):
                conn.rollback()
                return None
            # Persistent rate limits bound repeated browser rotations as well
            # as retry loops within the same recovery epoch.
            hour=conn.execute("""SELECT COUNT(*) FROM login_attempts WHERE
                account_id=? AND identity=? AND attempted_at>?""",
                (account.id,identity(account),now-3600)).fetchone()[0]
            day=conn.execute("""SELECT COUNT(*) FROM login_attempts WHERE
                account_id=? AND identity=? AND attempted_at>?""",
                (account.id,identity(account),now-86400)).fetchone()[0]
            if e["attempts"] >= 3 or hour >= 3 or day >= 6:
                conn.execute("""UPDATE events SET state='failed',
                    last_reason='rate_limited',updated_at=?
                    WHERE account_id=?""",(now,account.id))
                conn.commit()
                return None
            conn.execute("""INSERT INTO login_attempts(account_id,identity,attempted_at)
                VALUES(?,?,?)""",(account.id,identity(account),now))
            conn.execute("""DELETE FROM login_attempts WHERE attempted_at<?""",(now-604800,))
            conn.execute("""UPDATE events SET state='attempting',attempts=attempts+1,
                updated_at=? WHERE account_id=? AND identity=?""", (now, account.id, identity(account)))
            conn.commit()
            return self._event(conn, account)

    def outcome(self, account: Account, epoch: str, *, success: bool,
                reason: str = "needs_assistance") -> None:
        if reason not in ("needs_assistance","token_unavailable","challenge_required",
                          "network_error","identity_mismatch","ipc_unavailable",
                          "task_ambiguous","rate_limited","verified"):
            raise RecoveryConflict("Unrecognized recovery result")
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            e = self._event(conn, account)
            if not e or e["epoch"] != epoch or e["phase"] != "attempting":
                raise RecoveryConflict("Recovery attempt was already resolved")
            now = self._clock()
            is_retry = reason in ("network_error","ipc_unavailable") and e["attempts"] < 3
            delay = (300,900,3600)[min(e["attempts"]-1,2)]
            conn.execute("""UPDATE events SET state=?,due_at=?,last_reason=?,updated_at=?
                WHERE account_id=? AND epoch=?""",
                ("restored" if success else "retry" if is_retry else "failed",
                 now if success else now + delay, "verified" if success else reason,
                 now, account.id, epoch))
            conn.commit()

    def capture_started(self, account: Account, task: str, config: dict,
                        task_id: str, *, restart_class: str | None = None) -> str:
        clean, digest = validated_configuration(config)
        allowed_class = restart_class_for(task, clean)
        if restart_class is not None and restart_class != allowed_class:
            raise RecoveryConflict("Restartability cannot be escalated by caller")
        restart_class = allowed_class
        now = self._clock()
        canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            job_id = str(uuid4())
            conn.execute("""INSERT INTO desired_jobs(
                logical_id,account_id,identity,task,config_json,digest,
                restart_class,desired_state,last_task_id,approved_at)
                VALUES(?,?,?,?,?,?,?,'running',?,?)""",
                (job_id, account.id, identity(account), task, canonical,digest,
                 restart_class,task_id,now))
            conn.commit()
            return job_id

    def stop_task(self, account: Account, task_id: str) -> int:
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed=conn.execute("""UPDATE desired_jobs SET desired_state='stopped',
                revision=revision+1 WHERE account_id=? AND identity=? AND last_task_id=?""",
                (account.id,identity(account),task_id)).rowcount
            conn.commit()
            return changed

    def desired(self, account: Account, *, include_config: bool = False) -> list[dict[str, object]]:
        with self._mutex,self._db() as conn:
            rows=conn.execute("""SELECT * FROM desired_jobs WHERE account_id=? AND identity=?
                ORDER BY approved_at,logical_id""",(account.id,identity(account))).fetchall()
        return [{
            "id":r["logical_id"], "task":r["task"], "digest":r["digest"],
            "restart_class":r["restart_class"], "desired_state":r["desired_state"],
            "revision":r["revision"], "last_task_id":r["last_task_id"],
            **({"config":json.loads(r["config_json"])} if include_config else {}),
        } for r in rows]

    def complete_job(self, account: Account, job_id: str, *, revision: int) -> bool:
        """Mark an absolute construction target completed only after game readback."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("""UPDATE desired_jobs
                SET desired_state='completed', revision=revision+1
                WHERE account_id=? AND identity=? AND logical_id=?
                  AND revision=? AND desired_state='running'
                  AND restart_class IN ('reconcile_construction','fixed_transfer')""",
                (account.id, identity(account), job_id, revision)).rowcount
            conn.commit()
            return changed == 1

    def begin_resume(self, account: Account, job_id: str, epoch: str) -> dict[str,str] | None:
        with self._mutex,self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row=conn.execute("""SELECT * FROM desired_jobs WHERE account_id=?
                AND identity=? AND logical_id=?""",
                (account.id,identity(account),job_id)).fetchone()
            if (not row or row["desired_state"] != "running"
                    or row["restart_class"] not in (
                        "continuous", "reconcile_construction", "convergent_transport",
                        "fixed_transfer")):
                conn.rollback()
                return None
            old=conn.execute("""SELECT * FROM resume_receipts WHERE account_id=?
                AND logical_id=? AND epoch=?""",(account.id,job_id,epoch)).fetchone()
            if old:
                conn.rollback()
                return None
            request_id=str(uuid4())
            conn.execute("""INSERT INTO resume_receipts(account_id,logical_id,epoch,
                request_id,status,updated_at) VALUES(?,?,?,?,'dispatching',?)""",
                (account.id,job_id,epoch,request_id,self._clock()))
            conn.commit()
            return {"request_id":request_id,"job_id":job_id,"task":row["task"],
                    "config":json.loads(row["config_json"]),"revision":row["revision"]}

    def finish_resume(self, account: Account, job_id: str, epoch: str,
                      *, status: str, task_id: str | None = None, revision: int | None = None) -> None:
        if status not in ("started","unconfirmed","rejected","skipped"):
            raise RecoveryConflict("Invalid restoration receipt")
        with self._mutex,self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed=conn.execute("""UPDATE resume_receipts SET status=?,
                engine_task_id=?,updated_at=? WHERE account_id=? AND logical_id=?
                AND epoch=? AND status='dispatching'""",
                (status,task_id,self._clock(),account.id,job_id,epoch)).rowcount
            if changed!=1:
                raise RecoveryConflict("Recovery receipt no longer pending")
            if status=="started" and task_id is not None and revision is not None:
                # A user stop/edit during IPC dispatch MUST NOT be forgotten.
                conn.execute("""UPDATE desired_jobs SET last_task_id=?
                    WHERE logical_id=? AND account_id=? AND revision=?
                    AND desired_state='running'""",(task_id,job_id,account.id,revision))
            conn.commit()

    def receipts(self, account: Account) -> list[dict[str,object]]:
        with self._mutex,self._db() as conn:
            rows=conn.execute("""SELECT logical_id,epoch,request_id,status,engine_task_id
                FROM resume_receipts WHERE account_id=? ORDER BY updated_at DESC LIMIT 100""",
                (account.id,)).fetchall()
        return [dict(x) for x in rows]

    def summary(self, account: Account) -> dict[str,object]:
        p=self.policy(account)
        e=self.event(account)
        jobs=self.desired(account)
        return {"account_id":account.id,"policy":p,"event":e,
                "desired_jobs":sum(j["desired_state"]=="running" for j in jobs),
                "auto_resume_eligible":sum(j["restart_class"] in (
                    "continuous", "reconcile_construction", "convergent_transport",
                    "fixed_transfer"
                ) and j["desired_state"]=="running" for j in jobs),
                "manual_review":sum(j["restart_class"]=="manual" and
                                    j["desired_state"]=="running" for j in jobs)}
