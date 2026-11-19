"""Headless Selenium desktop integration tests: synthetic accounts, no network."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from daedalus.desktop.selenium_auth import GameforgeCredentials
from daedalus.gui_preferences import GuiPreferences


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    import daedalus.desktop.app as desktop

    monkeypatch.setattr(desktop, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(desktop.MainWindow, "_auto_reconnect_securely", lambda self: None)
    win = desktop.MainWindow()
    win.client = SimpleNamespace(close=lambda: None)
    win._active_backend_url = "https://trusted-daedalus.example"
    win._show_accounts([
        {"id": "account-a", "world": "s53-ru", "player": "Xiaomi",
         "label": "Alpha", "enabled": True, "session_status": "not_connected"},
        {"id": "account-b", "world": "s53-ru", "player": "Omega",
         "label": "Beta", "enabled": True, "session_status": "needs_assistance"},
        {"id": "account-c", "world": "s53-ru", "player": "Gamma",
         "label": "Gamma", "enabled": True, "session_status": "authenticated"},
        {"id": "account-d", "world": "s53-ru", "player": "Disabled",
         "label": "Disabled", "enabled": False, "session_status": "not_connected"},
    ])
    win.accounts_page.set_native_browser_login_enabled(True)
    yield win
    win.close()
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def test_accounts_have_headless_single_all_selected_controls(window):
    page = window.accounts_page
    emitted = []
    # Observe emitted scope without starting the connected MainWindow login
    # pipeline (which would request a password dialog in an offline test).
    page.automatic_login_requested.disconnect(window._begin_automatic_logins)
    page.automatic_login_requested.connect(emitted.append)
    page._auto_all()
    assert emitted == [["account-a", "account-b", "account-c"]]
    page.table.setCurrentCell(0, 0)
    page._auto_this()
    assert emitted[-1] == ["account-a"]
    page.set_automatic_login_busy(True, "Signing in with headless Chrome")
    assert not page.auto_login_all_button.isEnabled()
    assert page.auto_cancel_button.isEnabled()
    page.set_automatic_login_busy(False)
    assert not page.auto_cancel_button.isEnabled()


def test_one_click_warehouse_all_starts_headless_login_for_missing(window, monkeypatch):
    import daedalus.desktop.app as desktop

    calls = []
    monkeypatch.setattr(
        desktop, "get_saved_login",
        lambda *args: GameforgeCredentials("test@example.invalid", "synthetic"),
    )
    monkeypatch.setattr(window, "_request", lambda action, **kw: calls.append((action, kw)))
    window._request_warehouse_scope(
        "warehouses_all", ["account-a", "account-b", "account-c"]
    )
    assert window._automatic_login_active is True
    assert window._automatic_login_current == "account-a"
    assert window._automatic_login_queue == ["account-b"]
    assert window._automatic_login_report == (
        "warehouses_all", ["account-a", "account-b", "account-c"]
    )
    assert calls == [("native_login_start", {"account_id": "account-a"})]


def test_browser_handoff_from_selenium_contains_only_ciphertext(window, monkeypatch):
    import daedalus.desktop.app as desktop

    sent = []
    monkeypatch.setattr(window, "_request", lambda action, **kw: sent.append((action, kw)))
    monkeypatch.setattr(desktop, "encrypt_mac_world_session", lambda challenge, record, cookie,
                        *, email: {"confirmed": True, "client_key": "test-client",
                                   "nonce": "test-nonce", "ciphertext": "sealed"})
    window._automatic_login_active = True
    window._automatic_login_current = "account-a"
    window._automatic_login_credentials = GameforgeCredentials(
        "private@example.invalid", "do-not-transfer-this-password"
    )
    window._automatic_login_challenge = {
        "account_id": "account-a", "world": "s53-ru", "ticket_id": "fake-ticket",
    }
    window._selenium_success("private-world-cookie")
    assert sent[0][0] == "native_login_complete"
    payload = sent[0][1]["task_payload"]
    assert payload["envelope"]["ciphertext"] == "sealed"
    assert "private-world-cookie" not in str(payload)
    assert "do-not-transfer-this-password" not in str(payload)
    assert "private@example.invalid" not in str(payload)


def test_auto_login_challenge_routes_to_selenium_not_manual(window, monkeypatch, app):
    started, manual = [], []
    monkeypatch.setattr(window, "_launch_headless_selenium", started.append)
    monkeypatch.setattr(window, "_open_native_browser_login", manual.append)
    window._automatic_login_active = True
    window._pending_native_login_challenge = {
        "account_id": "account-a", "world": "s53-ru", "ticket_id": "synthetic",
    }
    window._on_worker_finished()
    app.processEvents()
    assert len(started) == 1
    assert manual == []


def test_cancelled_login_cannot_launch_browser(window, monkeypatch):
    callbacks = []
    monkeypatch.setattr(window, "_request", lambda action, **kw: callbacks.append(action))
    window._automatic_login_active = True
    window._automatic_login_current = "account-a"
    window._automatic_login_credentials = GameforgeCredentials(
        "private@example.invalid", "synthetic-password"
    )
    window._cancel_automatic_logins()
    window._launch_headless_selenium({
        "account_id": "account-a", "world": "s53-ru", "ticket_id": "fake",
    })
    assert window._selenium_worker is None
    assert "native_login_cancel" in callbacks


def test_sequential_login_resume_waits_for_selenium_and_api_completion(window, monkeypatch, app):
    queued = []
    monkeypatch.setattr(window, "_advance_automatic_login", lambda: queued.append("advance"))
    window._automatic_login_pending_advance = True
    window._worker = None
    window._selenium_worker = SimpleNamespace(deleteLater=lambda: None)
    window._selenium_finished()
    app.processEvents()
    assert queued == ["advance"]
    assert window._automatic_login_pending_advance is False


def test_completed_automatic_login_marks_verified_only_after_server_receipt(window, monkeypatch):
    import daedalus.desktop.app as desktop

    monkeypatch.setattr(desktop, "remember_login", lambda *_args: None)
    window._automatic_login_active = True
    window._automatic_login_current = "account-a"
    window._automatic_login_credentials = GameforgeCredentials(
        "synthetic@example.invalid", "synthetic"
    )
    window._automatic_login_save_credentials = True
    window._on_completed("native_login_complete", {
        "account_id": "account-a", "status": "world_cookie_bound",
    })
    assert window._automatic_login_successes == 1
    assert window._automatic_login_current is None
    assert window._automatic_login_pending_advance is True
