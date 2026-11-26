"""Synthetic engine and persistent idempotency tests; no Gameforge traffic."""

from __future__ import annotations

import os
import stat
import uuid

import pytest

from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
from daedalus.accounts import Account
from daedalus.engine_ipc import EngineIPCUnavailable, EngineTaskRejected
from daedalus.task_control import (
    TaskConflict,
    TaskController,
    TaskLedger,
    TaskPrerequisiteMissing,
    TaskRejected,
    TaskUnavailable,
    validated_configuration,
)


class FakeTaskIPC:
    def __init__(self) -> None:
        self.online = True
        self.sent = []
        self.stopped = []

    def has_account(self, account):
        return self.online and account.player == "ExamplePlayer"

    def preflight_task(self, account, task):
        return {"task": task, "ready": True, "reason": "none",
                "notifications_required": False, "checked": []}

    def start_managed_task(self, account, task, config, request_id):
        self.sent.append((account.id, task, config))
        return {"task_id": "f" * 24, "pid": 4242, "task": task, "status": "running"}

    def list_managed_tasks(self, account):
        return [{"task_id": "f" * 24, "pid": 4242, "task": "alertAttacks",
                 "status": "running", "started_at": 1700000000.0}]

    def stop_managed_task(self, account, task_id):
        self.stopped.append((account.id, task_id))
        return {"task_id": task_id, "status": "stopped"}


@pytest.fixture
def fixtures(tmp_path):
    accounts = [Account("alpha", "s301-en", "ExamplePlayer", "Example", True)]
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "leases")
    ipc = FakeTaskIPC()
    manager = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "ledger.sqlite3")
    yield manager, ipc, owner, tmp_path
    manager.close()


def test_task_start_uses_one_owner_and_durable_dedup(fixtures):
    controller, ipc, owner, temp = fixtures
    request_id = str(uuid.uuid4())
    started = controller.start("alpha", "alertAttacks", {"minutes": 20}, request_id,
                               confirmed=True)
    assert started["status"] == "started"
    assert started["task_id"] == "f" * 24
    assert ipc.sent == [("alpha", "alertAttacks", {"minutes": 20})]
    assert owner.status("alpha") == SessionPhase.AUTHENTICATED.value

    retry = controller.start("alpha", "alertAttacks", {"minutes": 20}, request_id,
                             confirmed=True)
    assert retry == started
    assert len(ipc.sent) == 1

    with pytest.raises(TaskConflict, match="different task"):
        controller.start("alpha", "alertAttacks", {"minutes": 25}, request_id,
                         confirmed=True)
    assert len(ipc.sent) == 1
    assert (temp / "ledger.sqlite3").exists()
    if os.name != "nt":
        assert stat.S_IMODE((temp / "ledger.sqlite3").stat().st_mode) == 0o600


def test_retry_after_backend_restart_does_not_relaunch(fixtures):
    controller, ipc, _owner, temp = fixtures
    request_id = str(uuid.uuid4())
    controller.start("alpha", "alertAttacks", {"minutes": 1}, request_id, confirmed=True)
    controller.close()
    second_owner = AccountSessionCoordinator(
        [Account("alpha", "s301-en", "ExamplePlayer", "Example", True)],
        state_dir=temp / "leases",
    )
    second = TaskController([Account("alpha", "s301-en", "ExamplePlayer", "Example", True)],
                            second_owner, ipc, ledger_path=temp / "ledger.sqlite3")
    try:
        result = second.start("alpha", "alertAttacks", {"minutes": 1}, request_id,
                              confirmed=True)
        assert result["status"] == "started"
        assert len(ipc.sent) == 1
        assert second_owner.status("alpha") == "not_connected"
    finally:
        second.close()


def test_opt_in_and_confirmation_required(fixtures):
    controller, ipc, owner, _ = fixtures
    with pytest.raises(ValueError, match="confirmation"):
        controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=False)
    with pytest.raises(ValueError, match="UUID"):
        controller.start("alpha", "alertAttacks", {}, "not-an-id", confirmed=True)
    with pytest.raises(ValueError, match="Unsupported"):
        controller.start("alpha", "notAnEngineTask", {}, str(uuid.uuid4()), confirmed=True)
    assert ipc.sent == []
    assert owner.status("alpha") == "not_connected"


def test_missing_session_releases_lease_and_does_not_dispatch(fixtures):
    controller, ipc, owner, _ = fixtures
    ipc.online = False
    with pytest.raises(TaskUnavailable, match="already-authenticated"):
        controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
    assert owner.status("alpha") == "not_connected"
    assert ipc.sent == []


def test_unconfirmed_ipc_result_cannot_be_automatically_replayed(fixtures):
    controller, ipc, _owner, _ = fixtures

    def fails(*_args, **_kwargs):
        raise EngineIPCUnavailable("Fake disconnected reply")

    ipc.start_managed_task = fails
    request_id = str(uuid.uuid4())
    with pytest.raises(EngineIPCUnavailable):
        controller.start("alpha", "alertAttacks", {}, request_id, confirmed=True)
    result = controller.start("alpha", "alertAttacks", {}, request_id, confirmed=True)
    assert result["status"] == "unconfirmed"
    assert result["task_id"] is None
    assert controller.preflight("alpha", "alertAttacks")["unresolved_request"] is True


def test_list_stop_reports_only_current_engine_managed_tasks(fixtures):
    controller, ipc, owner, _ = fixtures
    rows = controller.list_tasks("alpha")
    assert rows["engine_tasks"][0]["task_id"] == "f" * 24
    assert rows["requests"] == []
    stopped = controller.stop("alpha", "f" * 24)
    assert stopped["status"] == "stopped"
    assert ipc.stopped == [("alpha", "f" * 24)]
    assert owner.status("alpha") == "authenticated"


def test_configuration_secret_and_size_checks_are_recursive():
    for config in (
        {"password": "example"},
        {"nested": [{"gf_token": "not-a-real-token"}]},
        {"cookie": {}},
        {"outer": {"authKey": "sensitive"}},
        {"number": float("nan")},
        {"text": "x" * 2001},
    ):
        with pytest.raises((TypeError, ValueError)):
            validated_configuration(config)
    safe, digest = validated_configuration({"minutes": 20, "cities": [1, 2]})
    assert safe == {"minutes": 20, "cities": [1, 2]}
    assert len(digest) == 64


def test_ledger_reserve_creates_no_directory_before_first_write(tmp_path):
    ledger = TaskLedger(tmp_path / "private" / "ledger.sqlite3")
    assert not (tmp_path / "private").exists()
    saved, receipt = ledger.reserve("alpha", str(uuid.uuid4()), "alertAttacks", "a" * 64)
    assert saved is True
    assert receipt["status"] == "dispatching"
    assert (tmp_path / "private").exists()
    assert len(ledger.entries("alpha")) == 1


def test_missing_notifications_fail_before_ledger_reservation(fixtures):
    controller, ipc, _owner, temp = fixtures
    def missing(_account, task):
        return {"task": task, "ready": False,
                "reason": "notifications_required", "checked": ["notifications"],
                "notifications_required": True}
    ipc.preflight_task = missing
    request_id = str(uuid.uuid4())
    assert controller.preflight("alpha", "alertAttacks")["ready"] is False
    with pytest.raises(TaskPrerequisiteMissing, match="Configure Telegram or Discord"):
        controller.start("alpha", "alertAttacks", {}, request_id, confirmed=True)
    assert ipc.sent == []
    assert TaskLedger(temp / "ledger.sqlite3").entries("alpha") == []
    # Prerequisites that become available later can be tried safely.
    ipc.preflight_task = lambda a, t: {"ready": True, "reason": "none"}
    assert controller.start("alpha", "alertAttacks", {}, request_id, confirmed=True)["status"] == "started"


def test_unknown_preflight_does_not_mark_task_unconfirmed(fixtures):
    controller, ipc, _owner, temp = fixtures
    def unreachable(*args):
        raise EngineIPCUnavailable("preflight probe unavailable")
    ipc.preflight_task = unreachable
    with pytest.raises(EngineIPCUnavailable):
        controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
    assert TaskLedger(temp / "ledger.sqlite3").entries("alpha") == []
    assert not ipc.sent


def test_duplicate_request_id_remains_readable_even_if_prerequisites_change(fixtures):
    manager, ipc, _owner, _path = fixtures
    rid = str(uuid.uuid4())
    first = manager.start("alpha", "alertAttacks", {"minutes": 10}, rid, confirmed=True)
    ipc.preflight_task = lambda *_args: {"ready": False, "reason": "notifications_required"}
    assert manager.start("alpha", "alertAttacks", {"minutes": 10}, rid, confirmed=True) == first
    assert len(ipc.sent) == 1


def test_engine_pre_spawn_rejection_is_definite_and_does_not_block_future_requests(fixtures):
    controller, ipc, _owner, _temp = fixtures
    def definite(*_args):
        raise EngineTaskRejected("invalid_configuration")
    ipc.start_managed_task = definite
    request_id = str(uuid.uuid4())
    with pytest.raises(TaskRejected, match="Invalid automation parameters"):
        controller.start("alpha", "alertAttacks", {"minutes": "bad"}, request_id,
                         confirmed=True)
    receipts = controller.list_tasks("alpha")["requests"]
    assert receipts[0]["status"] == "rejected"
    assert receipts[0]["task_id"] is None
    assert controller.start("alpha", "alertAttacks", {"minutes": "bad"}, request_id,
                            confirmed=True)["status"] == "rejected"
    ipc.start_managed_task = lambda a, t, c, rid: {
        "task_id": "f" * 24, "pid": 4242, "task": t, "status": "running"}
    assert controller.start("alpha", "alertAttacks", {"minutes": 20},
                            str(uuid.uuid4()), confirmed=True)["status"] == "started"


def test_browser_cookie_worker_lease_is_adopted_before_dispatch(fixtures):
    """The production native-cookie path already owns this exact account lease."""
    controller, ipc, owner, _ = fixtures
    lease = owner.acquire("alpha")
    lease.transition(SessionPhase.AUTHENTICATED)
    request_id = str(uuid.uuid4())
    result = controller.start("alpha", "fillCityWarehouse", {
        "destination_city": 123, "resource": "wood", "useFreighters": False,
        "reviewed_sources": [{"city_id": 456, "amount": 50}],
    }, request_id, confirmed=True)
    assert result["status"] == "started"
    assert controller.owned_sessions() == (lease,)
    assert len(ipc.sent) == 1
    assert controller.preflight("alpha", "fillCityWarehouse")["unresolved_request"] is False


def test_unverified_local_lease_does_not_reserve_dispatch(fixtures):
    controller, ipc, owner, temp = fixtures
    lease = owner.acquire("alpha")
    try:
        with pytest.raises(TaskUnavailable, match="verified local account owner"):
            controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
        assert not ipc.sent
        assert TaskLedger(temp / "ledger.sqlite3").entries("alpha") == []
    finally:
        lease.close()


def test_closed_adopted_lease_can_be_replaced(fixtures):
    controller, ipc, owner, _ = fixtures
    first = owner.acquire("alpha")
    first.transition(SessionPhase.AUTHENTICATED)
    controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
    first.close()
    replacement = owner.acquire("alpha")
    replacement.transition(SessionPhase.AUTHENTICATED)
    controller.start("alpha", "alertAttacks", {}, str(uuid.uuid4()), confirmed=True)
    assert controller.owned_sessions() == (replacement,)
    assert len(ipc.sent) == 2
