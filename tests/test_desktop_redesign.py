"""End-user navigation, novice setup and explicit safety boundaries, no Gameforge."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtWidgets import QApplication

from daedalus.desktop.app import MainWindow
from daedalus.desktop.home_page import HomePage
from daedalus.desktop.pages import OperationsPage
from daedalus.desktop.task_page import TasksPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _accounts():
    return [
        {"id": "alpha", "player": "A", "label": "Offline", "enabled": True,
         "session_status": "not_connected"},
        {"id": "beta", "player": "B", "label": "Connected", "enabled": True,
         "session_status": "authenticated"},
    ]


def test_home_prioritizes_live_account_and_navigation_has_real_actions(app):
    page = HomePage()
    try:
        selected = []
        opened = []
        page.account_selected.connect(selected.append)
        page.view_warehouses.connect(lambda id: opened.append(("warehouse", id)))
        page.manage_automations.connect(lambda id: opened.append(("automation", id)))
        page.set_connected(True)
        page.set_accounts(_accounts())
        assert page.selected_account_id() == "beta"
        assert "2 accounts" in page.account_summary.text()
        assert "1 authenticated" in page.account_summary.text()
        assert page.warehouse_card.open_button.isEnabled()
        page.warehouse_card.open_button.click()
        page.automation_card.open_button.click()
        assert opened == [("warehouse", "beta"), ("automation", "beta")]
        page.select_account("alpha")
        assert page.selected_account_id() == "alpha"
        assert not page.warehouse_card.open_button.isEnabled()
        assert not page.automation_card.open_button.isEnabled()
        assert selected[-1] == "alpha"
        page.set_connected(False)
        assert not page.warehouse_card.open_button.isEnabled()
    finally:
        page.close()


def test_operations_catalog_can_open_background_setup_but_not_interactive_only(app):
    page = OperationsPage()
    try:
        selected = []
        page.configure_requested.connect(selected.append)
        page.set_operations([
            {"name": "alertAttacks", "kind": "background_task", "module": "ikabot.function.alertAttacks"},
            {"name": "statusOnly", "kind": "interactive_menu", "module": "ikabot.function.statusOnly"},
        ])
        page.table.setCurrentCell(0, 0)
        assert page.configure_button.isEnabled()
        page.configure_button.click()
        assert selected == ["alertAttacks"]
        page.table.setCurrentCell(1, 0)
        assert not page.configure_button.isEnabled()
        page._configure_selected()
        assert selected == ["alertAttacks"]
    finally:
        page.close()


def test_window_routes_catalog_and_home_to_guided_automation_without_dispatch(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences
    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window.home_page.set_connected(True)
        window._show_accounts(_accounts())
        window._show_capabilities({
            "structured_engine_dispatch": False,
            "operations": [{"name": "alertAttacks", "kind": "background_task"}],
        })
        assert window.home_page.objectName() == "home_page"
        assert window.tasks_page.objectName() == "tasks_page"
        window._configure_catalog_task("alertAttacks")
        assert window.tasks_page.selected_task_name() == "alertAttacks"
        window._view_home_automations("beta")
        assert window.tasks_page.selected_account_id() == "beta"
        assert not window.tasks_page.start_button.isEnabled()
    finally:
        window.close()


def test_guided_form_start_is_disabled_until_safe_readiness_reply(app):
    page = TasksPage()
    try:
        page.set_accounts([_accounts()[1]])
        page.set_capabilities([{ "name": "alertAttacks", "kind": "background_task",
            "config_fields": [{"name": "minutes", "type": "integer", "default": 20}] }], enabled=True)
        assert not page._advanced_visible
        assert page.config_editor.isHidden()
        assert page._form_inputs["minutes"].value() == 20
        assert not page.start_button.isEnabled()
        page.set_preflight({"account_id": "beta", "task": "alertAttacks",
                            "ready": False, "reason": "notifications_required"})
        assert not page.start_button.isEnabled()
        page.set_preflight({"account_id": "beta", "task": "alertAttacks",
                            "ready": True, "reason": "none"})
        assert page.start_button.isEnabled()
        assert page.select_task("alertAttacks")
        assert not page.start_button.isEnabled()  # changing selection requires new check
    finally:
        page.close()


def test_connection_screen_has_secure_ssh_option_without_exposing_token(app):
    from PySide6.QtWidgets import QLineEdit

    from daedalus.desktop.pages import ConnectionPage

    page = ConnectionPage()
    try:
        captured = []
        page.ssh_connect_requested.connect(lambda *args: captured.append(args))
        page.ssh_host_input.setText("debian@aiserver")
        page.token_input.setText("x" * 48)
        assert page.token_input.echoMode() == QLineEdit.Password
        page.ssh_button.click()
        assert captured == [("debian@aiserver", "x" * 48)]
        page.set_connected(True)
        assert page.token_input.text() == ""
    finally:
        page.close()


def test_secure_ssh_connect_receipt_reuses_connection_flow_and_closes_owned_tunnel(app, monkeypatch):

    import httpx

    import daedalus.desktop.app as module
    from daedalus.client import DaedalusClient
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    class FakeTunnel:
        def __init__(self):self.closed=False
        def close(self):self.closed=True
    tunnel = FakeTunnel()
    client = DaedalusClient("http://127.0.0.1:19995", "x"*48,
        transport=httpx.MockTransport(lambda _: httpx.Response(200,json={})))
    try:
        window._pending_ssh_destination = "debian@aiserver"
        window._pending_ssh_token = "x"*48
        window._on_completed("ssh_connect", {
            "client": client, "tunnel": tunnel,
            "result": {"health": {"service": "daedalus", "synthetic_demo": False},
                       "accounts": [], "capabilities": {"operations": [], "session_monitoring": False,
                         "structured_engine_dispatch": False},
                       "account_config": {"enabled": False}},
        })
        assert window.client is client
        assert window._ssh_tunnel is tunnel
        assert "Connected" in window.connection_page.status_label.text()
    finally:
        window.close()
    assert tunnel.closed


def test_home_automations_refreshes_managed_task_history_on_enter(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences
    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window.home_page.set_connected(True)
        window._show_accounts(_accounts())
        window._show_capabilities({"operations": [{"name": "alertAttacks",
            "kind": "background_task"}], "structured_engine_dispatch": False})
        requests = []
        monkeypatch.setattr(window, "_request", lambda action, **kwargs:
                            requests.append((action, kwargs)))
        # This test invokes the UI route with a mock connected client object;
        # no actual HTTP requests or task dispatches occur.
        window.client = object()
        window._view_home_automations("beta")
        assert requests == [("task_list", {"account_id": "beta"})]
        assert window.tasks_page.selected_account_id() == "beta"
        window.client = None
    finally:
        window.close()


def test_unconfirmed_receipt_in_preflight_disables_start_without_task_refresh(app):
    page = TasksPage()
    try:
        page.set_accounts([_accounts()[1]])
        page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}],
                              enabled=True)
        page.set_preflight({"account_id": "beta", "task": "alertAttacks",
            "ready": True, "reason": "none", "unresolved_request": True})
        assert not page.start_button.isEnabled()
        assert "reconciliation" in page.prerequisite_label.text()
    finally:
        page.close()


def test_secure_ssh_never_reuses_keychain_token_for_another_host(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences
    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(module, "load_ssh_destination", lambda: "trusted-host")
    monkeypatch.setattr(module, "saved_connection", lambda: ("http://127.0.0.1:8765", "x"*48))
    window = MainWindow()
    try:
        alerts = []
        monkeypatch.setattr(window, "_notice", lambda title, msg: alerts.append((title,msg)))
        window._connect_ssh("other-host", "")
        assert alerts
        assert window._worker is None
        assert window._pending_ssh_token is None
    finally:
        window.close()


def test_failed_start_queues_task_history_refresh_instead_of_retry(app, monkeypatch):
    from types import SimpleNamespace

    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window._show_accounts(_accounts())
        window.client = object()
        window._worker = SimpleNamespace(account_id="beta")
        requests = []
        notices = []
        monkeypatch.setattr(window, "_request", lambda action, **args: requests.append((action, args)))
        monkeypatch.setattr(window, "_notice", lambda title, message: notices.append((title,message)))
        window._on_failed("task_start", "Configure Telegram or Discord notifications")
        assert window._pending_task_refresh == "beta"
        assert "Automation not started" == notices[-1][0]
        assert requests == []  # no network re-dispatch or busy-race refresh
        window._on_worker_finished()
        assert requests == [("task_list", {"account_id": "beta"})]
        assert window._pending_task_refresh is None
        window.client = None
    finally:
        window.close()


def test_https_keychain_save_is_default_and_optional_ssh_is_hidden(app, monkeypatch):
    import daedalus.connection_prefs as prefs
    from daedalus.desktop.pages import ConnectionPage

    monkeypatch.setattr(prefs, "load_connection_url", lambda: None)
    page = ConnectionPage()
    try:
        assert page.remember_checkbox.isChecked()
        assert page.connect_button.text() == "Connect"
        assert page.url_input.text() == ""  # no fake local backend on a fresh Mac
        assert page.advanced_panel.isHidden()
        assert "HTTPS" in page.intro_label.text()
        assert page.demo_button.isHidden() is False or page.demo_button.parent() is page.connection_card
        page.advanced_button.click()
        assert not page.advanced_panel.isHidden()
        assert page.ssh_button.text() == "Use SSH fallback"
    finally:
        page.close()


def test_successful_https_login_saves_exact_token_only_to_keychain(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(module, "saved_connection", lambda: None)
    captured = []
    monkeypatch.setattr(module, "remember_connection", lambda url, tok: captured.append((url, tok)))

    class MockClient:
        def __init__(self, url, token):
            self._server = url
            self._token_length = len(token)
            self.closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "DaedalusClient", MockClient)
    window = MainWindow()
    try:
        dispatched = []
        monkeypatch.setattr(window, "_launch", lambda client, action: dispatched.append((client, action)))
        assert window.connection_page.remember_checkbox.isChecked()
        url = "https://controller.example.com"
        token = "x" * 48
        window._connect(url, token)
        assert dispatched[-1][1] == "connect"
        assert captured == []  # No token saved before backend acceptance
        window._on_completed("connect", {
            "health": {"service": "daedalus"}, "accounts": [],
            "capabilities": {"operations": [], "structured_engine_dispatch": False},
            "account_config": {"enabled": False},
        })
        assert captured == [(url, token)]
        assert "saved" in window.connection_page.keychain_status.text().lower()
        assert window.client._token_length == 48
    finally:
        window.close()


def test_startup_autoconnects_only_saved_https_and_token_is_url_scoped(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    current = [("http://127.0.0.1:8765", "x" * 48)]
    monkeypatch.setattr(module, "saved_connection", lambda: current[0])
    window = MainWindow()
    try:
        forwarded = []
        errors = []
        original_connect = window._connect
        monkeypatch.setattr(window, "_connect", lambda u, t, **_kw: forwarded.append((u, t)))
        monkeypatch.setattr(window, "_notice", lambda title, reason: errors.append(title))
        window._auto_reconnect_securely()
        assert forwarded == []
        current[0] = ("https://controller.example.com", "x" * 48)
        window._auto_reconnect_securely()
        assert forwarded == [current[0]]

        class MockClient:
            def __init__(self, url, token):
                self._server = url
            def close(self):
                pass

        monkeypatch.setattr(module, "DaedalusClient", MockClient)
        monkeypatch.setattr(window, "_connect", original_connect)
        monkeypatch.setattr(window, "_launch", lambda client, act: forwarded.append((client._server, act)))
        window._connect("https://other.example.com", "")
        assert errors[-1] == "API token required"
        assert len(forwarded) == 1
        window._connect("https://controller.example.com", "")
        assert forwarded[-1] == ("https://controller.example.com", "connect")
        assert window._pending_preferences is None
        assert window._pending_secret_saved
    finally:
        window.close()


def test_saved_https_reconnect_does_not_write_mac_keychain_again(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(module, "saved_connection", lambda: (
        "https://controller.example.com", "x" * 48,
    ))
    writes = []
    monkeypatch.setattr(module, "remember_connection", lambda *args: writes.append(args))
    class FakeClient:
        def __init__(self, url, token):
            self._server = url
        def close(self):
            pass
    monkeypatch.setattr(module, "DaedalusClient", FakeClient)
    window = MainWindow()
    try:
        monkeypatch.setattr(window, "_launch", lambda *args: None)
        window._auto_reconnect_securely()
        assert window._pending_secret_saved
        assert window._pending_preferences is None
        window._on_completed("connect", {
            "health": {"service": "daedalus"}, "accounts": [],
            "capabilities": {"operations": [], "structured_engine_dispatch": False},
            "account_config": {"enabled": False},
        })
        assert writes == []
        assert "saved" in window.connection_page.keychain_status.text().lower()
    finally:
        window.close()
