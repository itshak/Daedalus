"""Synthetic automatic barbarian preset reviews; no live game requests."""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import autoBarbarians as grind

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_grind_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    session = Mock()
    state = {"level": 1, "ships": 100, "amount": 1000, "destroyed": 0}
    cities = {1: {"id": "1", "cityName": "Origin", "islandId": "10"},
              2: {"id": "2", "cityName": "Target", "islandId": "20"}}

    def own(_s, cid, _n):
        if cid not in cities:
            raise ValueError("Foreign city")
        return str(cid)

    monkeypatch.setattr(grind, "requireOwnCity", own)
    monkeypatch.setattr(grind, "getCityById", lambda _s, cid: cities[int(cid)])
    monkeypatch.setattr(grind, "getIsland", lambda _html: {
        "id": "20", "barbarians": {"destroyed": state["destroyed"]},
    })
    monkeypatch.setattr(grind, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(grind, "getAvailableShips", lambda _s: state["ships"])
    monkeypatch.setattr(grind, "get_barbarians_lv", lambda *_a: {
        "level": state["level"], "ships": 5, "resources": [100, 0, 0, 0, 0],
    })
    monkeypatch.setattr(grind, "telegramDataIsValid", lambda _s: False)
    monkeypatch.setattr(grind, "discordDataIsValid", lambda _s: False)

    def details(*_a, **_kw):
        required = grind.get_max_schematics_units(grind.DEFAULT_SCHEMATICS["WITHOUT_HEPHAESTUS"])["total"]
        return True, {
            "units_data": {k: {"name": "Unit " + k, "weight": 1, "speed": 1} for k in required},
            "main_city_units": {k: {"amount": state["amount"]} for k in required},
        }

    monkeypatch.setattr(grind, "get_schematic_information", details)
    return session, state


def test_grind_preview_and_native_handoff(monkeypatch):
    session, state = fixture(monkeypatch)
    draft = {"target_city_id": 2, "send_notifications": False}
    plan = grind.preview_native_grind(session, 1, **draft)
    assert plan["ready"] and plan["requirements"]
    assert validate_grind_plan(1, draft, plan)["config"] == plan["config"]
    assert not session.post.called
    state["amount"] = 0
    assert not grind.preview_native_grind(session, 1, **draft)["ready"]
    state["amount"] = 1000
    state["ships"] = 0
    assert not grind.preview_native_grind(session, 1, **draft)["ready"]
    state["ships"] = 100
    assert not grind.preview_native_grind(session, 1, 2, True)["ready"]
    state["level"] = 2
    with pytest.raises(ValueError, match="stale"):
        grind.prepare_native_grind(session, **plan["config"])
    state["level"] = 40
    with pytest.raises(ValueError, match="outside"):
        grind.preview_native_grind(session, 1, **draft)
    state["level"] = 1
    original = Mock()
    monkeypatch.setattr(grind.do_it, "__wrapped__", original)
    grind.native_grind.__wrapped__(session, **plan["config"])
    assert original.call_count == 1
    assert original.call_args.args[-1] is False
    assert restart_class_for("autoBarbarians", plan["config"]) == "manual"
    legacy = {"island": {}, "city": {}, "float_city": None, "schematic": [],
              "units_data": {}, "ship_capacity": 100}
    assert grind.prepare_native_grind(session, **legacy) == {**legacy, "send_notifications": True}
    grind.native_grind.__wrapped__(session, **legacy)
    assert original.call_count == 2


def test_grind_review_api_scope(monkeypatch, tmp_path):
    session, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(ipc, "_exchange", lambda p, **kw: {
        "status": "ok", "world": p["world"], "username": p["player"],
        "plan": grind.preview_native_grind(session, p["city_id"], p["target_city_id"], p["send_notifications"]),
    })
    monkeypatch.setattr(ipc, "preflight_task", lambda _a, task: {
        "task": task, "ready": True, "reason": "none", "notifications_required": False, "checked": [],
    })
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    starts = []

    def start(account, task, config, rid):
        starts.append((account.id, task, config, rid))
        return {"task_id": "a" * 24, "pid": 1234, "task": task, "status": "running"}

    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token, session_coordinator=owner,
                                   task_controller=controller, ipc_client=ipc))
    try:
        path = "/api/v1/accounts/alpha/cities/1/grind-plan"
        draft = {"target_city_id": 2, "send_notifications": False}
        assert client.post(path, headers=auth, json={**draft, "target_city_id": 3}).status_code == 422
        response = client.post(path, headers=auth, json=draft)
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/grind-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "autoBarbarians", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        assert not starts
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "autoBarbarians")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()
