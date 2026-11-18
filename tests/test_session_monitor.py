"""Opt-in authenticated existing-session monitoring, all with synthetic IPC."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.auth_assistance import AssistanceBroker, AssistanceConflict
from daedalus.session_monitor import ExistingSessionRecoveryMonitor, MonitoringUnavailable
from daedalus.task_control import TaskController, TaskUnavailable

TOKEN = "x" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeVerifiedIPC:
    def __init__(self) -> None:
        self.online = True
        self.network_failure = False
        self.validation_calls = []
        self.sent = []

    def has_account(self, account):
        return self.online

    def validate_account(self, account):
        self.validation_calls.append(account.id)
        if self.network_failure:
            from daedalus.engine_ipc import EngineIPCUnavailable

            raise EngineIPCUnavailable("private sensitive cookie")
        return self.online

    def start_managed_task(self, account, task, config, rid):
        self.sent.append((account.id, task, rid))
        return {"task_id": "a" * 24, "pid": 4242, "status": "running"}

    def list_managed_tasks(self, _account):
        return []

    def stop_managed_task(self, _account, task_id):
        return {"task_id": task_id, "status": "stopped"}


@pytest.fixture
def context(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "Synthetic", True)
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "locks")
    ipc = FakeVerifiedIPC()
    controller = TaskController(
        [account], owner, ipc, ledger_path=tmp_path / "tasks.sqlite3",
        active_validation=True,
    )
    broker = AssistanceBroker(owner)
    monitor = ExistingSessionRecoveryMonitor(controller, broker)
    yield account, owner, ipc, controller, broker, monitor, tmp_path
    monitor.stop()
    controller.close()


def test_monitor_opt_in_attaches_only_verified_existing_session(context):
    _account, owner, ipc, _task_controller, broker, monitor, _tmp = context
    with pytest.raises(ValueError, match="confirmation"):
        monitor.observe("alpha", confirmed=False)
    assert ipc.validation_calls == []
    ipc.online = False
    with pytest.raises(MonitoringUnavailable, match="verified"):
        monitor.observe("alpha", confirmed=True)
    assert owner.status("alpha") == "not_connected"
    ipc.online = True
    assert monitor.observe("alpha", confirmed=True) == {
        "account_id": "alpha", "status": "monitoring_existing_session",
    }
    assert owner.status("alpha") == "authenticated"
    assert broker.snapshot("alpha")["ticket"] is None
    assert monitor.pending() == {"enabled": True, "tickets": []}


def test_lost_session_triggers_lease_bound_ticket_no_automatic_replay(context):
    account, owner, ipc, controller, broker, monitor, _tmp = context
    monitor.observe(account.id, confirmed=True)
    ipc.online = False
    statuses = monitor.poll_once()
    assert statuses[0].phase == SessionPhase.NEEDS_ASSISTANCE.value
    ticket = broker.snapshot(account.id)["ticket"]
    assert ticket["reason"] == "session_expired"
    assert ticket["state"] == "waiting_operator"
    assert monitor.pending()["tickets"] == [{
        "account_id": account.id, "ticket_id": ticket["ticket_id"],
        "reason": "session_expired", "state": "waiting_operator",
    }]
    with pytest.raises(TaskUnavailable, match="recovery"):
        controller.start(account.id, "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
    assert ipc.sent == []
    # The world/player lease is still held during manual assistance.
    second = AccountSessionCoordinator([account], state_dir=owner._state_dir)
    with pytest.raises(Exception, match="already"):
        second.acquire(account.id)

    broker.approve(account.id, ticket["ticket_id"], confirmed=True)
    assert owner.status(account.id) == "assisted_login"
    monitor.poll_once()
    assert owner.status(account.id) == "needs_assistance"
    assert broker.snapshot(account.id)["ticket"]["state"] == "retry_required"
    monitor.poll_once()
    fresh = broker.snapshot(account.id)["ticket"]
    assert fresh["ticket_id"] != ticket["ticket_id"]
    with pytest.raises(AssistanceConflict):
        broker.approve(account.id, ticket["ticket_id"], confirmed=True)

    ipc.online = True
    broker.approve(account.id, fresh["ticket_id"], confirmed=True)
    monitor.poll_once()
    assert owner.status(account.id) == "authenticated"
    assert broker.snapshot(account.id)["ticket"]["state"] == "verified_by_worker"
    assert ipc.sent == []  # No automatic task replays.


def test_transient_validation_exception_is_sanitized_and_never_resumes(context):
    account, owner, ipc, controller, _broker, monitor, _tmp = context
    monitor.observe(account.id, confirmed=True)
    ipc.network_failure = True
    monitor.poll_once()
    assert owner.status(account.id) == "needs_assistance"
    assert monitor.pending()["tickets"][0]["reason"] == "session_expired"
    assert "private sensitive cookie" not in str(monitor.pending())
    with pytest.raises(TaskUnavailable):
        controller.observe_existing(account.id, confirmed=True)


def test_monitor_start_stop_is_explicit_and_idempotent(context):
    _account, owner, ipc, _controller, _broker, monitor, _tmp = context
    assert monitor._thread is None
    monitor.start()
    thread = monitor._thread
    assert thread is not None and thread.is_alive()
    monitor.start()
    assert monitor._thread is thread
    monitor.stop()
    assert not thread.is_alive()
    assert owner.status("alpha") == "not_connected"
    assert ipc.validation_calls == []


def test_no_monitor_without_active_validation_and_matching_owner(context, tmp_path):
    account, _owner, _ipc, controller, _broker, _monitor, _ = context
    other = AccountSessionCoordinator([account], state_dir=tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="share one"):
        ExistingSessionRecoveryMonitor(controller, AssistanceBroker(other))
    controller._active_validation = False
    with pytest.raises(ValueError, match="active"):
        ExistingSessionRecoveryMonitor(controller, AssistanceBroker(controller._coordinator))


def test_protected_monitor_api_and_pending_assistance(context, tmp_path):
    _account, owner, ipc, controller, broker, monitor, _ = context
    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
        'player = "ExamplePlayer"\nlabel = "Synthetic"\nenabled = true\n',
        encoding="utf-8",
    )
    app = create_app(
        accounts_path=config, api_token=TOKEN, session_coordinator=owner,
        task_controller=controller, assistance_broker=broker, recovery_monitor=monitor,
    )
    with TestClient(app) as client:
        monitor_url = "/api/v1/accounts/alpha/monitor"
        assert client.post(monitor_url, json={"confirmed": True}).status_code == 401
        assert client.post(monitor_url, headers=AUTH,
                           json={"confirmed": False}).status_code == 422
        assert client.post(monitor_url, headers=AUTH, json={
            "confirmed": True, "password": "private",
        }).status_code == 422
        assert client.post("/api/v1/accounts/unknown/monitor", headers=AUTH,
                           json={"confirmed": True}).status_code == 404
        assert client.get("/api/v1/auth-assistance/pending").status_code == 401
        assert client.get("/api/v1/auth-assistance/pending", headers=AUTH).json() == {
            "enabled": True, "tickets": [],
        }
        assert client.get("/api/v1/capabilities", headers=AUTH).json()["session_monitoring"]
        assert client.post(monitor_url, headers=AUTH,
                           json={"confirmed": True}).status_code == 200
        ipc.online = False
        monitor.poll_once()
        tickets = client.get("/api/v1/auth-assistance/pending", headers=AUTH).json()["tickets"]
        assert len(tickets) == 1
        assert set(tickets[0]) == {"account_id", "ticket_id", "reason", "state"}
        assert "private" not in str(tickets)


def test_disabled_monitor_remains_read_only_default(context, tmp_path):
    _account, _owner, _ipc, _controller, _broker, monitor, _ = context
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\n'
                      'world = "s301-en"\nplayer = "ExamplePlayer"\n')
    client = TestClient(create_app(accounts_path=config, api_token=TOKEN))
    assert client.get("/api/v1/auth-assistance/pending", headers=AUTH).json() == {
        "enabled": False, "tickets": [],
    }
    assert client.post("/api/v1/accounts/alpha/monitor", headers=AUTH,
                       json={"confirmed": True}).status_code == 503
    with pytest.raises(ValueError, match="share the opted-in"):
        create_app(
            accounts_path=config, api_token=TOKEN, recovery_monitor=monitor,
        )


def test_cli_requires_two_explicit_flags_for_monitoring(capsys):
    from daedalus.cli import main

    for option_set in (
        ["--monitor-existing-sessions"],
        ["--demo", "--monitor-existing-sessions"],
    ):
        with pytest.raises(SystemExit) as error:
            main(["serve", *option_set])
        assert error.value.code == 2
        assert "--monitor-existing-sessions" in capsys.readouterr().err


def test_post_recovery_dispatch_needs_verified_single_use_ticket(context):
    account, _owner, ipc, _controller, broker, monitor, _ = context
    rid = str(uuid.uuid4())
    with pytest.raises(MonitoringUnavailable, match="approval"):
        monitor.resume_verified_task(account.id, "not-ready", "alertAttacks", {}, rid,
                                     confirmed=False)
    with pytest.raises(MonitoringUnavailable, match="verified"):
        monitor.resume_verified_task(account.id, "not-ready", "alertAttacks", {}, rid,
                                     confirmed=True)
    monitor.observe(account.id, confirmed=True)
    ipc.online = False
    monitor.poll_once()
    ticket = broker.snapshot(account.id)["ticket"]
    with pytest.raises(MonitoringUnavailable, match="verified"):
        monitor.resume_verified_task(account.id, ticket["ticket_id"], "alertAttacks", {}, rid,
                                     confirmed=True)
    broker.approve(account.id, ticket["ticket_id"], confirmed=True)
    ipc.online = True
    monitor.poll_once()
    assert broker.snapshot(account.id)["ticket"]["state"] == "verified_by_worker"
    result = monitor.resume_verified_task(account.id, ticket["ticket_id"],
                                          "alertAttacks", {}, rid, confirmed=True)
    assert result["status"] == "started"
    assert len(ipc.sent) == 1
    with pytest.raises(MonitoringUnavailable, match="verified"):
        monitor.resume_verified_task(account.id, ticket["ticket_id"], "alertAttacks", {},
                                     str(uuid.uuid4()), confirmed=True)
    assert len(ipc.sent) == 1


def test_post_recovery_rechecks_world_and_does_not_dispatch_offline(context):
    account, _owner, ipc, _controller, broker, monitor, _ = context
    monitor.observe(account.id, confirmed=True)
    ipc.online = False
    monitor.poll_once()
    ticket = broker.snapshot(account.id)["ticket"]
    broker.approve(account.id, ticket["ticket_id"], confirmed=True)
    ipc.online = True
    monitor.poll_once()
    ipc.online = False
    with pytest.raises(MonitoringUnavailable, match="no longer valid"):
        monitor.resume_verified_task(account.id, ticket["ticket_id"], "alertAttacks", {},
                                     str(uuid.uuid4()), confirmed=True)
    assert ipc.sent == []
