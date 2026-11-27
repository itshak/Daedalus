"""Durable staged production receipts; incomplete runs are never replayed."""
import json
import os
import time
from pathlib import Path

from ikabot.helpers.fixedTransferJournal import FixedTransferJournal, _verified_uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ProductionJournal:
    _db = FixedTransferJournal._db

    def __init__(self, session, run_id, plans, *, db_path=None):
        self.run_id = _verified_uuid(run_id)
        self.world = f"s{session.mundo}-{session.servidor}".casefold()
        self.player = session.username.casefold()
        self.intent = canonical(plans)
        path = db_path or os.environ.get("DAEDALUS_FIXED_TRANSFER_DB")
        if not path:
            raise ValueError("Protected production journal is not configured")
        self.path = Path(path).expanduser()
        with self._db() as conn:
            self._verify(conn)

    def _verify(self, conn):
        row = conn.execute("SELECT * FROM production_runs WHERE run_id=?", (self.run_id,)).fetchone()
        if (row is None or row["world"] != self.world or row["player"] != self.player
                or row["intent_json"] != self.intent or row["status"] != "prepared"):
            raise ValueError("Production run not approved or already resolved")

    def _member(self, conn, plan):
        self._verify(conn)
        if canonical(plan) not in {canonical(x) for x in json.loads(self.intent)}:
            raise ValueError("City is not part of the approved production run")

    def _city(self, conn, plan):
        self._member(conn, plan)
        row = conn.execute("SELECT * FROM production_cities WHERE run_id=? AND city_id=?",
                           (self.run_id, plan["city_id"])).fetchone()
        if row is None or row["status"] != "running":
            raise ValueError("Production city is not active")

    def begin_city(self, plan):
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._member(conn, plan)
            if conn.execute("SELECT 1 FROM production_cities WHERE run_id=? AND status='running'",
                            (self.run_id,)).fetchone():
                raise ValueError("Incomplete production city needs review")
            if conn.execute("SELECT 1 FROM production_cities WHERE run_id=? AND city_id=?",
                            (self.run_id, plan["city_id"])).fetchone():
                raise ValueError("Production city was already attempted")
            conn.execute("INSERT INTO production_cities(run_id,city_id,status) VALUES(?,?,'running')",
                         (self.run_id, plan["city_id"]))
            conn.commit()

    def reserve(self, plan, stage, kind, value):
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._city(conn, plan)
            rows = conn.execute("SELECT stage,status FROM production_stages WHERE run_id=? AND city_id=?",
                                (self.run_id, plan["city_id"])).fetchall()
            prior = {r["stage"]: r["status"] for r in rows}
            order = {"release": 0, "target": 1, "restore": 2, "secondary": 2}
            if (stage not in order or stage in prior or any(v != "confirmed" for v in prior.values())
                    or any(order[k] >= order[stage] for k in prior)
                    or kind != plan["target_kind" if stage == "target" else "donor_kind"]
                    or type(value) is not int or not 0 <= value <= 2_000_000
                    or (stage == "release" and (not plan["donor_release"] or
                        value != plan["donor_before"] - plan["donor_release"]))
                    or (stage == "target" and (value > plan["desired"] or (plan["target_after"] is not None and value > plan["target_after"]) or
                        plan["donor_release"] and "release" not in prior))
                    or (stage == "secondary" and (not plan["draft"].get("fill_both") or
                        not plan["donor_before"] - plan["donor_release"] <= value <= plan["donor_after"] or
                        (plan["donor_release"] and "release" not in prior)))
                    or (stage == "restore" and (plan["draft"].get("fill_both") or "release" not in prior or
                        not plan["donor_before"] - plan["donor_release"] <= value <= plan["donor_before"]))):
                raise ValueError("Unsafe production stage")
            conn.execute("""INSERT INTO production_stages
                (run_id,city_id,stage,kind,value,status,updated_at)
                VALUES(?,?,?,?,?,'pending',?)""",
                (self.run_id, plan["city_id"], stage, kind, value, time.time()))
            conn.commit()

    def confirm(self, plan, stage, observed):
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._city(conn, plan)
            changed = conn.execute("""UPDATE production_stages SET status='confirmed',
                observation_json=?,updated_at=? WHERE run_id=? AND city_id=? AND stage=? AND status='pending'""",
                (canonical(observed), time.time(), self.run_id, plan["city_id"], stage)).rowcount
            if changed != 1:
                raise ValueError("Production receipt is not pending")
            conn.commit()

    def complete_city(self, plan, result):
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._city(conn, plan)
            if conn.execute("""SELECT 1 FROM production_stages WHERE run_id=? AND city_id=?
                AND status='pending'""", (self.run_id, plan["city_id"])).fetchone():
                raise ValueError("Production mutation still pending")
            conn.execute("UPDATE production_cities SET status='complete',result_json=? WHERE run_id=? AND city_id=?",
                         (canonical(result), self.run_id, plan["city_id"]))
            conn.commit()

    def skip_stale(self, plan):
        """Record a pre-mutation stale city; never skip an already started city."""
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._member(conn, plan)
            conn.execute("INSERT INTO production_cities(run_id,city_id,status) VALUES(?,?,'stale')",
                         (self.run_id, plan["city_id"]))
            conn.commit()

    def finish(self):
        with self._db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._verify(conn)
            rows = conn.execute("SELECT status FROM production_cities WHERE run_id=?", (self.run_id,)).fetchall()
            if len(rows) != len(json.loads(self.intent)) or any(r[0] not in ("complete", "stale") for r in rows):
                raise ValueError("Production still needs review")
            status = "partial" if any(r[0] == "stale" for r in rows) else "complete"
            conn.execute("UPDATE production_runs SET status=?,updated_at=? WHERE run_id=?",
                         (status, time.time(), self.run_id))
            conn.commit()
