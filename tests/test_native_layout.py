"""Synthetic layout checks; no live city mutations."""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import reorganizeCityBuildings as layouts

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import validate_layout_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    def city(cid, buildings):
        return {"id": str(cid), "cityName": f"City {cid}", "position": [
            {"position": i, "building": b, "level": 1, "isBusy": False}
            for i, b in enumerate(buildings)
        ]}
    cities = {1: city(1, ["townHall", "academy", "warehouse"]),
              2: city(2, ["townHall", "warehouse", "academy"])}
    def own(_session, cid, _name):
        if cid not in cities:
            raise ValueError("Foreign city")
        return str(cid)
    monkeypatch.setattr(layouts, "requireOwnCity", own)
    monkeypatch.setattr(layouts, "getCityById", lambda _s, cid: cities[int(cid)])
    return Mock(), cities


def test_layout_preview_stale_busy_and_single_attempt(monkeypatch):
    session, cities = fixture(monkeypatch)
    plan = layouts.preview_native_layout(session, 1, 2)
    assert plan["ready"] and len(plan["moves"]) == 1
    assert validate_layout_plan(1, 2, plan)["config"] == plan["config"]
    assert not session.post.called
    cities[1]["position"][1]["level"] = 2
    with pytest.raises(ValueError, match="stale"):
        layouts.prepare_native_layout(session, **plan["config"])
    cities[1]["position"][1]["level"] = 1
    cities[1]["position"][1]["isBusy"] = True
    with pytest.raises(ValueError, match="busy"):
        layouts.preview_native_layout(session, 1, 2)
    cities[1]["position"][1]["isBusy"] = False
    with pytest.raises(ValueError):
        layouts.preview_native_layout(session, 1, 3)
    with pytest.raises(ValueError):
        layouts.preview_native_layout(session, 1, 1)
    layouts.native_layout(session, **plan["config"])
    mutations = [call for call in session.post.call_args_list if "params" in call.kwargs]
    assert len(mutations) == 1
    assert mutations[0].kwargs["retry_on_failure"] is False
    assert mutations[0].kwargs["params"]["cityId"] == "1"
    assert restart_class_for("reorganizeCityBuildings", plan["config"]) == "manual"


def test_layout_no_applicable_swaps(monkeypatch):
    session, cities = fixture(monkeypatch)
    cities[2]["position"] = cities[1]["position"]
    plan = layouts.preview_native_layout(session, 1, 2)
    assert plan["ready"] is False and plan["moves"] == []
    with pytest.raises(ValueError):
        layouts.prepare_native_layout(session, **plan["config"])
    assert not session.post.called


def test_layout_ticket_account_scope_and_no_generic_launch(monkeypatch, tmp_path):
    session, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(ipc, "_exchange", lambda payload, **kwargs: {
        "status": "ok", "world": payload["world"], "username": payload["player"],
        "plan": layouts.preview_native_layout(session, payload["city_id"], payload["template_city_id"]),
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
        path = "/api/v1/accounts/alpha/cities/1/layout-plan"
        assert client.post(path, json={"template_city_id": 2}).status_code == 401
        assert client.post(path, headers=auth, json={"template_city_id": 1}).status_code == 422
        assert client.post(path, headers=auth, json={"template_city_id": 3}).status_code == 422
        plan = client.post(path, headers=auth, json={"template_city_id": 2})
        assert plan.status_code == 200, plan.text
        plan = plan.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/layout-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "reorganizeCityBuildings", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        assert not starts
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "reorganizeCityBuildings")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()
