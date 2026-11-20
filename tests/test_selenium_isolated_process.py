"""Offline-only tests for killable, single-account Selenium child execution."""
from __future__ import annotations

import os
import sys
import time

import pytest

from daedalus.desktop import selenium_child as child
from daedalus.desktop.selenium_auth import GameforgeCredentials


def _request(**overrides):
    request = {
        "account_id": "account-a", "world": "s53-ru",
        "origin": "https://daedalus.example",
        "record": {"id": "account-a", "world": "s53-ru", "player": "Ais"},
        "sealed_vault": None, "remember": False, "credentials": None,
    }
    return {**request, **overrides}


def _credentials():
    return GameforgeCredentials("test@example.invalid", "fake-password")


def test_child_looks_up_keychain_and_browser_outside_gui(monkeypatch):
    output, called = [], []
    monkeypatch.setattr(child, "_emit", lambda kind, value=None: output.append((kind, value)))
    monkeypatch.setattr(child, "get_saved_login", lambda *a: _credentials())
    monkeypatch.setattr(child, "login_world", lambda cred, world, *, notify: (
        called.append((cred, world)) or notify("headless_login") or "synthetic-cookie"
    ))
    monkeypatch.setattr(child, "seal_login", lambda *a: {"encrypted": "fake"})

    assert child.execute(_request()) == 0
    assert called[0] == (_credentials(), "s53-ru")
    assert [kind for kind, _ in output] == [
        "stage", "credentials", "stage", "stage", "vault", "cookie",
    ]
    assert output[-1] == ("cookie", "synthetic-cookie")


def test_child_missing_saved_login_requests_gui_prompt_without_browser(monkeypatch):
    output = []
    monkeypatch.setattr(child, "_emit", lambda kind, value=None: output.append(kind))
    monkeypatch.setattr(child, "get_saved_login", lambda *a: None)
    monkeypatch.setattr(child, "legacy_warehouse_login", lambda *a: None)
    monkeypatch.setattr(child, "login_world", lambda *a, **kw: pytest.fail("No Chrome"))
    assert child.execute(_request()) == 0
    assert output == ["stage", "credentials_required"]


def test_child_manual_credentials_bypass_keychain_lookup(monkeypatch):
    output = []
    monkeypatch.setattr(child, "_emit", lambda kind, value=None: output.append(kind))
    monkeypatch.setattr(child, "get_saved_login", lambda *a: pytest.fail("No lookup"))
    monkeypatch.setattr(child, "login_world", lambda *a, **kw: "synthetic-cookie")
    assert child.execute(_request(credentials={
        "email": "test@example.invalid", "password": "fake-password",
    })) == 0
    assert output == ["credentials", "stage", "cookie"]


def test_process_worker_uses_local_child_ipc_and_receives_cookie(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from daedalus.desktop import selenium_worker as worker_mod

    app = QApplication.instance() or QApplication([])
    script = """
import sys,json
payload=json.loads(sys.stdin.buffer.readline())
assert payload['account_id'] == 'account-a'
print(json.dumps({'kind':'credentials','value':{
    'email':payload['credentials']['email'],
    'remember':False}}),flush=True)
print(json.dumps({'kind':'cookie','value':'fake-cookie'}),flush=True)
"""
    monkeypatch.setattr(worker_mod, "child_command", lambda: [sys.executable, "-u", "-c", script])
    worker = worker_mod.SeleniumLoginWorker(
        "s53-ru", _credentials(), origin="https://daedalus.example",
        account_id="account-a",
        record={"id": "account-a", "world": "s53-ru"},
    )
    received, failures, creds = [], [], []
    worker.cookie_ready.connect(received.append)
    worker.login_failed.connect(failures.append)
    worker.credentials_resolved.connect(lambda cred, saved: creds.append((cred, saved)))
    try:
        worker.start()
        assert worker.wait(4000)
        app.processEvents()
        assert received == ["fake-cookie"]
        assert creds == [("test@example.invalid", False)]
        assert not failures
    finally:
        worker.cancel()
        worker.deleteLater()


@pytest.mark.skipif(os.name != "posix", reason="Process-group cancellation requires POSIX")
def test_cancel_kills_stuck_isolated_helper_without_qt_deadlock(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from daedalus.desktop import selenium_worker as worker_mod

    app = QApplication.instance() or QApplication([])
    script = """
import sys,time,json
sys.stdin.buffer.readline()
print(json.dumps({'kind':'stage','value':'headless_login'}),flush=True)
time.sleep(90)
"""
    monkeypatch.setattr(worker_mod, "child_command", lambda: [sys.executable, "-u", "-c", script])
    worker = worker_mod.SeleniumLoginWorker(
        "s53-ru", _credentials(), origin="https://daedalus.example",
        account_id="account-a", record={"id": "account-a", "world": "s53-ru"},
    )
    stages, failures = [], []
    worker.stage_changed.connect(stages.append)
    worker.login_failed.connect(failures.append)
    try:
        worker.start()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and not stages:
            app.processEvents()
            time.sleep(0.01)
        assert stages == ["headless_login"], "Synthetic subprocess never started"
        start = time.monotonic()
        worker.cancel()
        assert worker.wait(2500), "Cancellation must not wait for WebDriver's timeout"
        assert time.monotonic() - start < 2.5
        app.processEvents()
        assert not failures
        assert worker._process is None
    finally:
        worker.cancel()
        worker.wait(3000)
        worker.deleteLater()


def test_frozen_launcher_dispatches_login_child_before_desktop():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "packaging" / "build_macos_app.py"
    spec = importlib.util.spec_from_file_location("daedalus_macos_packaging", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    launcher = module.launcher_source()
    assert "sys.argv[1:] == ['--selenium-child']" in launcher
    assert launcher.index("selenium_main()") < launcher.index("from daedalus.desktop import main")
    command = module.build_command(
        Path("/tmp/launcher.py"), output_dir=Path("/tmp/out"),
        work_dir=Path("/tmp/work"), spec_dir=Path("/tmp/spec"),
    )
    assert "daedalus.desktop.selenium_child" in command

@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups")
def test_kill_group_cleans_descendants_even_if_helper_already_exited(monkeypatch):
    import signal

    from daedalus.desktop.selenium_worker import SeleniumLoginWorker

    calls = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))
    class Exited:
        pid = 12345678
        def poll(self): return 0

    SeleniumLoginWorker._kill_group(Exited())
    assert calls == [(12345678, signal.SIGKILL)]


def test_private_diagnostics_are_rotated_and_never_store_login_material(tmp_path, monkeypatch):
    from daedalus.desktop import diagnostics

    monkeypatch.setattr(diagnostics.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(diagnostics.sys, "platform", "darwin")
    path = diagnostics.configure_desktop_diagnostics()
    assert path == tmp_path / "Library" / "Logs" / "Daedalus" / "desktop.log"
    assert path.exists()
    if os.name == "posix":
        assert path.stat().st_mode & 0o077 == 0
    assert diagnostics.configure_desktop_diagnostics() == path
