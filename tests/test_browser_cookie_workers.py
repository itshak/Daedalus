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


def test_real_cookie_child_reads_both_protected_bindings_and_starts_ipc(
    monkeypatch,
):
    """Exercise the actual child.main, not a fake Popen (regression: TypeError).

    Mocked bindings retain the production two-argument signature. Old code
    accidentally passed only the account and silently exited with code 1.
    """
    import io
    import json
    import sys
    from types import ModuleType

    import daedalus.browser_cookie_child as child
    import daedalus.saved_session_recovery as saved

    account = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    calls = []
    class HTTP:
        def close(self):
            calls.append("http_closed")

    session = SimpleNamespace(logged=True, s=HTTP())
    def fake_email(row, store):
        assert (row.id, row.world, row.player) == (account.id, account.world, account.player) and store is None
        calls.append("email")
        return "synthetic@example.invalid"

    def fake_cookie(row, store):
        assert (row.id, row.world, row.player) == (account.id, account.world, account.player) and store is None
        calls.append("cookie")
        return "X" * 48

    def fake_restore(row, email, cookie):
        assert (row.id, row.world, row.player) == (account.id, account.world, account.player)
        assert email == "synthetic@example.invalid"
        assert cookie == "X" * 48
        calls.append("restore")
        return session

    def fake_verify(session_value, row):
        assert session_value is session and (row.id, row.world, row.player) == (account.id, account.world, account.player)
        calls.append("attested")

    monkeypatch.setattr(saved, "_email_binding", fake_email)
    monkeypatch.setattr(saved, "_world_cookie_binding", fake_cookie)
    monkeypatch.setattr(saved, "_real_restore", fake_restore)
    monkeypatch.setattr(saved, "verify_restored_identity", fake_verify)
    ipc = ModuleType("ikabot.helpers.ipc")
    ipc.start_dedicated_ipc_server = lambda restored: (
        calls.append("ipc_started") or object()
    )
    ipc.stop_ipc_server = lambda: calls.append("ipc_stopped")
    for name in ("ikabot", "ikabot.helpers"):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "ikabot.helpers.ipc", ipc)
    request = json.dumps({
        "id": account.id, "world": account.world, "player": account.player,
    }).encode() + b"\n"
    monkeypatch.setattr(child.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(request)))
    def stop_loop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(child.time, "sleep", stop_loop)
    assert child.main() == 0
    assert calls == [
        "email", "cookie", "restore", "attested", "ipc_started",
        "ipc_stopped", "http_closed",
    ]


def test_saved_native_worker_startup_restores_each_account_only_when_bound(
    monkeypatch, tmp_path,
):
    from daedalus import browser_cookie_workers as workers_module
    import daedalus.saved_session_recovery as saved

    accounts = [
        Account("alpha", "s301-en", "Alice", "Alice", True),
        Account("beta", "s301-en", "Bob", "Bob", True),
        Account("gamma", "s301-en", "Carol", "Carol", False),
    ]
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    router = SimpleNamespace()
    workers = workers_module.BrowserCookieWorkers(owner, router)
    invoked = []
    monkeypatch.setattr(
        saved, "_email_binding",
        lambda row, store: "synthetic@example.invalid",
    )
    monkeypatch.setattr(
        saved, "_world_cookie_binding",
        lambda row, store: "X" * 48 if row.id == "alpha" else None,
    )
    monkeypatch.setattr(workers, "start", lambda row: invoked.append(row.id))
    with pytest.raises(ValueError, match="consent"):
        workers.restore_saved(accounts, confirmed=False)
    outcome = workers.restore_saved(accounts, confirmed=True)
    assert invoked == ["alpha"]
    assert outcome == {"connected": 1, "missing_binding": 1, "unavailable": 0}
