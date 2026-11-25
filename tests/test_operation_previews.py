"""Offline coverage for native reviewed construction dispatch."""
import uuid

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.operation_previews import OperationPreviews, PreviewUnavailable
from daedalus.task_control import TaskController


def test_ticket_scope_expiration_capacity_and_single_request():
    now = [100.0]
    tickets = OperationPreviews(ttl=10, capacity=2, clock=lambda: now[0])
    config = {"city_id": 1, "buildings": [{"position": 2}]}
    ticket = tickets.issue("a", "constructionList", config)
    config["city_id"] = 99
    with pytest.raises(PreviewUnavailable):
        tickets.claim(ticket, "b", "constructionList", "one")
    with pytest.raises(PreviewUnavailable):
        tickets.claim(ticket, "a", "sendResources", "one")
    original = tickets.claim(ticket, "a", "constructionList", "one")
    assert original["city_id"] == 1
    original["city_id"] = 99
    assert tickets.claim(ticket, "a", "constructionList", "one")["city_id"] == 1
    with pytest.raises(PreviewUnavailable):
        tickets.claim(ticket, "a", "constructionList", "two")
    tickets.issue("a", "constructionList", config)
    tickets.issue("a", "constructionList", config)
    with pytest.raises(PreviewUnavailable):
        tickets.claim(ticket, "a", "constructionList", "one")
    key = tickets.issue("a", "constructionList", config)
    now[0] += 10
    with pytest.raises(PreviewUnavailable):
        tickets.claim(key, "a", "constructionList", "one")


def test_reviewed_construction_api_uses_opaque_scoped_plan(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
        '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n'
    )
    accounts = load_accounts(config)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    starts = []

    class IPC:
        def construction_preview(self, account, city_id, upgrades):
            return {
                "account_id": account.id, "city_id": city_id, "ready": True,
                "costs": [100, 0, 0, 0, 0], "available": [200, 0, 0, 0, 0],
                "missing": [0] * 5, "estimated_seconds": 120,
                "config": {"city_id": city_id, "city_name": "Example city", "buildings": [
                    {"name": "Town hall", "position": 0, "level": 3, "upgradeTo": 4}
                ]},
            }

        def preflight_task(self, account, task):
            return {"task": task, "ready": True, "reason": "none",
                    "notifications_required": False, "checked": []}

        def has_account(self, account):
            return True

        def start_managed_task(self, account, task, config, request_id):
            starts.append((account.id, task, config, request_id))
            return {"task_id": "a" * 24, "pid": 1234, "task": task, "status": "running"}

    ipc = IPC()
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(
        accounts_path=config, api_token=token, session_coordinator=owner,
        task_controller=controller, ipc_client=ipc,
    ))
    try:
        path = "/api/v1/accounts/alpha/cities/1/construction-plan"
        plan = client.post(path, headers=auth, json={
            "upgrades": [{"position": 0, "target_level": 4}],
        }).json()
        assert plan["ready"] and plan["preview_id"]
        assert "config" not in plan and not starts
        assert plan["buildings"][0]["target_level"] == 4
        payload = {"preview_id": plan["preview_id"], "request_id": str(uuid.uuid4()),
                   "confirmed": True}
        target = "/api/v1/accounts/alpha/tasks/construction-start"
        assert client.post(target, json=payload).status_code == 401
        assert client.post(target, headers=auth, json={**payload, "confirmed": False}).status_code == 422
        assert client.post(target.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert client.post(target, headers=auth, json={**payload, "config": {}}).status_code == 422
        assert not starts
        response = client.post(target, headers=auth, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "started"
        assert starts[0][:2] == ("alpha", "constructionList")
        assert starts[0][2]["city_id"] == 1
        assert client.post(target, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
        assert client.post(target, headers=auth, json={
            **payload, "request_id": str(uuid.uuid4()),
        }).status_code == 409
        assert len(starts) == 1
    finally:
        controller.close()
