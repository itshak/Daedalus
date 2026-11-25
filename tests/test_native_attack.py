"""Synthetic manual barbarian wave contracts; no actual game requests."""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import attackBarbarians as attack

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_attack_inventory, validate_attack_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    session = Mock()
    state = {"level": 1, "ships": 100, "amount": 100, "destroyed": 0}
    cities = {1: {"id": "1", "cityName": "Origin", "islandId": "10", "x": 1, "y": 1},
              2: {"id": "2", "cityName": "Target", "islandId": "20", "x": 2, "y": 2}}

    def own(_s, cid, _n):
        if cid not in cities:
            raise ValueError("Foreign city")
        return str(cid)

    monkeypatch.setattr(attack, "requireOwnCity", own)
    monkeypatch.setattr(attack, "getCityById", lambda _s, cid: cities[int(cid)])
    monkeypatch.setattr(attack, "getIsland", lambda _html: {
        "id": "20", "x": 2, "y": 2, "barbarians": {"destroyed": state["destroyed"]},
    })
    monkeypatch.setattr(attack, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(attack, "getAvailableShips", lambda _s: state["ships"])
    monkeypatch.setattr(attack, "get_barbarians_lv", lambda *_a: {
        "level": state["level"], "ships": 5, "resources": [100, 0, 0, 0, 0],
    })
    monkeypatch.setattr(attack, "get_units", lambda *_a: {
        "302": {"name": "Unit", "amount": state["amount"]},
    })
    monkeypatch.setattr(attack, "get_unit_data", lambda *_a: {"name": "Unit", "weight": 2, "speed": 1})
    return session, state


def draft():
    return {"target_city_id": 2, "waves": [
        {"round": 1, "loot": False, "ships": 2, "units": {"302": 30}},
        {"round": 2, "loot": True, "ships": 0, "units": {"302": 10}},
    ]}


def test_manual_attack_preview_and_native_handoff(monkeypatch):
    session, state = fixture(monkeypatch)
    options = attack.native_attack_inventory(session, 1)
    assert validate_attack_inventory(1, options)["units"][0]["available"] == 100
    plan = attack.preview_native_attack(session, 1, **draft())
    assert plan["ready"] and plan["required_ships"] == 4
    assert validate_attack_plan(1, draft(), plan)["config"] == plan["config"]
    assert not session.post.called
    state["amount"] = 35
    assert not attack.preview_native_attack(session, 1, **draft())["ready"]
    state["amount"] = 100
    state["ships"] = 3
    assert not attack.preview_native_attack(session, 1, **draft())["ready"]
    state["ships"] = 100
    state["level"] = 2
    with pytest.raises(ValueError, match="stale"):
        attack.prepare_native_attack(session, **plan["config"])
    state["level"] = 1
    invalid = draft()
    invalid["waves"][1]["round"] = 1
    with pytest.raises(ValueError):
        attack.preview_native_attack(session, 1, **invalid)
    invalid = draft()
    invalid["waves"][0]["units"] = {"999": 1}
    with pytest.raises(ValueError):
        attack.preview_native_attack(session, 1, **invalid)
    original = Mock()
    monkeypatch.setattr(attack.do_it, "__wrapped__", original)
    attack.native_attack.__wrapped__(session, **plan["config"])
    assert original.call_count == 1
    assert original.call_args.kwargs["strict_review"] is True
    assert restart_class_for("attackBarbarians", plan["config"]) == "manual"
    legacy = {"island": {}, "city": {}, "babarians_info": {}, "plan": [], "ship_capacity": 100}
    assert attack.prepare_native_attack(session, **legacy) == legacy
    attack.native_attack.__wrapped__(session, **legacy)
    assert original.call_count == 2


def test_manual_attack_api_inventory_and_scope(monkeypatch, tmp_path):
    session, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}, {"id": 2}])

    def exchange(p, **_kw):
        data = {"status": "ok", "world": p["world"], "username": p["player"]}
        if p["action"] == "list_attack_units_existing":
            return {**data, "inventory": attack.native_attack_inventory(session, p["city_id"])}
        return {**data, "plan": attack.preview_native_attack(session, p["city_id"], p["target_city_id"], p["waves"])}

    monkeypatch.setattr(ipc, "_exchange", exchange)
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
        path = "/api/v1/accounts/alpha/cities/1"
        assert client.get(path + "/attack-options", headers=auth).json()["units"][0]["unit_id"] == "302"
        assert client.post(path + "/attack-plan", headers=auth, json={**draft(), "target_city_id": 3}).status_code == 422
        response = client.post(path + "/attack-plan", headers=auth, json=draft())
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/attack-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "attackBarbarians", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        assert not starts
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "attackBarbarians")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()
