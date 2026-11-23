"""Cookie-only worker starts only after a verified handoff; no real game traffic."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.browser_cookie_workers import BrowserCookieWorkers
from daedalus.recovery_runtime import RecoveryWorkerError


@pytest.fixture
def account_owner(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "locks")
    return account, owner


def test_verified_cookie_worker_attaches_only_after_private_ipc_player_probe(
    monkeypatch, tmp_path, account_owner,
):
    import daedalus.browser_cookie_workers as module

    account, owner = account_owner
    descriptor = tmp_path / "private.json"
    calls = []
    monkeypatch.setattr(module.RecoveryWorkers, "_descriptor",
                        staticmethod(lambda _account: descriptor))

    class Child:
        def __init__(self, command, *, stdin, stdout, stderr, env, start_new_session):
            assert command[-1] == "daedalus.browser_cookie_child"
            assert env["DAEDALUS_ACCOUNT_IPC_FILE"] == str(descriptor)
            assert "cookie" not in env and "lobby_token" not in env
            self.stdin = __import__("io").BytesIO()
            self.pid = 1000
            self.alive = True
            descriptor.write_text("isolated")
            calls.append("spawn")

        def poll(self):
            return None if self.alive else 0

    class PrivateIPC:
        def __init__(self, path):
            assert path == descriptor

        def validate_account(self, selected):
            assert selected == account
            calls.append("verified-world-player")
            return True

    monkeypatch.setattr(module.subprocess, "Popen", Child)
    monkeypatch.setattr(module, "ControlledIPCClient", PrivateIPC)
    monkeypatch.setattr(
        module.ManagedAccountWorker, "stop",
        lambda worker: (calls.append("stopped"), worker.router.drop(worker.account.id)),
    )
    router = SimpleNamespace(
        fallback=SimpleNamespace(has_account=lambda _a: False),
        use=lambda aid, path: calls.append(("routed", aid, path)),
        drop=lambda aid: calls.append(("dropped", aid)),
    )
    workers = BrowserCookieWorkers(owner, router, launch_timeout=1)
    assert owner.status("alpha") == "not_connected"
    workers.start(account)
    assert owner.status("alpha") == "authenticated"
    assert calls.index("verified-world-player") < calls.index(
        ("routed", "alpha", descriptor)
    )
    with pytest.raises(RecoveryWorkerError, match="Another worker owns"):
        workers.start(account)
    workers.close()
    assert owner.status("alpha") == "not_connected"
    assert ("dropped", "alpha") in calls


def test_failed_worker_bootstrap_does_not_falsely_authenticate(
    monkeypatch, tmp_path, account_owner,
):
    import daedalus.browser_cookie_workers as module

    account, owner = account_owner
    monkeypatch.setattr(module.RecoveryWorkers, "_descriptor",
                        staticmethod(lambda _account: tmp_path / "unused.json"))

    class CrashedChild:
        def __init__(self, command, *, stdin, stdout, stderr, env, start_new_session):
            self.stdin = __import__("io").BytesIO()
            self.pid = 1001

        def poll(self):
            return 1

    monkeypatch.setattr(module.subprocess, "Popen", CrashedChild)
    monkeypatch.setattr(module.ManagedAccountWorker, "stop", lambda worker: None)
    router = SimpleNamespace(fallback=SimpleNamespace(has_account=lambda _a: False))
    workers = BrowserCookieWorkers(owner, router, launch_timeout=0.1)
    with pytest.raises(RecoveryWorkerError, match="startup failed"):
        workers.start(account)
    assert owner.status("alpha") == "not_connected"
