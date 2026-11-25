"""Durable server activity is scoped and bounded, never a raw log."""
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.activity_history import validate_activity_page
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.task_control import TaskController, TaskLedger


def test_old_ledger_migrates_without_inventing_timestamps(tmp_path):
    path = tmp_path / "old.sqlite"
    rid = str(uuid.uuid4())
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE requests(account_id TEXT, request_id TEXT, task TEXT, "
                     "payload_hash TEXT, status TEXT, engine_task_id TEXT, pid INTEGER, "
                     "PRIMARY KEY(account_id,request_id))")
        conn.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?)",
                     ("alpha", rid, "alertAttacks", "private", "started", "hidden", 1))
    ledger = TaskLedger(path)
    result = ledger.activity("alpha")
    assert result["events"] == [{"request_id": rid, "task": "alertAttacks", "status": "started",
                                 "created_at": None, "updated_at": None}]
    new = str(uuid.uuid4())
    ledger.reserve("alpha", new, "alertAttacks", "private")
    ledger.finish("alpha", new, status="unconfirmed")
    ledger.acknowledge("alpha", new)
    event = ledger.activity("alpha")["events"][0]
    assert event["created_at"] is not None and event["updated_at"] >= event["created_at"]
    assert event["status"] == "operator_reconciled"


def test_bounded_account_scoped_activity_without_worker(tmp_path):
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "A"\nenabled = false\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "B"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    path = tmp_path / "ledger.sqlite"
    controller = TaskController(accounts, owner, ControlledIPCClient(), ledger_path=path)
    ledger = TaskLedger(path)
    ids = []
    for i in range(4):
        rid = str(uuid.uuid4())
        ids.append(rid)
        ledger.reserve("alpha", rid, "alertAttacks", "never expose")
        ledger.finish("alpha", rid, status="started" if i%2==0 else "unconfirmed")
        ledger.reserve("beta", str(uuid.uuid4()), "alertAttacks", "private")
    token = "x"*48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token,
                                   task_controller=controller, session_coordinator=owner))
    try:
        endpoint = "/api/v1/accounts/alpha/activity"
        assert client.get(endpoint).status_code == 401
        first = client.get(endpoint+"?limit=2", headers=auth).json()
        assert validate_activity_page(first, "alpha", None, 2, "all") == first
        assert [r["request_id"] for r in first["events"]] == ids[:1:-1]
        second = client.get(endpoint+f"?limit=2&before={first['next_before']}", headers=auth).json()
        assert [r["request_id"] for r in second["events"]] == ids[1::-1]
        assert second["next_before"] is None
        filtered = client.get(endpoint+"?status=unconfirmed", headers=auth).json()
        assert [r["request_id"] for r in filtered["events"]] == ids[3::-2]
        assert "never expose" not in str(first)
        for query in ["?limit=101", "?before=0", "?status=bogus"]:
            assert client.get(endpoint+query, headers=auth).status_code == 422
        assert client.get(endpoint.replace("alpha","missing"), headers=auth).status_code == 404
        with pytest.raises(ValueError):
            validate_activity_page(first, "beta", None, 2, "all")
    finally:
        controller.close()
