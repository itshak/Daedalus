"""Synthetic engine, API and recovery checks; never contact game servers."""
import json
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import donate as donation

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.task_control import TaskController


def fake_game(monkeypatch):
    state = {"stock": 1000, "donated": 100, "required": 500, "level": 2, "upgrading": 0}
    session = Mock()
    monkeypatch.setattr(donation, "requireOwnCity", lambda s, city, name: str(city))
    monkeypatch.setattr(donation, "getCityById", lambda s, city: {
        "id": city, "islandId": "99", "name": "Town", "availableResources": [state["stock"]],
    })
    monkeypatch.setattr(donation, "getIsland", lambda html: {"tipo": 2})

    def post(url="", **kwargs):
        if kwargs:
            return "submitted"
        return json.dumps([
            ["updateGlobalData", {"backgroundData": {
                "resourceLevel": state["level"],
                "resourceEndUpgradeTime": state["upgrading"],
                "tradegoodLevel": state["level"],
                "tradegoodEndUpgradeTime": state["upgrading"],
            }}],
            ["updateTemplateData", ["resource", (
                f'<li class="wood">{state["required"]}</li>'
                f'<li class="wood">{state["donated"]}</li>'
            )]],
        ])

    session.post.side_effect = post
    return session, state


def test_donation_read_only_and_stale_review(monkeypatch):
    session, state = fake_game(monkeypatch)
    plan = donation.preview_native_donation(session, 1, "resource", 200)
    assert plan["ready"] and plan["remaining"] == 400
    assert all(not call.kwargs for call in session.post.call_args_list)
    assert donation.prepare_donate(session, **plan["config"]) == plan["config"]
    state["donated"] = 101
    with pytest.raises(ValueError, match="stale"):
        donation.prepare_donate(session, **plan["config"])
    state["stock"] = 10
    assert not donation.preview_native_donation(session, 1, "resource", 200)["ready"]
    state["stock"] = 1000
    state["upgrading"] = 1
    assert not donation.preview_native_donation(session, 1, "tradegood", 200)["ready"]
    with pytest.raises(ValueError):
        donation.preview_native_donation(session, 1, "other", 200)
    assert all(not call.kwargs for call in session.post.call_args_list)


def test_donation_single_mutation_and_manual_recovery(monkeypatch):
    session, _ = fake_game(monkeypatch)
    plan = donation.preview_native_donation(session, 1, "tradegood", 100)
    donation.execute_native_donation.__wrapped__(session, **plan["config"])
    mutations = [call.kwargs for call in session.post.call_args_list if call.kwargs]
    assert len(mutations) == 1
    assert mutations[0]["retry_on_failure"] is False
    assert mutations[0]["params"]["donation"] == 100
    assert mutations[0]["params"]["cityId"] == "1"
    assert restart_class_for("donate", plan["config"]) == "manual"


def test_donation_ipc_and_reviewed_api(monkeypatch, tmp_path):
    session, _ = fake_game(monkeypatch)
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
        "plan": donation.preview_native_donation(
            session, payload["city_id"], payload["project"], payload["amount"]),
    })
    monkeypatch.setattr(ipc, "preflight_task", lambda account, task: {
        "task": task, "ready": True, "reason": "none",
        "notifications_required": False, "checked": [],
    })
    monkeypatch.setattr(ipc, "has_account", lambda account: True)

    def start(account, task, config, rid):
        starts.append((account.id, task, config, rid))
        return {"task_id": "a" * 24, "pid": 1234, "task": task, "status": "running"}

    monkeypatch.setattr(ipc, "start_managed_task", start, raising=False)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token,
                                   session_coordinator=owner, task_controller=controller,
                                   ipc_client=ipc))
    try:
        path = "/api/v1/accounts/alpha/cities/1/donation-plan"
        draft = {"project": "resource", "amount": 100}
        assert client.post(path, json=draft).status_code == 401
        assert client.post(path, headers=auth, json={**draft, "amount": True}).status_code == 422
        assert client.post(path.replace("/1/", "/2/"), headers=auth, json=draft).status_code == 422
        result = client.post(path, headers=auth, json=draft)
        assert result.status_code == 200, result.text
        plan = result.json()
        assert plan["ready"] and "config" not in plan and not starts
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()),
                   "confirmed": True}
        target = "/api/v1/accounts/alpha/tasks/donation-start"
        assert client.post(target.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post(target.replace("donation-start", "construction-start"), headers=auth,
                           json=payload).status_code == 409
        assert client.post(target, headers=auth, json={**payload, "confirmed": False}).status_code == 422
        assert client.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "donate", "config": {}, "confirmed": True,
            "request_id": str(uuid.uuid4()),
        }).status_code == 422
        assert not starts
        result = client.post(target, headers=auth, json=payload)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "started"
        assert starts[0][:2] == ("alpha", "donate")
        assert starts[0][2]["amount"] == 100
        assert client.post(target, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
        assert client.post(target, headers=auth, json={
            **payload, "request_id": str(uuid.uuid4()),
        }).status_code == 409
        assert len(starts) == 1
    finally:
        controller.close()
