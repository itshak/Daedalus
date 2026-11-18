"""Safe cookie-only worker bootstrap tests; all game sessions are synthetic."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError, SessionPhase
from daedalus.accounts import Account
from daedalus.saved_session_recovery import bind_saved_email
from daedalus.saved_worker import SavedCookieWorker, SavedWorkerUnavailable
from daedalus.task_control import TaskController, TaskUnavailable


class FakeKeyring:
    def __init__(self):
        self.saved = {}

    def get_password(self, service, user):
        return self.saved.get((service, user))

    def set_password(self, service, user, password):
        self.saved[(service, user)] = password


class FakeIPC:
    def __init__(self, account):
        self.account = account
        self.online = True
        self.started = []

    def has_account(self, account):
        return self.online and account == self.account

    def start_managed_task(self, account, task, config, request_id):
        self.started.append((account.id, task, config, request_id))
        return {"task_id": "a" * 24, "pid": 42, "status": "running"}


@pytest.fixture
def system(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "Test", True)
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "leases")
    keyring = FakeKeyring()
    bind_saved_email(account, "fixture@example.invalid", credential_store=keyring)
    session = SimpleNamespace(
        logged=True, mundo="301", servidor="en", username="ExamplePlayer",
        s=SimpleNamespace(closed=False),
    )
    session.s.close = lambda: setattr(session.s, "closed", True)
    events = []
    worker = SavedCookieWorker(
        account, owner, credential_store=keyring,
        restore=lambda *args: (events.append(("restore", args)), session)[1],
        start_ipc=lambda verified: (events.append(("start-ipc", verified)), object())[1],
        stop_ipc=lambda: events.append(("stop-ipc",)),
    )
    return account, owner, keyring, session, events, worker, tmp_path


def test_opt_in_and_keyring_required(system):
    account, owner, keyring, session, events, worker, _ = system
    with pytest.raises(SavedWorkerUnavailable, match="consent"):
        worker.start(confirmed=False)
    assert events == []
    keyring.saved.clear()
    with pytest.raises(SavedWorkerUnavailable, match="Bind"):
        worker.start(confirmed=True)
    assert owner.status(account.id) == "not_connected"
    assert events == []
    assert not session.s.closed


def test_verified_worker_owns_lease_and_stops_ipc_before_releasing(system):
    account, owner, _keyring, session, events, worker, _ = system
    worker.start(confirmed=True)
    assert owner.status(account.id) == SessionPhase.AUTHENTICATED.value
    assert events[0][0] == "restore"
    assert events[0][1][0] is account
    assert events[0][1][1] == "fixture@example.invalid"
    assert events[0][1][2] is None
    assert events[1] == ("start-ipc", session)
    with pytest.raises(SavedWorkerUnavailable, match="already started"):
        worker.start(confirmed=True)
    with pytest.raises(SessionBusyError):
        owner.acquire(account.id)
    worker.close()
    assert events[2] == ("stop-ipc",)
    assert session.s.closed
    assert owner.status(account.id) == "not_connected"
    worker.close()


@pytest.mark.parametrize("wrong", [
    ("logged", False), ("username", "WrongPlayer"),
    ("mundo", "302"), ("servidor", "de"),
])
def test_unverified_session_never_activates_ipc(system, wrong):
    account, owner, _, session, events, worker, _ = system
    setattr(session, *wrong)
    with pytest.raises(SavedWorkerUnavailable, match="did not verify"):
        worker.start(confirmed=True)
    assert events[0][0] == "restore"
    assert len(events) == 1
    assert session.s.closed
    assert owner.status(account.id) == "not_connected"


def test_failed_restore_is_sanitized_and_releases_lease(system):
    account, owner, _, _, events, worker, _ = system
    def fail(*_args):
        raise RuntimeError("private-cookie-DO-NOT-LEAK")
    worker._restore = fail
    with pytest.raises(SavedWorkerUnavailable) as error:
        worker.start(confirmed=True)
    assert "private-cookie-DO-NOT-LEAK" not in str(error.value)
    assert owner.status(account.id) == "not_connected"
    assert events == []


def test_worker_start_refuses_unrelated_ipc_owner(system):
    account, owner, _, session, _events, worker, _ = system
    worker._start_ipc = lambda _session: None
    with pytest.raises(SavedWorkerUnavailable, match="already running"):
        worker.start(confirmed=True)
    assert owner.status(account.id) == "not_connected"
    assert session.s.closed


def test_local_task_controller_adopts_exact_worker_lease(system):
    account, owner, _, _, _, worker, root = system
    ipc = FakeIPC(account)
    controller = TaskController([account], owner, ipc, ledger_path=root / "ledger.sqlite3")
    try:
        worker.start(confirmed=True)
        controller.adopt_verified_saved_worker(account.id, worker.lease)
        assert controller.owned_sessions() == (worker.lease,)
        result = controller.start(
            account.id, "alertAttacks", {"minutes": 2}, str(uuid.uuid4()), confirmed=True,
        )
        assert result["status"] == "started"
        assert len(ipc.started) == 1
        with pytest.raises(TaskUnavailable, match="lease"):
            controller.adopt_verified_saved_worker(account.id, worker.lease)
    finally:
        controller.close()
        worker.close()
    assert owner.status(account.id) == "not_connected"


def test_task_controller_rejects_unverified_local_worker(system):
    account, owner, _, _, _, worker, root = system
    ipc = FakeIPC(account)
    controller = TaskController([account], owner, ipc, ledger_path=root / "ledger.sqlite3")
    try:
        worker.start(confirmed=True)
        ipc.online = False
        with pytest.raises(TaskUnavailable, match="does not match"):
            controller.adopt_verified_saved_worker(account.id, worker.lease)
        assert controller.owned_sessions() == ()
    finally:
        controller.close()
        worker.close()
