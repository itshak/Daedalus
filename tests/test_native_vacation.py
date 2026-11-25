"""Offline vacation review and recovery guards."""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import vacationMode as vacation

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_state import RecoveryStore
from daedalus.reviewed_operations import validate_vacation_plan
from daedalus.task_control import TaskController


def fixture(monkeypatch):
    session = Mock(mundo=1, servidor="en", username="Example")
    active = []
    monkeypatch.setattr(vacation, "requireOwnCity", lambda _s, cid, _n: str(cid))
    monkeypatch.setattr(vacation, "getCityById", lambda _s, cid: {
        "id": cid, "cityName": "Town",
    })
    monkeypatch.setattr(vacation, "updateProcessList", lambda _s: active)
    return session, active


def test_vacation_engine_readiness_and_single_attempt(monkeypatch):
    session, active = fixture(monkeypatch)
    plan = vacation.preview_native_vacation(session, 1)
    assert plan["ready"]
    assert validate_vacation_plan(1, plan)["config"] == plan["config"]
    assert not session.post.called
    active.append({"pid": 99999999})
    with pytest.raises(ValueError):
        vacation.prepare_native_vacation(session, **plan["config"])
    active.clear()
    vacation.native_vacation.__wrapped__(session, **plan["config"])
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["retry_on_failure"] is False
    assert session.post.call_args.kwargs["params"]["function"] == "activateVacationMode"


def test_vacation_requires_idle_account_and_disabled_recovery(monkeypatch, tmp_path):
    session, _ = fixture(monkeypatch)
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    store = RecoveryStore(tmp_path / "recovery.sqlite")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}])
    monkeypatch.setattr(ipc, "_exchange", lambda p, **kw: {
        "status": "ok", "world": p["world"], "username": p["player"],
        "plan": vacation.preview_native_vacation(session, p["city_id"]),
    })
    monkeypatch.setattr(ipc, "preflight_task", lambda _a, task: {
        "task": task, "ready": True, "reason": "none", "notifications_required": False, "checked": [],
    })
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    active, starts = [], []
    monkeypatch.setattr(ipc, "list_managed_tasks", lambda _a: active)

    def start(account, task, config, rid):
        starts.append((account.id, task, config, rid))
        return {"task_id": "a" * 24, "pid": 1234, "task": task, "status": "running"}

    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite",
                                recovery_store=store)
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token, session_coordinator=owner,
                                   task_controller=controller, ipc_client=ipc, recovery_store=store))
    try:
        path = "/api/v1/accounts/alpha/cities/1/vacation-plan"
        assert client.post(path, headers=auth, json={"extra": True}).status_code == 422
        blocked = client.post(path, headers=auth, json={}).json()
        assert blocked["ready"] is False and blocked["recovery_disabled"] is False
        assert blocked["preview_id"] is None
        store.set_policy(accounts[0], enabled=False, auto_resume=False)
        active.append({"status": "running"})
        blocked = client.post(path, headers=auth, json={}).json()
        assert blocked["ready"] is False and blocked["managed_active"] is True
        active.clear()
        response = client.post(path, headers=auth, json={})
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["ready"] and "config" not in plan
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        url = "/api/v1/accounts/alpha/tasks/vacation-start"
        assert client.post(url.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "vacationMode", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4())}).status_code == 422
        store.set_policy(accounts[0], enabled=True, auto_resume=True)
        assert client.post(url, headers=auth, json=payload).status_code == 503
        assert not starts
        store.set_policy(accounts[0], enabled=False, auto_resume=False)
        plan = client.post(path, headers=auth, json={}).json()
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert starts[0][:2] == ("alpha", "vacationMode")
        assert client.post(url, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
        assert not store.desired(accounts[0])
    finally:
        controller.close()
