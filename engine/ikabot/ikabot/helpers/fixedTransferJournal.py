"""Durable, fail-closed checkpoint for Daedalus-managed fixed cargo transfers.

Only approved, same-account, owned-city sendResources intents use this module.
The game transport POST is never retried after an uncertain response. A chunk
has a write-ahead pending receipt before POST and is committed only after the
IkaBot server reports definitive transport acceptance (type 10).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID


class FixedTransferUnsafe(RuntimeError):
    """An operation may have committed; never automatically send it twice."""


def canonical_transfer(routes, use_freighters=False):
    """Normalize a fixed-amount, owned-city-only transfer intent."""
    if type(use_freighters) is not bool or not isinstance(routes, list) or not 0 < len(routes) <= 40:
        raise ValueError("Unsupported fixed transfer policy")
    clean = []
    for row in routes:
        if not isinstance(row, dict) or set(row) != {"from", "to", "resources"}:
            raise ValueError("Only explicit owned-city fixed routes are checkpointable")
        src, dest, amounts = row["from"], row["to"], row["resources"]
        if (type(src) is not int or type(dest) is not int
                or not 0 < src < 10**12 or not 0 < dest < 10**12 or src == dest
                or not isinstance(amounts, list) or len(amounts) != 5
                or any(type(x) is not int or not 0 <= x <= 10**12 for x in amounts)
                or sum(amounts) == 0):
            raise ValueError("Invalid fixed transfer resources")
        clean.append({"from": src, "to": dest, "resources": amounts[:]})
    return {"routes": clean, "useFreighters": use_freighters}


def _verified_uuid(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
    ) or str(UUID(value)) != value:
        raise ValueError("Fixed transfer requires canonical UUID4")
    return value


class FixedTransferJournal:
    """Unprivileged engine-facing read/commit access to an existing host ledger."""

    def __init__(self, session, transfer_id, routes, use_freighters=False, *, db_path=None):
        self.transfer_id = _verified_uuid(transfer_id)
        self.intent = canonical_transfer(routes, use_freighters)
        self.canonical = json.dumps(self.intent, sort_keys=True, separators=(",", ":"))
        self.world = f"s{session.mundo}-{session.servidor}".casefold()
        self.player = session.username.casefold()
        path = db_path or os.environ.get("DAEDALUS_FIXED_TRANSFER_DB")
        if not path:
            raise FixedTransferUnsafe("Protected fixed transfer ledger is not configured")
        self.path = Path(path).expanduser()
        with self._db() as conn:
            self._verify(conn)

    @contextmanager
    def _db(self):
        path = self.path
        if path.is_symlink() or path.parent.is_symlink():
            raise FixedTransferUnsafe("Unsafe fixed transfer journal path")
        try:
            details = path.stat()
            directory = path.parent.stat()
        except OSError as exc:
            raise FixedTransferUnsafe("Fixed transfer journal is unavailable") from exc
        if not stat.S_ISREG(details.st_mode) or not stat.S_ISDIR(directory.st_mode):
            raise FixedTransferUnsafe("Fixed transfer journal is not a regular file")
        if os.name == "posix" and (
            details.st_uid != os.getuid() or details.st_mode & 0o077
            or directory.st_mode & 0o077
        ):
            raise FixedTransferUnsafe("Fixed transfer journal must be owner-only")
        conn = sqlite3.connect(path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            yield conn
        finally:
            conn.close()

    def _verify(self, conn):
        row = conn.execute(
            """SELECT world, player, intent_json, status, dispatched_json
               FROM fixed_transfers WHERE transfer_id=?""", (self.transfer_id,)
        ).fetchone()
        if (row is None or row["world"] != self.world or row["player"] != self.player
                or row["intent_json"] != self.canonical
                or row["status"] not in ("prepared", "running", "complete")):
            raise FixedTransferUnsafe("Fixed transfer is not approved for this identity")
        dispatched = json.loads(row["dispatched_json"])
        targets = [route["resources"] for route in self.intent["routes"]]
        if (not isinstance(dispatched, list) or len(dispatched) != len(targets)
                or any(not isinstance(row, list) or len(row) != 5
                       or any(type(value) is not int or not 0 <= value <= cap
                              for value, cap in zip(row, target))
                       for row, target in zip(dispatched, targets))):
            raise FixedTransferUnsafe("Fixed transfer progress is invalid")
        return dispatched

    def _pending(self, conn):
        return conn.execute(
            """SELECT chunk_id FROM fixed_transfer_chunks
               WHERE transfer_id=? AND status='pending' LIMIT 1""",
            (self.transfer_id,),
        ).fetchone()

    def remaining(self, index, requested):
        """Never reuse a quantity from an unconfirmed transport POST."""
        with self._db() as conn:
            sent = self._verify(conn)
            if self._pending(conn):
                raise FixedTransferUnsafe("Uncertain in-flight transport needs reconciliation")
            if type(index) is not int or not 0 <= index < len(sent):
                raise FixedTransferUnsafe("Invalid fixed transfer route index")
            target = self.intent["routes"][index]["resources"]
            if list(requested) != target:
                raise FixedTransferUnsafe("Fixed transfer route was changed")
            return [cap - actual for cap, actual in zip(target, sent[index])]

    def reserve(self, index, quantities):
        """Persist a pending receipt BEFORE the real game transport POST."""
        if (type(index) is not int or not 0 <= index < len(self.intent["routes"])
                or not isinstance(quantities, list) or len(quantities) != 5
                or sum(quantities) <= 0
                or any(type(v) is not int or v < 0 for v in quantities)):
            raise FixedTransferUnsafe("Invalid outgoing cargo checkpoint")
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sent = self._verify(conn)
            if self._pending(conn):
                raise FixedTransferUnsafe("A previous transport outcome is unconfirmed")
            maximum = self.intent["routes"][index]["resources"]
            if any(confirmed + current > target
                   for confirmed, current, target in zip(sent[index], quantities, maximum)):
                raise FixedTransferUnsafe("Fixed transfer would exceed original authorized quantity")
            row = conn.execute(
                """INSERT INTO fixed_transfer_chunks(
                     transfer_id, route_index, cargo_json, status, updated_at)
                   VALUES(?,?,?,'pending',?) RETURNING chunk_id""",
                (self.transfer_id, index, json.dumps(quantities), time.time()),
            ).fetchone()
            conn.commit()
            return int(row["chunk_id"])

    def _transition(self, chunk_id, quantities, status):
        if status not in ("confirmed", "rejected"):
            raise FixedTransferUnsafe("Invalid transport receipt status")
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sent = self._verify(conn)
            row = conn.execute(
                """SELECT route_index,cargo_json,status FROM fixed_transfer_chunks
                   WHERE transfer_id=? AND chunk_id=?""",
                (self.transfer_id, chunk_id),
            ).fetchone()
            if (row is None or row["status"] != "pending"
                    or json.loads(row["cargo_json"]) != quantities):
                raise FixedTransferUnsafe("Transport receipt changed during dispatch")
            if status == "confirmed":
                index = row["route_index"]
                target = self.intent["routes"][index]["resources"]
                sent[index] = [a + b for a, b in zip(sent[index], quantities)]
                if any(a > b for a, b in zip(sent[index], target)):
                    raise FixedTransferUnsafe("Transport receipt exceeds approved quantity")
                fully_sent = all(
                    vec == route["resources"]
                    for vec, route in zip(sent, self.intent["routes"])
                )
                conn.execute(
                    """UPDATE fixed_transfers
                       SET dispatched_json=?,status=?,updated_at=?
                       WHERE transfer_id=?""",
                    (json.dumps(sent), "complete" if fully_sent else "running",
                     time.time(), self.transfer_id),
                )
            conn.execute(
                """UPDATE fixed_transfer_chunks SET status=?,updated_at=?
                   WHERE transfer_id=? AND chunk_id=? AND status='pending'""",
                (status, time.time(), self.transfer_id, chunk_id),
            )
            conn.commit()

    def confirmed(self, chunk_id, quantities):
        self._transition(chunk_id, quantities, "confirmed")

    def rejected(self, chunk_id, quantities):
        """Only call for a definitive server 'not dispatched' response."""
        self._transition(chunk_id, quantities, "rejected")
