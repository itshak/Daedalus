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
from daedalus.recovery_reconcile import checkpoint_intent, restart_class_for
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
                CREATE TABLE IF NOT EXISTS warehouse_fill_recovery(
                    transfer_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS warehouse_fill_verified(
                    chunk_id INTEGER PRIMARY KEY, transfer_id TEXT NOT NULL,
                    observed_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS production_runs(
                    run_id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                    identity TEXT NOT NULL, world TEXT NOT NULL, player TEXT NOT NULL,
                    intent_json TEXT NOT NULL, status TEXT NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS production_cities(
                    run_id TEXT NOT NULL, city_id INTEGER NOT NULL, status TEXT NOT NULL,
                    result_json TEXT, PRIMARY KEY(run_id,city_id)
                );
                CREATE TABLE IF NOT EXISTS production_stages(
                    run_id TEXT NOT NULL, city_id INTEGER NOT NULL, stage TEXT NOT NULL,
                    kind TEXT NOT NULL, value INTEGER NOT NULL, status TEXT NOT NULL,
                    observation_json TEXT, updated_at REAL NOT NULL,
                    PRIMARY KEY(run_id,city_id,stage)
                );
                CREATE TABLE IF NOT EXISTS production_reconciliations(
                    run_id TEXT PRIMARY KEY, observation_json TEXT NOT NULL,
                    reconciled_at REAL NOT NULL
                );
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
            # New, enabled accounts recover automatically by default.
            # A persisted user disable/paused policy is always authoritative.
            # If an existing account ID changes world/player, do not
            # accidentally authorize recovery for its new identity.
            enabled_by_default = account.enabled and row is None
            return {
                "account_id": account.id,
                "enabled": bool(enabled_by_default),
                "auto_resume": bool(enabled_by_default),
                "grace_seconds": DEFAULT_GRACE_SECONDS, "pause_until": None,
                "pause_indefinite": False, "revision": 0,
            }
        return {
            "account_id": account.id, "enabled": account.enabled and bool(row["enabled"]),
            "auto_resume": account.enabled and bool(row["enabled"]) and bool(row["auto_resume"]), "grace_seconds": row["grace"],
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
                    pause_until=CASE WHEN policies.identity=excluded.identity AND excluded.enabled=1 THEN policies.pause_until ELSE NULL END,
                    pause_indefinite=CASE WHEN policies.identity=excluded.identity AND excluded.enabled=1 THEN policies.pause_indefinite ELSE 0 END,
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
            now = self._clock()
            # A new account uses a virtual default-on policy until its first
            # write. Materialize it atomically before persisting a pause.
            conn.execute("""INSERT INTO policies(
                account_id,identity,enabled,auto_resume,grace,
                pause_until,pause_indefinite,revision,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    pause_until=excluded.pause_until,
                    pause_indefinite=excluded.pause_indefinite,
                    revision=policies.revision+1,
                    updated_at=excluded.updated_at""",
                (account.id, identity(account), int(p["enabled"]),
                 int(p["auto_resume"]), p["grace_seconds"],
                 now+seconds if seconds else None, int(seconds is None),
                 int(p["revision"])+1, now))
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

    def note_verified_manual_recovery(self, account: Account) -> None:
        """A separately attested explicit browser login resolves a failed epoch."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            event = self._event(conn, account)
            if event and event["phase"] == "failed":
                now = self._clock()
                conn.execute("""UPDATE events SET state='restored',due_at=?,
                    last_reason='verified',updated_at=? WHERE account_id=? AND epoch=?""",
                    (now, now, account.id, event["epoch"]))
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
            conn.execute("""UPDATE fixed_transfers
                SET status='stopped',updated_at=? WHERE transfer_id IN (
                    SELECT logical_id FROM desired_jobs
                    WHERE account_id=? AND identity=? AND last_task_id=?
                )""", (self._clock(), account.id, identity(account), task_id))
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

    def complete_job(self, account: Account, job_id: str, *, revision: int,
                     warehouse_reason: str | None = None, epoch: str | None = None) -> bool:
        """Persist a verified terminal observation and preserve its reason."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if epoch is not None and not self._resume_permitted(conn, account, epoch):
                return False
            if warehouse_reason is not None:
                if warehouse_reason not in {"warehouse_capacity_reached", "warehouse_intent_exhausted"}:
                    raise RecoveryConflict("Invalid warehouse completion reason")
                job = conn.execute("""SELECT j.restart_class, f.status FROM desired_jobs j
                    JOIN fixed_transfers f ON f.transfer_id=j.logical_id
                    WHERE j.logical_id=? AND j.account_id=? AND j.identity=?
                    AND j.revision=? AND j.desired_state='running'""",
                    (job_id, account.id, identity(account), revision)).fetchone()
                if job is None or job["restart_class"] != "warehouse_fill":
                    return False
                pending = conn.execute("""SELECT 1 FROM fixed_transfer_chunks c
                    LEFT JOIN warehouse_fill_verified v ON v.chunk_id=c.chunk_id AND v.transfer_id=c.transfer_id
                    WHERE c.transfer_id=? AND (c.status='pending' OR
                    (c.status='confirmed' AND v.chunk_id IS NULL)) LIMIT 1""", (job_id,)).fetchone()
                unresolved_resume = conn.execute("""SELECT 1 FROM resume_receipts
                    WHERE account_id=? AND logical_id=? AND status IN ('dispatching','unconfirmed') LIMIT 1""",
                    (account.id, job_id)).fetchone()
                if pending or unresolved_resume or job["status"] not in ("prepared", "running", "held_stock", "complete", "capacity_reached"):
                    return False
            changed = conn.execute("""UPDATE desired_jobs
                SET desired_state='completed', revision=revision+1
                WHERE account_id=? AND identity=? AND logical_id=?
                  AND revision=? AND desired_state='running'
                  AND restart_class IN ('reconcile_construction','fixed_transfer','warehouse_fill')
                  AND (restart_class!='warehouse_fill' OR ? IS NOT NULL)""",
                (account.id, identity(account), job_id, revision, warehouse_reason)).rowcount
            if changed and warehouse_reason is not None:
                conn.execute("UPDATE fixed_transfers SET status=?,updated_at=? WHERE transfer_id=?",
                             ("capacity_reached" if warehouse_reason == "warehouse_capacity_reached" else "complete",
                              self._clock(), job_id))
                conn.execute("""INSERT INTO warehouse_fill_recovery(transfer_id,revision,reason) VALUES(?,?,?)
                    ON CONFLICT(transfer_id) DO UPDATE SET revision=excluded.revision,reason=excluded.reason""",
                    (job_id, revision+1, warehouse_reason))
            conn.commit()
            return changed == 1

    def settle_warehouse_jobs(self, account: Account) -> None:
        """Retire already verified terminal jobs before matching a new launch.

        Caller must have established that no warehouse worker is active.
        """
        for job in self.desired(account, include_config=True):
            if job["restart_class"] != "warehouse_fill" or job["desired_state"] != "running":
                continue
            try:
                progress = self.fixed_transfer_progress(account, job["config"], task=job["task"])
            except RecoveryConflict:
                continue
            if progress["completed"] and not progress["uncertain"]:
                self.complete_job(account, job["id"], revision=job["revision"],
                                  warehouse_reason=progress.get("hold_reason") or "warehouse_intent_exhausted")

    def _resume_permitted(self, conn, account: Account, epoch: str) -> bool:
        policy = self._policy(conn, account)
        event = self._event(conn, account)
        return bool(policy["enabled"] and policy["auto_resume"] and event
                    and event["epoch"] == epoch and event["phase"] == "restored"
                    and not policy["pause_indefinite"]
                    and (policy["pause_until"] is None or policy["pause_until"] <= self._clock()))

    def resume_permitted(self, account: Account, epoch: str) -> bool:
        with self._mutex, self._db() as conn:
            return self._resume_permitted(conn, account, epoch)

    def begin_resume(self, account: Account, job_id: str, epoch: str) -> dict[str,str] | None:
        with self._mutex,self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not self._resume_permitted(conn, account, epoch):
                conn.rollback()
                return None
            row=conn.execute("""SELECT * FROM desired_jobs WHERE account_id=?
                AND identity=? AND logical_id=?""",
                (account.id,identity(account),job_id)).fetchone()
            if (not row or row["desired_state"] != "running"
                    or row["restart_class"] not in (
                        "continuous", "reconcile_construction", "convergent_transport",
                        "fixed_transfer", "warehouse_fill")):
                conn.rollback()
                return None
            old=conn.execute("""SELECT * FROM resume_receipts WHERE account_id=?
                AND logical_id=? AND (epoch=? OR status IN ('dispatching','unconfirmed'))""",
                (account.id,job_id,epoch)).fetchone()
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
                FROM resume_receipts WHERE account_id=? AND logical_id IN (
                    SELECT logical_id FROM desired_jobs WHERE account_id=? AND identity=?
                ) ORDER BY updated_at DESC LIMIT 100""",
                (account.id, account.id, identity(account))).fetchall()
        return [dict(x) for x in rows]

    def warehouse_transport_uncertain(self, account: Account) -> bool:
        """Unresolved warehouse cargo must not trigger another automatic transport."""
        for job in self.desired(account, include_config=True):
            if (job["restart_class"] != "warehouse_fill"
                    or job["desired_state"] not in ("running", "dispatching", "review")):
                continue
            try:
                if self.fixed_transfer_progress(account, job["config"], task=job["task"])["uncertain"]:
                    return True
            except RecoveryConflict:
                return True
        return False

    def summary(self, account: Account) -> dict[str,object]:
        p=self.policy(account)
        e=self.event(account)
        jobs=self.desired(account, include_config=True)
        eligible=manual=0
        for job in jobs:
            if job["desired_state"] not in ("running", "review", "dispatching"):
                continue
            if job["restart_class"] == "warehouse_fill":
                try:
                    progress=self.fixed_transfer_progress(account,job["config"],task=job["task"])
                except RecoveryConflict:
                    progress={"uncertain":True}
                if progress["uncertain"] or job["desired_state"] != "running":
                    manual+=1
                elif not progress["completed"]:
                    eligible+=1
            elif job["desired_state"] == "running":
                if job["restart_class"] in ("continuous", "reconcile_construction",
                        "convergent_transport", "fixed_transfer"):
                    eligible+=1
                elif job["restart_class"] == "manual":
                    manual+=1
        return {"account_id":account.id,"policy":p,"event":e,
                "desired_jobs":sum(j["desired_state"]=="running" for j in jobs),
                "auto_resume_eligible":eligible,
                "manual_review":manual}

    def production_blocked(self, account: Account) -> bool:
        with self._db() as conn:
            return conn.execute("""SELECT 1 FROM production_runs
                WHERE world=? AND player=? AND status='prepared' LIMIT 1""",
                (account.world.casefold(), account.player.casefold())).fetchone() is not None

    def prepare_production(self, account: Account, run_id: str, plans: list) -> None:
        from uuid import UUID

        from daedalus.production_inventory import validate_priority_draft, validate_priority_plan

        if not isinstance(run_id, str) or UUID(run_id).version != 4 or str(UUID(run_id)) != run_id:
            raise RecoveryConflict("Invalid production run identity")
        if not isinstance(plans, list) or not plans or any(not isinstance(p, dict) for p in plans):
            raise RecoveryConflict("Invalid production plans")
        rows = [{"city_id": p.get("city_id"), "draft": p.get("draft")} for p in plans]
        clean = validate_priority_draft(rows[0]["city_id"], rows)
        plans = [validate_priority_plan(r["city_id"], r["draft"], p) for r, p in zip(clean, plans)]
        canonical = json.dumps(plans, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("""SELECT 1 FROM production_runs
                WHERE world=? AND player=? AND status='prepared'""",
                (account.world.casefold(), account.player.casefold())).fetchone():
                raise RecoveryConflict("Earlier production needs reconciliation")
            conn.execute("""INSERT INTO production_runs
                VALUES(?,?,?,?,?,?,'prepared',?)""",
                (run_id, account.id, identity(account), account.world.casefold(),
                 account.player.casefold(), canonical, self._clock()))
            conn.commit()

    def reject_production(self, account: Account, run_id: str) -> None:
        """Only a definitive no-child-start receipt can release this fence."""
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""UPDATE production_runs SET status='rejected',updated_at=?
                WHERE run_id=? AND account_id=? AND identity=? AND status='prepared'
                AND NOT EXISTS (SELECT 1 FROM production_cities WHERE run_id=?)""",
                (self._clock(), run_id, account.id, identity(account), run_id))
            conn.commit()

    def production_intent(self, account: Account, run_id: str) -> list[dict]:
        with self._db() as conn:
            row = conn.execute("""SELECT intent_json FROM production_runs
                WHERE run_id=? AND account_id=? AND identity=? AND status='prepared'""",
                (run_id, account.id, identity(account))).fetchone()
            if row is None:
                raise RecoveryConflict("Production run does not require reconciliation")
            return json.loads(row["intent_json"])

    def reconcile_production(self, account: Account, run_id: str, observations: list) -> None:
        """Archive operator-reviewed actual counts, without applying another assignment."""
        canonical = json.dumps(observations, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("""UPDATE production_runs SET status='reconciled',updated_at=?
                WHERE run_id=? AND account_id=? AND identity=? AND status='prepared'""",
                (self._clock(), run_id, account.id, identity(account))).rowcount
            if changed != 1:
                raise RecoveryConflict("Production run is no longer pending")
            conn.execute("INSERT INTO production_reconciliations VALUES(?,?,?)",
                         (run_id, canonical, self._clock()))
            conn.commit()

    def production_progress(self, account: Account) -> list[dict]:
        with self._db() as conn:
            runs = conn.execute("""SELECT run_id,status,updated_at,intent_json FROM production_runs
                WHERE account_id=? AND identity=? ORDER BY updated_at DESC LIMIT 20""",
                (account.id, identity(account))).fetchall()
            results = []
            for run in runs:
                cities = {r["city_id"]: r for r in conn.execute(
                    "SELECT city_id,status,result_json FROM production_cities WHERE run_id=?", (run["run_id"],))}
                rows = []
                for plan in json.loads(run["intent_json"]):
                    cid = plan["city_id"]
                    city = cities.get(cid)
                    stages = []
                    for receipt in conn.execute("""SELECT stage,kind,value,status,observation_json
                        FROM production_stages WHERE run_id=? AND city_id=? ORDER BY rowid""", (run["run_id"],cid)):
                        stage = dict(receipt)
                        observed = stage.pop("observation_json")
                        if observed:
                            inv = json.loads(observed)
                            stage["observed"] = {kind: inv["sites"][kind]["current"] for kind in ("resource", "tradegood")}
                        stages.append(stage)
                    rows.append({"city_id": cid, "resource": plan["resource"],
                        "target_before": plan["target_before"], "donor_before": plan["donor_before"],
                        "desired": plan["desired"], "donor_release": plan["donor_release"],
                        "status": city["status"] if city else "not_started", "stages": stages,
                        "result": json.loads(city["result_json"]) if city and city["result_json"] else None})
                resolved = conn.execute("SELECT observation_json FROM production_reconciliations WHERE run_id=?",
                                        (run["run_id"],)).fetchone()
                results.append({"run_id":run["run_id"], "status":run["status"],
                                "updated_at":run["updated_at"], "cities":rows,
                                "reconciled_observations": json.loads(resolved[0]) if resolved else None})
            return results

    def prepare_fixed_transfer(self, account: Account, config: dict, *, task="sendResources") -> str:
        """Persist approved absolute cargo intent BEFORE engine task dispatch."""
        if restart_class_for(task, config) not in ("fixed_transfer", "warehouse_fill"):
            raise RecoveryConflict("Fixed transfer lacks a verified checkpoint key")
        clean, digest = validated_configuration(config)
        intent = checkpoint_intent(task, clean)
        if intent is None:
            raise RecoveryConflict("Unsupported fixed transfer routes")
        transfer_id = config["transfer_id"]
        canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
        target = json.dumps(intent, sort_keys=True, separators=(",", ":"))
        zero = json.dumps([[0] * 5 for _ in intent["routes"]])
        now = self._clock()
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT digest FROM desired_jobs WHERE logical_id=?",
                (transfer_id,),
            ).fetchone()
            if prior is not None:
                raise RecoveryConflict("Fixed transfer identifier has already been used")
            conn.execute("""INSERT INTO desired_jobs(
                logical_id,account_id,identity,task,config_json,digest,
                restart_class,desired_state,last_task_id,approved_at)
                VALUES(?,?,?,?,?,?,?,'dispatching',NULL,?)""",
                (transfer_id, account.id, identity(account), task,
                 canonical, digest, restart_class_for(task, clean), now))
            conn.execute("""INSERT INTO fixed_transfers(
                transfer_id,account_id,identity,world,player,intent_json,
                dispatched_json,status,updated_at)
                VALUES(?,?,?,?,?,?,?,'prepared',?)""",
                (transfer_id, account.id, identity(account),
                 account.world.casefold(), account.player.casefold(),
                 target, zero, now))
            conn.commit()
        return transfer_id

    def finish_fixed_transfer(self, account: Account, transfer_id: str,
                              *, status: str, task_id: str | None = None) -> None:
        """Preserve uncertainty if IPC launch cannot be proved unsuccessful."""
        if status not in ("started", "rejected", "unconfirmed"):
            raise RecoveryConflict("Unknown fixed transfer launch result")
        with self._mutex, self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT desired_state FROM desired_jobs
                WHERE logical_id=? AND account_id=? AND identity=?
                AND restart_class IN ('fixed_transfer','warehouse_fill')""",
                (transfer_id, account.id, identity(account))).fetchone()
            if row is None or row[0] != "dispatching":
                raise RecoveryConflict("Fixed transfer start receipt was already resolved")
            state = "running" if status == "started" else (
                "stopped" if status == "rejected" else "review"
            )
            conn.execute("""UPDATE desired_jobs
                SET desired_state=?,last_task_id=?,revision=revision+1
                WHERE logical_id=?""", (state, task_id, transfer_id))
            if status != "started":
                conn.execute("""UPDATE fixed_transfers
                    SET status=?,updated_at=? WHERE transfer_id=?""",
                    ("stopped" if status == "rejected" else "unconfirmed",
                     self._clock(), transfer_id))
            else:
                conn.execute("""UPDATE fixed_transfers
                    SET status='running',updated_at=?
                    WHERE transfer_id=? AND status='prepared'""",
                    (self._clock(), transfer_id))
            conn.commit()

    def record_warehouse_reason(self, account: Account, job_id: str, revision: int, reason: str) -> None:
        """Persist a bounded reconciliation reason, tied to the exact job revision."""
        if reason not in {"warehouse_untracked", "warehouse_receipt_uncertain", "warehouse_intent_exhausted",
                          "warehouse_city_changed", "warehouse_capacity_reached", "warehouse_fleet_unavailable",
                          "warehouse_source_unavailable", "warehouse_source_stock_missing",
                          "warehouse_remaining", "warehouse_observation_unavailable"}:
            raise RecoveryConflict("Unknown warehouse recovery reason")
        with self._mutex, self._db() as conn:
            conn.execute("""INSERT INTO warehouse_fill_recovery(transfer_id,revision,reason)
                SELECT logical_id,revision,? FROM desired_jobs WHERE logical_id=? AND account_id=?
                AND identity=? AND revision=? AND restart_class='warehouse_fill'
                ON CONFLICT(transfer_id) DO UPDATE SET revision=excluded.revision,reason=excluded.reason""",
                         (reason, job_id, account.id, identity(account), revision))
            conn.commit()

    def warehouse_reason(self, account: Account, job_id: str, revision: int) -> str | None:
        with self._mutex, self._db() as conn:
            row = conn.execute("""SELECT r.reason FROM warehouse_fill_recovery r JOIN desired_jobs j
                ON j.logical_id=r.transfer_id WHERE j.account_id=? AND j.identity=? AND j.logical_id=?
                AND r.revision=? AND j.revision=?""",
                               (account.id, identity(account), job_id, revision, revision)).fetchone()
        return row["reason"] if row else None

    def fixed_transfer_progress(self, account: Account,
                                config: dict, *, task="sendResources") -> dict[str, object]:
        """Read accepted transport receipts; a pending POST blocks replay."""
        if restart_class_for(task, config) not in ("fixed_transfer", "warehouse_fill"):
            raise RecoveryConflict("Fixed transfer intent is untracked")
        tid = config["transfer_id"]
        normalized = checkpoint_intent(task, config)
        expected = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        with self._mutex, self._db() as conn:
            row = conn.execute("""SELECT ft.intent_json,ft.dispatched_json,ft.status
                FROM fixed_transfers ft JOIN desired_jobs j
                  ON j.logical_id=ft.transfer_id
                WHERE ft.transfer_id=? AND ft.account_id=? AND ft.identity=?
                  AND j.account_id=? AND j.identity=? AND j.task=?
                  AND j.config_json=?""", (
                    tid, account.id, identity(account), account.id,
                    identity(account), task, json.dumps(config, sort_keys=True,
                                                 separators=(",", ":")),
                )).fetchone()
            pending = conn.execute("""SELECT COUNT(*) FROM fixed_transfer_chunks
                WHERE transfer_id=? AND status='pending'""", (tid,)).fetchone()[0]
            if task == "fillCityWarehouse":
                confirmed_chunks = conn.execute("""SELECT route_index,cargo_json FROM fixed_transfer_chunks
                    WHERE transfer_id=? AND status='confirmed'""", (tid,)).fetchall()
                pending += conn.execute("""SELECT COUNT(*) FROM fixed_transfer_chunks c
                    LEFT JOIN warehouse_fill_verified v ON v.chunk_id=c.chunk_id AND v.transfer_id=c.transfer_id
                    WHERE c.transfer_id=? AND c.status='confirmed' AND v.chunk_id IS NULL""", (tid,)).fetchone()[0]
        if row is None or row["intent_json"] != expected:
            raise RecoveryConflict("Missing or mismatched fixed transfer checkpoint")
        try:
            sent = json.loads(row["dispatched_json"])
            target = [route["resources"] for route in normalized["routes"]]
            if (not isinstance(sent, list) or len(sent) != len(target)
                    or any(not isinstance(vector, list) or len(vector) != 5
                           or any(type(v) is not int or not 0 <= v <= cap
                                  for v, cap in zip(vector, limits))
                           for vector, limits in zip(sent, target))):
                raise ValueError("Invalid fixed shipment counters")
            if task == "fillCityWarehouse":
                totals = [[0] * 5 for _ in target]
                for chunk in confirmed_chunks:
                    index = chunk["route_index"]
                    cargo = json.loads(chunk["cargo_json"])
                    if (type(index) is not int or not 0 <= index < len(target)
                            or not isinstance(cargo, list) or len(cargo) != 5
                            or any(type(v) is not int or v < 0 for v in cargo)):
                        raise ValueError("Invalid warehouse receipt")
                    totals[index] = [a + b for a, b in zip(totals[index], cargo)]
                if totals != sent:
                    raise ValueError("Warehouse receipt totals do not match checkpoint")
        except (ValueError, TypeError) as exc:
            raise RecoveryConflict("Fixed transfer progress is corrupt") from exc
        return {
            "dispatched": sent,
            "remaining": [[limit - actual for limit, actual in zip(t, s)]
                          for t, s in zip(target, sent)],
            "uncertain": pending > 0 or row["status"] not in (
                ("prepared", "running", "complete", "capacity_reached", "held_stock")
                if task == "fillCityWarehouse" else ("prepared", "running", "complete")),
            "completed": (all(t == s for t, s in zip(target, sent)) or
                          (task == "fillCityWarehouse" and row["status"] == "capacity_reached"))
                         and (task != "fillCityWarehouse" or (pending == 0 and row["status"] in
                              ("prepared", "running", "complete", "capacity_reached", "held_stock"))),
            **({"hold_reason": "warehouse_source_stock_missing"} if task == "fillCityWarehouse" and row["status"] == "held_stock" else {}),
            **({"hold_reason": "warehouse_capacity_reached"} if task == "fillCityWarehouse" and row["status"] == "capacity_reached" else {}),
        }
