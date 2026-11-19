"""Full HTTP authorization and task lifecycle against a fake IPC worker."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import EngineIPCUnavailable
from daedalus.task_control import TaskController

TOKEN = "x" * 48
CONFIG = """
schema = 1
[[accounts]]
id = "alpha"
world = "s301-en"
player = "ExamplePlayer"
"""


class MockIPC:
    def __init__(self):
        self.calls = []
        self.fail_once = False
        self.notifications_ready = True
        self.reject_bad_config = False

    def has_account(self, account):
        self.calls.append(("verify", account.id))
        return True

    def preflight_task(self, account, task):
        return {"task": task, "ready": self.notifications_ready,
                "reason": "none" if self.notifications_ready else "notifications_required",
                "notifications_required": True, "checked": ["notifications"]}

    def start_managed_task(self, account, task, config, request_id):
        self.calls.append(("start", account.id, task, config))
        if self.reject_bad_config:
            from daedalus.engine_ipc import EngineTaskRejected
            raise EngineTaskRejected("invalid_configuration")
        if self.fail_once:
            self.fail_once = False
            raise EngineIPCUnavailable("secret-server-error-should-be-redacted")
        return {"task_id": "f" * 24, "pid": 1234, "task": task, "status": "running"}

    def list_managed_tasks(self, account):
        self.calls.append(("list", account.id))
        return [{"task_id": "f" * 24, "task": "alertAttacks", "pid": 1234,
                 "started_at": 1700000000, "status": "running"}]

    def stop_managed_task(self, account, task_id):
        self.calls.append(("stop", account.id, task_id))
        return {"task_id": task_id, "status": "stopped"}


@pytest.fixture
def setup(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text(CONFIG)
    accounts = load_accounts(config)
    coordinator = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = MockIPC()
    manager = TaskController(accounts, coordinator, ipc, ledger_path=tmp_path / "requests.sqlite3")
    client = TestClient(create_app(
        accounts_path=config, api_token=TOKEN, session_coordinator=coordinator,
        task_controller=manager,
    ))
    yield client, ipc, manager, coordinator
    manager.close()


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def request(task="alertAttacks", config=None, rid=None, *, confirmed=True):
    return {
        "task": task, "config": {"minutes": 20} if config is None else config,
        "request_id": rid or str(uuid.uuid4()), "confirmed": confirmed,
    }


def test_task_routes_disabled_by_default_even_when_accounts_configured(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text(CONFIG)
    client = TestClient(create_app(accounts_path=config, api_token=TOKEN))
    assert client.get("/api/v1/accounts/alpha/tasks", headers=auth()).status_code == 503
    assert client.post("/api/v1/accounts/alpha/tasks", headers=auth(),
                       json=request()).status_code == 503
    assert client.get("/api/v1/capabilities", headers=auth()).json()[
        "structured_engine_dispatch"
    ] is False


def test_task_auth_confirmation_dedup_and_stop(setup):
    client, ipc, _manager, coordinator = setup
    target = "/api/v1/accounts/alpha/tasks"
    payload = request()
    assert client.post(target, json=payload).status_code == 401
    assert client.post(target, json={**payload, "confirmed": False},
                       headers=auth()).status_code == 422
    assert ipc.calls == []

    response = client.post(target, json=payload, headers=auth())
    assert response.status_code == 200
    assert response.json()["task_id"] == "f" * 24
    assert coordinator.status("alpha") == "authenticated"
    assert client.get("/api/v1/health").json()["mode"] == "task_control_opt_in"
    assert client.get("/api/v1/capabilities", headers=auth()).json()[
        "structured_engine_dispatch"
    ] is True
    duplicate = client.post(target, json=payload, headers=auth())
    assert duplicate.status_code == 200
    assert len([call for call in ipc.calls if call[0] == "start"]) == 1

    listed = client.get(target, headers=auth())
    assert listed.status_code == 200
    assert listed.json()["engine_tasks"][0]["task_id"] == "f" * 24
    assert listed.json()["requests"][0]["status"] == "started"

    stopped = client.post(f"{target}/{'f' * 24}/stop", headers=auth())
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert ("stop", "alpha", "f" * 24) in ipc.calls


def test_task_invalid_inputs_no_network(setup):
    client, ipc, _, _coordinator = setup
    target = "/api/v1/accounts/alpha/tasks"
    assert client.post("/api/v1/accounts/other/tasks", json=request(),
                       headers=auth()).status_code == 404
    assert client.post(target, json=request(task="notAnEngineTask"),
                       headers=auth()).status_code == 422
    assert client.post(target, json=request(config={"gf_token": "dummy"}),
                       headers=auth()).status_code == 422
    assert client.post(target, json=request(rid="short"), headers=auth()).status_code == 422
    assert ipc.calls == []


def test_timeout_is_unconfirmed_and_requires_manual_reconciliation(setup):
    client, ipc, _, _coordinator = setup
    target = "/api/v1/accounts/alpha/tasks"
    first = request()
    ipc.fail_once = True
    failed = client.post(target, json=first, headers=auth())
    assert failed.status_code == 503
    assert "secret-server-error" not in failed.text
    task_rows = client.get(target, headers=auth()).json()["requests"]
    assert task_rows[0]["status"] == "unconfirmed"

    blocked = client.post(target, json=request(), headers=auth())
    assert blocked.status_code == 503
    assert len([call for call in ipc.calls if call[0] == "start"]) == 1

    ack_url = f"{target}/requests/{first['request_id']}/acknowledge"
    assert client.post(ack_url, json={"confirmed": False},
                       headers=auth()).status_code == 422
    reconciled = client.post(ack_url, json={"confirmed": True}, headers=auth())
    assert reconciled.status_code == 200
    assert reconciled.json()["status"] == "operator_reconciled"
    next_run = client.post(target, json=request(), headers=auth())
    assert next_run.status_code == 200
    assert len([call for call in ipc.calls if call[0] == "start"]) == 2


def test_task_readiness_is_readonly_and_missing_notification_is_clear_409(setup):
    client, ipc, _manager, _coordinator = setup
    target = "/api/v1/accounts/alpha/tasks"
    prereq = target + "/preflight?task=alertAttacks"
    assert client.get(prereq).status_code == 401
    ipc.notifications_ready = False
    readiness = client.get(prereq, headers=auth())
    assert readiness.status_code == 200
    assert readiness.json()["reason"] == "notifications_required"
    assert readiness.json()["ready"] is False
    assert readiness.json()["unresolved_request"] is False
    assert client.get(target, headers=auth()).json()["requests"] == []
    launch = client.post(target, json=request(), headers=auth())
    assert launch.status_code == 409
    assert "Configure Telegram or Discord" in launch.json()["detail"]
    assert client.get(target, headers=auth()).json()["requests"] == []
    assert not any(call[0]=="start" for call in ipc.calls)
    ipc.notifications_ready = True
    assert client.get(prereq, headers=auth()).json()["ready"] is True
    assert client.post(target, json=request(), headers=auth()).status_code == 200


def test_definite_preparation_error_returns_safe_422_without_uncertain_request(setup):
    client, ipc, _manager, _coordinator = setup
    target = "/api/v1/accounts/alpha/tasks"
    ipc.reject_bad_config = True
    payload = request(config={"minutes": "invalid"})
    failure = client.post(target, json=payload, headers=auth())
    assert failure.status_code == 422
    assert "Invalid automation parameters" in failure.json()["detail"]
    rows = client.get(target, headers=auth()).json()["requests"]
    assert rows[0]["status"] == "rejected"
    ipc.reject_bad_config = False
    assert client.post(target, json=request(), headers=auth()).status_code == 200
