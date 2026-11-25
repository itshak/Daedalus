"""Source-based synthetic reviewed construction supply tests."""
import copy
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import constructionList as engine
from ikabot.function import sendResources
from ikabot.helpers import taskConfig

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_construction_supply
from daedalus.task_control import TaskController, validated_configuration

UPGRADES = [{"position": 1, "target_level": 6}]
OPTIONS = {"source_ids": [2, 3], "round_up": True, "useFreighters": False, "supply_only": False}


@pytest.fixture
def game(monkeypatch):
    session = Mock()
    cities = {
        "1": {"id": "1", "name": "Target", "islandId": "40", "endUpgradeTime": 0,
              "availableResources": [250, 0, 30, 0, 0],
              "freeSpaceForResources": [1000]*5,
              "position": [{"position": 1, "name": "Town Hall", "building": "townHall",
                            "level": 5, "isBusy": False, "isMaxLevel": False}]},
        "2": {"id": "2", "name": "First", "availableResources": [400, 0, 150, 0, 0]},
        "3": {"id": "3", "name": "Second", "availableResources": [500, 0, 100, 0, 0]},
    }

    def own(_s, cid, _name):
        if str(cid) not in cities:
            raise ValueError("Foreign city")
        return str(cid)

    def costs(_s, _city, building, current, target, _reducers, **_kw):
        building["constructionTimes"] = [120]*(target-current)
        return [1000, 0, 200, 0, 0]

    monkeypatch.setattr(taskConfig, "requireOwnCity", own)
    monkeypatch.setattr(taskConfig, "getCityById", lambda _s,cid: cities[str(cid)])
    monkeypatch.setattr(engine, "getCity", lambda _html: cities["1"])
    monkeypatch.setattr(engine, "getCostsReducers", lambda _city: [0]*5)
    monkeypatch.setattr(engine, "getResourcesNeeded", costs)
    monkeypatch.setattr(sendResources, "getIdsOfCities", lambda _s: (list(cities), cities))
    monkeypatch.setattr(sendResources, "requireOwnCity", own)
    monkeypatch.setattr(sendResources, "getCityById", lambda _s,cid: cities[str(cid)])
    monkeypatch.setattr(sendResources, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(sendResources, "getAvailableShips", lambda _s: 2)
    monkeypatch.setattr(sendResources, "getTotalShips", lambda _s: 3)
    return session, cities


def test_exact_reviewed_supply_allocation_and_staleness(game):
    session, cities = game
    plan = engine.preview_native_construction(session, 1, UPGRADES, OPTIONS)
    assert plan["ready"] and plan["missing"] == [750, 0, 170, 0, 0]
    assert plan["config"]["shipments"] == [
        {"from": 2, "to": 1, "resources": [400, 0, 150, 0, 0]},
        {"from": 3, "to": 1, "resources": [400, 0, 50, 0, 0]}]
    validate_construction_supply(1, OPTIONS, plan, plan, plan["config"])
    validated_configuration(plan["config"])
    assert restart_class_for("constructionList", plan["config"]) == "manual"
    assert engine.prepare_constructionList(session, **plan["config"]) == plan["config"]
    wrong = copy.deepcopy(plan)
    wrong["supply"]["remaining"][0] = 1
    with pytest.raises(ValueError):
        validate_construction_supply(1, OPTIONS, wrong, wrong, wrong["config"])
    cities["2"]["availableResources"][0] = 399
    with pytest.raises(ValueError, match="stale"):
        engine.prepare_constructionList(session, **plan["config"])
    cities["1"]["freeSpaceForResources"][0] = 500
    insufficient = engine.preview_native_construction(session, 1, UPGRADES, OPTIONS)
    assert not insufficient["ready"] and insufficient["supply"]["remaining"][0] == 250
    with pytest.raises(ValueError, match="Foreign"):
        engine.preview_native_construction(session, 1, UPGRADES, {**OPTIONS, "source_ids": [4]})
    session.post.assert_not_called()


def test_supply_waits_for_actual_stock_and_halts_if_dispatch_uncertain(game, monkeypatch):
    session, cities = game
    plan = engine.preview_native_construction(session, 1, UPGRADES, OPTIONS)
    dispatch = Mock(side_effect=RuntimeError("Unknown outcome"))
    upgrade = Mock()
    monkeypatch.setattr(engine, "executeRoutes", dispatch)
    monkeypatch.setattr(engine, "expandBuilding", upgrade)
    with pytest.raises(RuntimeError, match="Unknown"):
        engine._run_supplied_construction(session, plan["config"])
    upgrade.assert_not_called()

    def arrive(_s, routes, useFreighters, verify_recipient):
        for i, route in enumerate(routes):
            verify_recipient(i)
            for j, amount in enumerate(route[3:]):
                cities["1"]["availableResources"][j] += amount

    def build(_s, city, building, wait_for_resources, queue, *, reviewed):
        assert city == "1" and reviewed and not wait_for_resources
        cities["1"]["position"][0]["level"] = building["upgradeTo"]

    monkeypatch.setattr(engine, "executeRoutes", arrive)
    monkeypatch.setattr(engine, "expandBuilding", build)
    engine._run_supplied_construction(session, plan["config"])
    assert cities["1"]["position"][0]["level"] == 6


def test_supply_only_never_upgrades(game, monkeypatch):
    session, _ = game
    plan = engine.preview_native_construction(session, 1, UPGRADES, {**OPTIONS, "supply_only": True})
    dispatch, upgrade = Mock(), Mock()
    monkeypatch.setattr(engine, "executeRoutes", dispatch)
    monkeypatch.setattr(engine, "expandBuilding", upgrade)
    engine._run_supplied_construction(session, plan["config"])
    dispatch.assert_called_once()
    upgrade.assert_not_called()


def test_controller_supply_ticket_and_owned_source_validation(game, monkeypatch, tmp_path):
    session, _ = game
    file = tmp_path/"accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path/"locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}, {"id": 2}, {"id": 3}])
    monkeypatch.setattr(ipc, "_exchange", lambda p, **_kw: {
        "world": p["world"], "username": p["player"], "city_id": p["city_id"],
        "plan": engine.preview_native_construction(session, p["city_id"], p["upgrades"], p.get("supply"))})
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    monkeypatch.setattr(ipc, "preflight_task", lambda _a, task: {
        "task": task, "ready": True, "reason": "none", "notifications_required": False, "checked": []})
    starts = Mock(return_value={"task_id": "a"*24, "pid": 1234, "task": "constructionList", "status": "running"})
    monkeypatch.setattr(ipc, "start_managed_task", starts)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path/"tasks.sqlite")
    token = "x"*48
    auth = {"Authorization": "Bearer "+token}
    client = TestClient(create_app(accounts_path=file, api_token=token, ipc_client=ipc,
                                   session_coordinator=owner, task_controller=controller))
    try:
        path = "/api/v1/accounts/alpha/cities/1/construction-plan"
        assert client.post(path, headers=auth, json={"upgrades": UPGRADES,
                           "supply": {**OPTIONS, "source_ids": [4]}}).status_code == 422
        reply = client.post(path, headers=auth, json={"upgrades": UPGRADES, "supply": OPTIONS})
        assert reply.status_code == 200, reply.text
        plan = reply.json()
        assert plan["ready"] and plan["preview_id"] and "config" not in plan
        starts.assert_not_called()
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "constructionList", "config": {"supply_review": {}},
            "confirmed": True, "request_id": str(uuid.uuid4())}).status_code == 422
        launch = {"confirmed": True, "preview_id": plan["preview_id"], "request_id": str(uuid.uuid4())}
        path = "/api/v1/accounts/alpha/tasks/construction-start"
        assert client.post(path, headers=auth, json=launch).status_code == 200
        assert client.post(path, headers=auth, json=launch).status_code == 200
        starts.assert_called_once()
    finally:
        controller.close()
