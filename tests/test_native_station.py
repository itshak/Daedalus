"""Synthetic owned-city deployment, never a real game request."""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import stationArmy as station

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_station_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    session = Mock()
    quantities = [5]
    capacity = [10]
    cities = {1: {"id": "1", "cityName": "Origin", "islandId": "10"},
              2: {"id": "2", "cityName": "Destination", "islandId": "20"}}
    def own(_s, cid, _n):
        if cid not in cities:
            raise ValueError("Foreign city")
        return str(cid)
    monkeypatch.setattr(station, "requireOwnCity", own)
    monkeypatch.setattr(station, "getCityById", lambda _s, cid: cities[int(cid)])
    monkeypatch.setattr(station, "getShipCapacity", lambda _s: (capacity[0], 100))
    monkeypatch.setattr(station, "getAvailableShips", lambda _s: 2)
    def post(**kwargs):
        p = kwargs["params"]
        if p.get("view") == "deployment":
            mode = p["deploymentType"]
            return (
                r'<div class=\"amount\">' + str(quantities[0]) + r'<\/div>'
                + r'name=\"cargo_' + mode + r'_301_upkeep\"\n   value=\"3\"'
                + r'<div class=\"weight\">2<\/div>'
            )
        return "submitted"
    session.post.side_effect = post
    return session, quantities, capacity


@pytest.mark.parametrize("ground", [True, False])
def test_station_scope_capacity_stale_and_one_attempt(monkeypatch, ground):
    session, quantities, capacity = fixture(monkeypatch)
    plan = station.preview_native_station(session, 1, 2, ground)
    assert plan["ready"] and plan["total"] == 5
    assert plan["weight"] == (10 if ground else None)
    assert plan["capacity"] == (20 if ground else None)
    assert validate_station_plan(1, {"destination_city_id": 2, "ground": ground}, plan)["config"] == plan["config"]
    quantities[0] = 6
    with pytest.raises(ValueError, match="stale"):
        station.prepare_native_station(session, **plan["config"])
    quantities[0] = 5
    if ground:
        capacity[0] = 2
        assert not station.preview_native_station(session, 1, 2, ground)["ready"]
        capacity[0] = 10
    with pytest.raises(ValueError):
        station.preview_native_station(session, 1, 1, ground)
    with pytest.raises(ValueError):
        station.preview_native_station(session, 1, 3, ground)
    assert not any("action" in c.kwargs["params"] for c in session.post.call_args_list)
    station.native_station(session, **plan["config"])
    mutations = [c.kwargs for c in session.post.call_args_list if "action" in c.kwargs["params"]]
    assert len(mutations) == 1
    assert mutations[0]["retry_on_failure"] is False
    assert mutations[0]["params"]["function"] == ("deployArmy" if ground else "deployFleet")
    assert restart_class_for("stationArmy", plan["config"]) == "manual"


def test_station_ticket_scope_and_no_generic_start(monkeypatch, tmp_path):
    session, _, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(station, "getIdsOfCities", lambda _s: (["1", "2"], {}))
    monkeypatch.setattr(ipc, "_exchange", lambda p, **kw: {
        "status": "ok", "world": p["world"], "username": p["player"],
        "plan": station.preview_native_station(session, p["city_id"], p["destination_city_id"], p["ground"],
                                               p.get("all_origins", False), p.get("both", False)),
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
        path = "/api/v1/accounts/alpha/cities/1/station-plan"
        draft = {"destination_city_id": 2, "ground": True}
        assert client.post(path, headers=auth, json={**draft, "destination_city_id": 3}).status_code == 422
        assert client.post(path, headers=auth, json={**draft, "ground": 1}).status_code == 422
        assert client.post(path, headers=auth, json={**draft, "both": True, "ground": False}).status_code == 422
        assert client.post(path, headers=auth, json={**draft, "all_origins": 1}).status_code == 422
        aggregate = client.post(path, headers=auth, json={**draft, "all_origins": True, "both": True})
        assert aggregate.status_code == 200, aggregate.text
        assert aggregate.json()["total"] == 10 and len(aggregate.json()["deployments"]) == 2
        response = client.post(path, headers=auth, json=draft)
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/station-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "stationArmy", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        assert not starts
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "stationArmy")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()


def test_all_city_combined_deployment_checks_shared_capacity_and_staleness(monkeypatch):
    session, quantities, capacity = fixture(monkeypatch)
    origin2 = {"id": "3", "cityName": "Another source", "islandId": "30"}
    original_get = station.getCityById
    original_own = station.requireOwnCity
    monkeypatch.setattr(station, "getCityById", lambda s, cid:
                        origin2 if int(cid) == 3 else original_get(s, cid))
    monkeypatch.setattr(station, "requireOwnCity", lambda s, cid, n:
                        "3" if cid == 3 else original_own(s, cid, n))
    monkeypatch.setattr(station, "getIdsOfCities", lambda _s: (["1", "2", "3"], {}))
    draft = {"destination_city_id": 2, "ground": True, "all_origins": True, "both": True}
    plan = station.preview_native_station(session, 1, **draft)
    assert plan["total"] == 20 and plan["weight"] == plan["capacity"] == 20
    assert len(plan["deployments"]) == 4 and plan["ready"]
    assert validate_station_plan(1, draft, plan)["config"] == plan["config"]
    capacity[0] = 9
    assert not station.preview_native_station(session, 1, **draft)["ready"]
    capacity[0] = 10
    quantities[0] = 6
    with pytest.raises(ValueError, match="stale"):
        station.prepare_native_station(session, **plan["config"])
    quantities[0] = 5
    assert not any("action" in c.kwargs["params"] for c in session.post.call_args_list)
    station.native_station(session, **plan["config"])
    writes = [c.kwargs for c in session.post.call_args_list if "action" in c.kwargs["params"]]
    assert [(w["params"]["currentCityId"], w["params"]["function"]) for w in writes] == [
        ("1", "deployArmy"), ("1", "deployFleet"), ("3", "deployArmy"), ("3", "deployFleet")]
    assert all(w["retry_on_failure"] is False for w in writes)


def test_combined_deployment_stops_remaining_routes_on_change(monkeypatch):
    session, quantities, _ = fixture(monkeypatch)
    draft = {"destination_city_id": 2, "ground": True, "both": True}
    plan = station.preview_native_station(session, 1, **draft)
    original_post = session.post.side_effect

    def post(**kwargs):
        reply = original_post(**kwargs)
        if kwargs["params"].get("action") == "transportOperations":
            quantities[0] = 4
        return reply

    session.post.side_effect = post
    # Exercise the underlying task function: the decorator handles task errors.
    with pytest.raises(ValueError, match="changed"):
        station.native_station.__wrapped__(session, **plan["config"])
    writes = [c.kwargs for c in session.post.call_args_list if "action" in c.kwargs["params"]]
    assert len(writes) == 1
