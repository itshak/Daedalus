"""Qt-only, credential-free checks for original IkaBot Selenium GUI integration."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")
pytest.importorskip("selenium")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from daedalus.desktop import app as app_module
from daedalus.desktop.pages import AccountsPage, WarehousesPage
from daedalus.desktop.selenium_credentials import GameforgeCredentials
from daedalus.gui_preferences import GuiPreferences

ACCOUNTS = [
    {"id": "alpha", "world": "s301-en", "player": "Demo A",
     "label": "Alpha", "enabled": True, "session_status": "needs_assistance"},
    {"id": "beta", "world": "s301-en", "player": "Demo B",
     "label": "Beta", "enabled": True, "session_status": "authenticated"},
    {"id": "gamma", "world": "s301-en", "player": "Demo C",
     "label": "Gamma", "enabled": True, "session_status": "not_connected"},
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def dispose(widget, app):
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def test_accounts_single_all_and_selected_auto_login_are_available(app):
    page = AccountsPage()
    try:
        page.set_accounts(ACCOUNTS)
        requested = []
        page.native_browser_login_batch_requested.connect(requested.append)
        assert not page.auto_login_all_button.isEnabled()
        page.set_native_browser_login_enabled(True)
        assert page.auto_login_all_button.isEnabled()
        page.auto_login_all_button.click()
        assert requested == [["alpha", "beta", "gamma"]]
        page.set_native_browser_login_enabled(False)
        assert not page.auto_login_all_button.isEnabled()
    finally:
        dispose(page, app)


def test_warehouses_one_click_auto_login_requires_secure_backend_permission(app):
    page = WarehousesPage()
    try:
        page.set_accounts(ACCOUNTS)
        requests = []
        page.sign_in_all_requested.connect(requests.append)
        assert not page.sign_in_all_button.isEnabled()
        page.set_login_available(True)
        assert page.sign_in_all_button.isEnabled()
        page.sign_in_all_button.click()
        assert requests == [["alpha", "beta", "gamma"]]
        page.set_login_available(False)
        assert not page.sign_in_all_button.isEnabled()
    finally:
        dispose(page, app)


def test_login_queue_skips_authenticated_and_keeps_account_order(app, monkeypatch):
    monkeypatch.setattr(app_module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(
        app_module.MainWindow, "_auto_reconnect_securely", lambda self: None,
    )
    win = app_module.MainWindow()
    try:
        win.accounts_page.set_accounts(ACCOUNTS)
        win.accounts_page.set_native_browser_login_enabled(True)
        win.client = object()
        win._active_backend_url = "https://example.test"
        started = []
        reports = []
        monkeypatch.setattr(
            win, "_begin_native_browser_login", started.append,
        )
        monkeypatch.setattr(
            win, "_request", lambda action, **kwargs: reports.append((action, kwargs)),
        )
        win._start_automatic_login_batch(
            ["alpha", "beta", "gamma"], report_after=True,
        )
        assert started == ["alpha"]
        assert win._automatic_login_queue == ["gamma"]
        win._automatic_login_current = None  # simulated completed backend ticket
        win._continue_automatic_login_batch()
        assert started == ["alpha", "gamma"]
        win._automatic_login_current = None
        win._continue_automatic_login_batch()
        assert reports == [(
            "warehouses_all", {"task_payload": {"account_ids": ["alpha", "beta", "gamma"]}},
        )]
        assert win._automatic_login_origin is None
    finally:
        win.client = None
        dispose(win, app)


def test_switching_backend_clears_sign_in_queue(app, monkeypatch):
    monkeypatch.setattr(app_module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(
        app_module.MainWindow, "_auto_reconnect_securely", lambda self: None,
    )
    win = app_module.MainWindow()
    try:
        win.accounts_page.set_accounts(ACCOUNTS)
        win.accounts_page.set_native_browser_login_enabled(True)
        win.client = object()
        win._active_backend_url = "https://original.example"
        started = []
        monkeypatch.setattr(win, "_begin_native_browser_login", started.append)
        win._start_automatic_login_batch(["alpha", "gamma"])
        assert started == ["alpha"]
        win._active_backend_url = "https://new.example"
        win._automatic_login_current = None
        win._continue_automatic_login_batch()
        assert started == ["alpha"]
        assert win._automatic_login_queue == []
    finally:
        win.client = None
        dispose(win, app)


def test_login_dialog_reuses_mac_keychain_and_never_starts_browser_on_construct(
    app, monkeypatch,
):
    import daedalus.desktop.selenium_login_dialog as dialog_module

    class Store:
        def __init__(self, *args, **kwargs):
            pass
        def get_credentials(self):
            return GameforgeCredentials("fixture@example.test", "never-printed")

    monkeypatch.setattr(dialog_module, "GameforgeKeychain", Store)
    dialog = dialog_module.SeleniumLoginDialog(
        backend_url="https://example.test", account_id="alpha",
        world="s301-en", player="Demo A", ttl_seconds=600, auto_start=False,
    )
    try:
        assert dialog._credentials.email == "fixture@example.test"
        assert dialog._worker is None
        assert dialog.world == "s301-en"
        assert not dialog.password_input.text()
        assert dialog.result() != dialog.Accepted
    finally:
        dialog.discard_session()
        dispose(dialog, app)
