"""Synthetic new-building inventory and reviewed mutation checks."""
import json
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import constructBuilding as building

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_build_inventory, validate_build_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    city = {"id": "1", "cityName": "Town", "availableResources": [100, 0, 0, 0, 0],
            "position": [{"position": 1, "building": "empty", "type": "land"}]}
    session = Mock()
    cost = [20]
    def own(_session, cid, _name):
        if cid != 1:
            raise ValueError("Foreign city")
        return "1"
    monkeypatch.setattr(building, "requireOwnCity", own)
    monkeypatch.setattr(building, "getCityById", lambda _s, _cid: city)
    def post(**kwargs):
        if kwargs["params"].get("view") == "buildingGround":
            markup = ('<li class="building academy"><div title="Academy" class="buildingimg academy" '
                      'onclick="ajaxHandlerCall(\'buildingId=4&foo=1\')"></div>'
                      f'<li class="wood" title="Wood: {cost[0]}"></li></li>')
            return json.dumps([["updateGlobalData", {"actionRequest": "test-only"}],
                               ["update", ["buildingGround", markup]]])
        return "submitted"
    session.post.side_effect = post
    return session, city, cost


def test_build_ground_choices_review_staleness_and_single_attempt(monkeypatch):
    session, city, cost = fixture(monkeypatch)
    data = building.native_build_options(session, 1)
    assert data["options"][0]["name"] == "Academy"
    assert data["options"][0]["costs"] == [20, 0, 0, 0, 0]
    assert validate_build_inventory(1, data)["options"] == data["options"]
    plan = building.preview_native_build(session, 1, 1, 4)
    assert plan["ready"] and plan["missing"] == [0] * 5
    assert validate_build_plan(1, {"position": 1, "building_id": 4}, plan)["config"] == plan["config"]
    assert not any("action" in call.kwargs["params"] for call in session.post.call_args_list)
    cost[0] = 21
    with pytest.raises(ValueError, match="stale"):
        building.prepare_native_build(session, **plan["config"])
    cost[0] = 20
    city["availableResources"][0] = 10
    assert not building.preview_native_build(session, 1, 1, 4)["ready"]
    city["availableResources"][0] = 100
    with pytest.raises(ValueError):
        building.preview_native_build(session, 1, 2, 4)
    with pytest.raises(ValueError):
        building.preview_native_build(session, 2, 1, 4)
    building.native_build(session, **plan["config"])
    mutations = [c.kwargs for c in session.post.call_args_list if "action" in c.kwargs["params"]]
    assert len(mutations) == 1
    assert mutations[0]["params"]["action"] == "BuildNewBuilding"
    assert mutations[0]["retry_on_failure"] is False
    assert restart_class_for("constructBuilding", plan["config"]) == "manual"


def test_build_ticket_api_scope_no_generic_launch(monkeypatch, tmp_path):
    session, _, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}])
    def exchange(payload, **kwargs):
        result = {"status": "ok", "world": payload["world"], "username": payload["player"]}
        if payload["action"] == "list_build_options_existing":
            return {**result, "inventory": building.native_build_options(session, payload["city_id"])}
        return {**result, "plan": building.preview_native_build(session, payload["city_id"],
                                                                payload["position"], payload["building_id"])}
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
        options = client.get(path + "/build-options", headers=auth)
        assert options.status_code == 200, options.text
        assert options.json()["options"][0]["building_id"] == 4
        assert client.post(path + "/build-plan", headers=auth, json={"position": True, "building_id": 4}).status_code == 422
        plan = client.post(path + "/build-plan", headers=auth, json={"position": 1, "building_id": 4})
        assert plan.status_code == 200, plan.text
        plan = plan.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/build-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "constructBuilding", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        assert not starts
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "constructBuilding")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()
