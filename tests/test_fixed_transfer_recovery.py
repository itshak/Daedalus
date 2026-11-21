"""Fixed-quantity transfer is a dispatch-target, never a replay of old cargo."""
from __future__ import annotations

import json
import sqlite3
from uuid import uuid4

import pytest

from daedalus.accounts import Account
from daedalus.recovery_reconcile import (
    canonical_fixed_transfer,
    fixed_transfer_plan,
    restart_class_for,
)
from daedalus.recovery_state import RecoveryConflict, RecoveryStore

ACCOUNT = Account("fixed-a", "s53-ru", "captain", "Captain", True)


def config():
    return {
        "routes": [
            {"from": 101, "to": 102, "resources": [75, 10, 0, 0, 0]},
            {"from": 102, "to": 103, "resources": [0, 0, 20, 0, 0]},
        ],
        "useFreighters": False,
        "transfer_id": str(uuid4()),
    }


def prepare(tmp_path):
    db = RecoveryStore(tmp_path / "recovery.sqlite3")
    job = config()
    db.prepare_fixed_transfer(ACCOUNT, job)
    return db, job


def test_prepared_target_is_private_and_not_automatically_replayed(tmp_path):
    db, job = prepare(tmp_path)
    assert restart_class_for("sendResources", job) == "fixed_transfer"
    assert db.desired(ACCOUNT)[0]["desired_state"] == "dispatching"
    assert db.fixed_transfer_progress(ACCOUNT, job)["remaining"] == [
        [75, 10, 0, 0, 0], [0, 0, 20, 0, 0]
    ]
    assert db.begin_resume(ACCOUNT, job["transfer_id"], "new-epoch") is None
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_confirmed_dispatch_subtracted_but_pending_chunk_blocks_auto_resume(tmp_path):
    db, job = prepare(tmp_path)
    db.finish_fixed_transfer(ACCOUNT, job["transfer_id"], status="started", task_id="old")
    with sqlite3.connect(db.path) as conn:
        conn.execute("""UPDATE fixed_transfers SET dispatched_json=?
            WHERE transfer_id=?""", (json.dumps([[40, 10, 0, 0, 0], [0, 0, 0, 0, 0]]),
                                   job["transfer_id"]))
        conn.execute("""INSERT INTO fixed_transfer_chunks(
            transfer_id,route_index,cargo_json,status,updated_at)
            VALUES(?,?,?,'pending',?)""", (job["transfer_id"], 0,
                                          json.dumps([35, 0, 0, 0, 0]), 123))
    progress = db.fixed_transfer_progress(ACCOUNT, job)
    assert progress["remaining"][0] == [35, 0, 0, 0, 0]
    assert progress["uncertain"] is True
    class IPC:
        def cities(self, _):
            return [{"id": 101}, {"id": 102}, {"id": 103}]
    plan = fixed_transfer_plan(db, IPC(), ACCOUNT, job)
    assert (plan.state, plan.reason) == ("review", "fixed_transfer_uncertain")


def test_fully_acknowledged_original_quantity_is_completed(tmp_path):
    db, job = prepare(tmp_path)
    db.finish_fixed_transfer(ACCOUNT, job["transfer_id"], status="started", task_id="old")
    with sqlite3.connect(db.path) as conn:
        conn.execute("""UPDATE fixed_transfers SET dispatched_json=?,status='complete'
            WHERE transfer_id=?""", (json.dumps([
                [75, 10, 0, 0, 0], [0, 0, 20, 0, 0]
            ]), job["transfer_id"]))
    class IPC:
        def cities(self, _):
            return [{"id": 101}, {"id": 102}, {"id": 103}]
    assert fixed_transfer_plan(db, IPC(), ACCOUNT, job).state == "completed"
    record = db.desired(ACCOUNT)[0]
    assert db.complete_job(ACCOUNT, record["id"], revision=record["revision"])
    assert db.desired(ACCOUNT)[0]["desired_state"] == "completed"


def test_unconfirmed_launch_or_explicit_stop_prevents_further_transport(tmp_path):
    db, job = prepare(tmp_path)
    db.finish_fixed_transfer(ACCOUNT, job["transfer_id"], status="unconfirmed")
    assert db.desired(ACCOUNT)[0]["desired_state"] == "review"
    assert db.fixed_transfer_progress(ACCOUNT, job)["uncertain"]
    other = config()
    db.prepare_fixed_transfer(ACCOUNT, other)
    db.finish_fixed_transfer(ACCOUNT, other["transfer_id"],
                             status="started", task_id="old-id")
    assert db.stop_task(ACCOUNT, "old-id") == 1
    assert db.fixed_transfer_progress(ACCOUNT, other)["uncertain"]


def test_fixed_transfer_is_owned_city_only_and_server_generated():
    original = config()
    assert canonical_fixed_transfer(original) is not None
    original["routes"][0]["island"] = "120"
    assert restart_class_for("sendResources", original) == "manual"
    original["routes"][0].pop("island")
    original["transfer_id"] = "nonuuid"
    assert restart_class_for("sendResources", original) == "manual"


def test_job_collision_and_wrong_identity_fail_closed(tmp_path):
    db, job = prepare(tmp_path)
    with pytest.raises(RecoveryConflict):
        db.prepare_fixed_transfer(ACCOUNT, job)
    mismatched = Account(ACCOUNT.id, ACCOUNT.world, "someone-else", "Other", True)
    with pytest.raises(RecoveryConflict):
        db.fixed_transfer_progress(mismatched, job)


def test_database_schema_migrates_v1_without_losing_existing_job(tmp_path):
    path = tmp_path / "recovery.sqlite3"
    db = RecoveryStore(path)
    db.capture_started(ACCOUNT, "alertAttacks", {"listen": True}, "old")
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=1")
        conn.execute("DROP TABLE fixed_transfer_chunks")
        conn.execute("DROP TABLE fixed_transfers")
    upgraded = RecoveryStore(path)
    assert upgraded.desired(ACCOUNT)[0]["task"] == "alertAttacks"
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
