"""Source-derived, synthetic worker assignment contracts."""
import json
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import modifyProduction as workers

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.reviewed_operations import WORKER_TASKS, validate_worker_plan, validated_worker_draft
from daedalus.task_control import TaskController


def fake_game(monkeypatch):
    slider = {"max_value": 100, "overcharge": 20, "value": 25}
    city = {"id": "1", "islandId": "99", "name": "Town", "position": [
        {"building": "academy", "position": 2},
        {"building": "temple", "position": 3},
    ]}
    session = Mock()

    def own(s, city_id, name):
        if city_id != 1:
            raise ValueError("Foreign city")
        return str(city_id)

    monkeypatch.setattr(workers, "requireOwnCity", own)
    monkeypatch.setattr(workers, "getCityById", lambda s, city_id: city)

    def post(url="", **kwargs):
        if kwargs:
            return "submitted"
        return json.dumps([[], [], ["update", {
            "js_ResourceSlider": {"slider": slider},
            "js_AcademySlider": {"slider": slider},
            "js_TempleSlider": {"slider": slider},
        }]])

    session.post.side_effect = post
    return session, slider, city


@pytest.mark.parametrize("task,options,expected,mutation_key", [
    ("modifyProduction", {"project": "resource", "overcharge": True}, 120, "rw"),
    ("modifyProduction", {"project": "tradegood", "overcharge": False}, 100, "tw"),
    ("modifyAcademyWorkers", {}, 100, "s"),
    ("modifyTempleWorkers", {}, 100, "priests"),
])
def test_workers_preview_and_one_attempt(monkeypatch, task, options, expected, mutation_key):
    session, slider, _ = fake_game(monkeypatch)
    plan = workers.preview_native_workers(session, task, 1, 100, **options)
    assert plan["target"] == expected and plan["current"] == 25
    assert not any(call.kwargs for call in session.post.call_args_list)
    clean = validated_worker_draft(task, {"percentage": 100, **options})
    assert validate_worker_plan(task, 1, clean, plan)["config"] == plan["config"]
    slider["max_value"] = 101
    with pytest.raises(ValueError, match="stale"):
        workers.prepare_native_workers(session, task, **plan["config"])
    assert not any(call.kwargs for call in session.post.call_args_list)
    slider["max_value"] = 100
    workers.execute_native_workers(session, task, **plan["config"])
    mutations = [call.kwargs for call in session.post.call_args_list if call.kwargs]
    assert len(mutations) == 1
    assert mutations[0]["retry_on_failure"] is False
    assert mutations[0]["params"][mutation_key] == expected
    assert mutations[0]["params"]["cityId"] == "1"
    assert restart_class_for(task, plan["config"]) == "manual"


def test_worker_unknown_current_and_missing_building(monkeypatch):
    session, slider, city = fake_game(monkeypatch)
    slider.pop("value")
    plan = workers.preview_native_workers(session, "modifyAcademyWorkers", 1, 0)
    assert plan["current"] is None and plan["target"] == 0
    city["position"] = []
    with pytest.raises(ValueError):
        workers.preview_native_workers(session, "modifyTempleWorkers", 1, 50)
    with pytest.raises(ValueError):
        workers.preview_native_workers(session, "modifyProduction", 1, 50, "resource", True)
    with pytest.raises(ValueError):
        workers.preview_native_workers(session, "modifyAcademyWorkers", 2, 50)
    with pytest.raises(ValueError):
        validated_worker_draft("modifyTempleWorkers", {"percentage": True})
    with pytest.raises(ValueError):
        validated_worker_draft("modifyProduction", {"percentage": 0, "project": "resource",
                                                    "overcharge": True})


def test_worker_reviewed_api_and_cross_operation_scope(monkeypatch, tmp_path):
    session, _, _ = fake_game(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
        '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n'
    )
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    starts = []
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda account: [{"id": 1, "name": "Town"}])
    monkeypatch.setattr(ipc, "_exchange", lambda payload, **kwargs: {
        "status": "ok", "world": payload["world"], "username": payload["player"],
        "plan": workers.preview_native_workers(
            session, payload["task"], payload["city_id"], payload["percentage"],
            payload.get("project"), payload.get("overcharge", False)),
    })
    monkeypatch.setattr(ipc, "preflight_task", lambda account, task: {
        "task": task, "ready": True, "reason": "none",
        "notifications_required": False, "checked": [],
    })
    monkeypatch.setattr(ipc, "has_account", lambda account: True)

    def start(account, task, config, rid):
        starts.append((account.id, task, config, rid))
        return {"task_id": "a" * 24, "pid": 1234, "task": task, "status": "running"}

    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token,
                                   session_coordinator=owner, task_controller=controller,
                                   ipc_client=ipc))
    try:
        path = "/api/v1/accounts/alpha/cities/1/worker-plan"
        draft = {"task": "modifyAcademyWorkers", "draft": {"percentage": 50}}
        assert client.post(path, json=draft).status_code == 401
        assert client.post(path, headers=auth, json={
            **draft, "draft": {"percentage": 50, "expected": {}}}).status_code == 422
        result = client.post(path, headers=auth, json=draft)
        assert result.status_code == 200, result.text
        plan = result.json()
        assert plan["ready"] and plan["target"] == 50 and "config" not in plan and not starts
        payload = {"task": draft["task"], "preview_id": plan["preview_id"],
                   "request_id": str(uuid.uuid4()), "confirmed": True}
        target = "/api/v1/accounts/alpha/tasks/worker-start"
        assert client.post(target.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post(target, headers=auth, json={
            **payload, "task": "modifyTempleWorkers"}).status_code == 409
        for task in WORKER_TASKS:
            assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
                "task": task, "config": {}, "confirmed": True,
                "request_id": str(uuid.uuid4()),
            }).status_code == 422
        assert not starts
        result = client.post(target, headers=auth, json=payload)
        assert result.status_code == 200, result.text
        assert starts[0][:2] == ("alpha", draft["task"])
        assert starts[0][2]["expected"]["target"] == 50
        assert client.post(target, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
        assert client.post(target, headers=auth, json={
            **payload, "request_id": str(uuid.uuid4()),
        }).status_code == 409
        assert len(starts) == 1
    finally:
        controller.close()


def test_multiple_cities_both_projects_review_and_halt(monkeypatch):
    session, slider, city = fake_game(monkeypatch)
    second = {**city, "id": "2", "name": "Another town"}
    def own(_s, cid, _name):
        if cid not in (1, 2):
            raise ValueError("Foreign city")
        return str(cid)

    monkeypatch.setattr(workers, "requireOwnCity", own)
    monkeypatch.setattr(workers, "getCityById", lambda _s, cid: city if cid == "1" else second)
    draft = {"percentage": 100, "project": "both", "overcharge": True, "additional_city_ids": [2]}
    plan = workers.preview_native_workers(session, "modifyProduction", 1, **draft)
    assert plan["target"] == 480
    assert [r["project"] for r in plan["assignments"]] == ["resource", "tradegood"] * 2
    assert validate_worker_plan("modifyProduction", 1, validated_worker_draft("modifyProduction", draft),
                                plan)["config"] == plan["config"]
    with pytest.raises(ValueError):
        workers.preview_native_workers(session, "modifyProduction", 1, **{**draft, "additional_city_ids": [3]})
    with pytest.raises(ValueError):
        workers.preview_native_workers(session, "modifyProduction", 1, **{**draft, "additional_city_ids": [1]})
    assert not any(c.kwargs for c in session.post.call_args_list)
    original = session.post.side_effect

    def post(url="", **kwargs):
        reply = original(url, **kwargs)
        if kwargs:
            slider["max_value"] = 99
        return reply

    session.post.side_effect = post
    with pytest.raises(ValueError, match="stale"):
        workers.execute_native_workers(session, "modifyProduction", **plan["config"])
    writes = [c.kwargs for c in session.post.call_args_list if c.kwargs]
    assert len(writes) == 1 and writes[0]["params"]["rw"] == 120
    assert writes[0]["retry_on_failure"] is False
    assert restart_class_for("modifyProduction", plan["config"]) == "manual"


def test_worker_aggregate_api_rejects_foreign_city_and_preserves_projects(monkeypatch, tmp_path):
    session, _, _ = fake_game(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}])
    monkeypatch.setattr(ipc, "_exchange", lambda p, **_kw: {
        "status": "ok", "world": p["world"], "username": p["player"],
        "plan": workers.preview_native_workers(session, p["task"], p["city_id"], p["percentage"],
                                               p.get("project"), p.get("overcharge", False),
                                               p.get("additional_city_ids"))})
    monkeypatch.setattr(ipc, "preflight_task", lambda _a, task: {
        "task": task, "ready": True, "reason": "none", "notifications_required": False, "checked": []})
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x"*48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token, ipc_client=ipc,
                                   session_coordinator=owner, task_controller=controller))
    try:
        path = "/api/v1/accounts/alpha/cities/1/worker-plan"
        draft = {"percentage": 50, "project": "both", "overcharge": False}
        request = {"task": "modifyProduction", "draft": draft}
        assert client.post(path, headers=auth, json={**request, "draft": {
            **draft, "additional_city_ids": [2]}}).status_code == 422
        reply = client.post(path, headers=auth, json=request)
        assert reply.status_code == 200, reply.text
        result = reply.json()
        assert result["target"] == 100 and len(result["assignments"]) == 2
        assert result["preview_id"] and "config" not in result
    finally:
        controller.close()
