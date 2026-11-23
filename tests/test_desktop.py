"""Headless PySide6/Fluent smoke tests for native desktop migration.

These tests skip unless the optional desktop dependencies are installed.
The dedicated macOS workflow installs them and runs these tests explicitly.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtWidgets import QApplication, QLineEdit

from daedalus.desktop.app import MainWindow
from daedalus.desktop.pages import (
    AccountsPage,
    ConnectionPage,
    OperationsPage,
    WarehousesPage,
)
from daedalus.desktop.task_page import TasksPage


@pytest.fixture(scope="module")
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_full_fluent_navigation_constructs_without_backend(qt_app):
    window = MainWindow()
    try:
        assert window.windowTitle() == "Daedalus for Ikariam"
        assert not window.windowIcon().isNull()
        assert window.client is None
        assert isinstance(window.accounts_page, AccountsPage)
        assert isinstance(window.warehouses_page, WarehousesPage)
        assert isinstance(window.operations_page, OperationsPage)
        assert isinstance(window.connection_page, ConnectionPage)
        assert isinstance(window.tasks_page, TasksPage)
    finally:
        window.close()


def test_connection_token_is_masked_and_not_persisted(qt_app):
    page = ConnectionPage()
    assert page.token_input.echoMode() == QLineEdit.Password
    page.token_input.setText("x" * 48)
    page.set_connected(True)
    assert page.token_input.text() == ""
    assert "active for this session" in page.token_input.placeholderText()
    page.set_token_saved(True)
    assert "••••••" in page.token_input.placeholderText()
    assert "saved in Keychain" in page.token_input.placeholderText()
    assert page.token_input.text() == ""
    assert "Connected" in page.status_label.text()
    page.close()


def test_accounts_page_reports_real_nonsecret_states(qt_app):
    page = AccountsPage()
    page.set_accounts(
        [{"id": "alpha", "world": "s301-en", "player": "Example", "enabled": True,
          "session_status": "needs_assistance", "label": "Primary"}]
    )
    assert page.table.rowCount() == 1
    assert page.table.item(0, 4).text() == "✕"
    assert "needs sign-in assistance" in page.table.item(0, 4).toolTip()
    assert page.table.item(0, 5).text() == "?"
    assert "not been checked" in page.table.item(0, 5).toolTip()
    page.set_connected_ids(["alpha"])
    assert page.table.item(0, 5).text() == "✓"
    assert "worker is attached" in page.table.item(0, 5).toolTip()
    page.set_connected_ids([])
    assert page.table.item(0, 5).text() == "✕"
    assert "No IkaBot worker" in page.table.item(0, 5).toolTip()
    page.close()


def test_operations_page_shows_inventory_without_enabling_execution(qt_app):
    page = OperationsPage()
    page.set_operations(
        [
            {"name": "constructionList", "kind": "background_task",
             "module": "ikabot.function.constructionList", "parameters": ["city_id"]},
            {"name": "getStatus", "kind": "interactive_menu",
             "module": "ikabot.function.getStatus", "parameters": []},
        ]
    )
    assert page.table.rowCount() == 2
    assert "Read-only" in page.status_label.text()
    page.search_input.setText("construction")
    assert page.table.rowCount() == 1
    page.close()


def test_warehouse_view_preserves_220k_filter_and_unknown_values(qt_app):
    page = WarehousesPage()
    page.set_accounts(
        [{"id": "alpha", "label": "Primary", "world": "s301-en", "player": "Example"}]
    )
    assert page.selected_account_id() == "alpha"
    page.set_snapshots(
        "alpha",
        [
            {"city_name": "Athens", "captured_at": "2026-11-18",
             "resources": {"unsecured": {"wood": 150_000, "wine": 80_000,
                                        "marble": 0, "glass": 0, "sulfur": 0},
                           "capacity": 500_000}},
            {"city_name": "Ephesus", "resources": {"unsecured": {"wood": 10_000}}},
        ],
    )
    assert page.table.rowCount() == 2
    assert page.table.item(1, 4).text() == "—"  # unknown marble is not zero
    page.only_220k.setChecked(True)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "Athens"
    page.close()
    page.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qt_app.processEvents()


def test_task_page_requires_backend_enablement_before_actions(qt_app):
    page = TasksPage()
    try:
        assert not page.start_button.isEnabled()
        assert not page.refresh_button.isEnabled()
        page.set_accounts([
            {"id": "alpha", "label": "Primary", "world": "s301-en", "player": "Example", "enabled": True},
            {"id": "disabled", "label": "Disabled", "world": "s302-en", "player": "Other", "enabled": False},
        ])
        page.set_capabilities([
            {"name": "constructionList", "kind": "background_task"},
            {"name": "getStatus", "kind": "menu_only"},
        ], enabled=False)
        assert page.selected_account_id() == "alpha"
        assert page.account_combo.count() == 1
        assert page.task_combo.count() == 1
        assert not page.start_button.isEnabled()
        page.set_capabilities([
            {"name": "constructionList", "kind": "background_task"},
        ], enabled=True)
        assert not page.start_button.isEnabled()  # readiness must be checked
        page.set_preflight({"account_id": "alpha", "task": "constructionList", "ready": True, "reason": "none"})
        # Readiness is not a substitute for an actual validated construction queue.
        assert not page.start_button.isEnabled()
        assert page.refresh_button.isEnabled()
        captured = []
        page.refresh_requested.connect(captured.append)
        page._refresh()
        assert captured == ["alpha"]
        page.set_tasks({
            "engine_tasks": [{"task_id": "f" * 24, "pid": 81001, "task": "constructionList", "status": "running"}],
            "requests": [],
        })
        assert page.task_table.rowCount() == 1
        page.set_capabilities([], enabled=False)
        assert not page.start_button.isEnabled()
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_reconnect_with_current_client_only_requests_readonly_handshake(qt_app, monkeypatch):
    window = MainWindow()
    actions = []
    existing = object()
    window.client = existing
    monkeypatch.setattr(window, "_launch", lambda client, action: actions.append((client, action)))
    try:
        window._reconnect()
        assert actions == [(existing, "connect")]
        assert all(action != "task_start" for _, action in actions)
        window.client = None
    finally:
        window.close()


def test_saved_connection_is_opt_in_and_never_written_to_text_inputs(qt_app, monkeypatch):
    import daedalus.desktop.app as module

    window = MainWindow()
    stored = []
    token = "synthetic-only-" + ("x" * 32)
    url = "http://127.0.0.1:8765"

    class FakeClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake = FakeClient()
    monkeypatch.setattr(module, "remember_connection", lambda *args: stored.append(args))
    notices = []
    monkeypatch.setattr(module.InfoBar, "success", lambda title, message, **kw: (
        notices.append((title, message))
    ))
    try:
        window._pending_client = fake
        window._pending_preferences = (url, token)
        window._on_completed("connect", {"accounts": [], "capabilities": {"operations": []}})
        assert window.client is fake
        assert stored == [(url, token)]
        assert window.connection_page.token_input.text() == ""
        assert "saved in Keychain" in window.connection_page.token_input.placeholderText()
        assert token not in window.connection_page.status_label.text()
        assert token not in window.connection_page.token_input.placeholderText()
        assert notices == [(
            "Connected to Daedalus",
            "Secure connection verified. You can now open Overview or Accounts.",
        )]
    finally:
        window.close()


def test_failed_new_connection_discloses_old_session_remains(qt_app, monkeypatch):
    window = MainWindow()

    class ExistingClient:
        def close(self):
            pass

    window.client = ExistingClient()
    window.connection_page.set_connected(True)
    monkeypatch.setattr(window, "_notice", lambda *_args: None)
    try:
        window._on_failed("connect", "401 unauthorized")
        assert "New connection failed" in window.connection_page.status_label.text()
        assert "previously verified backend" in window.connection_page.status_label.text()
        assert window.connection_page.overview_button.isEnabled()
    finally:
        window.close()


def test_warehouse_island_grouping_and_text_export(qt_app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    page = WarehousesPage()
    page.set_accounts([
        {"id": "alpha", "label": "Primary", "world": "s301-en", "player": "Example"}
    ])
    page.set_snapshots("alpha", [
        {"city_name": "Unknown Isle", "island": None,
         "resources": {"unsecured": {"wine": 0}}},
        {"city_name": "Athens", "island": "1:2", "island_resource": "wine",
         "resources": {"unsecured": {"wood": 300_000, "wine": 0}}},
        {"city_name": "Ephesus", "island": "1:2", "island_resource": "wine",
         "resources": {"unsecured": {"wood": 10_000, "wine": None}}},
    ])
    try:
        page.group_island.setChecked(True)
        assert [page.table.item(i, 0).text() for i in range(3)] == [
            "Athens", "Ephesus", "Unknown Isle",
        ]
        path = tmp_path / "warehouse.txt"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *_args, **_kwargs: (str(path), "Text"),
        )
        page._save("txt")
        content = path.read_text(encoding="utf-8")
        assert content.count("===== 1:2 (Вино) =====") == 1
        assert "Вино:\t0" in content and "Вино:\t—" in content
        assert "Daedalus warehouse report" not in content
        assert "Primary" not in content
        page._copy_islands()
        assert qt_app.clipboard().text() == content
        page.only_220k.setChecked(True)
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "Athens"
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_native_account_metadata_editor_is_opt_in_and_confirmed(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = AccountsPage()
    current = {
        "id": "alpha", "world": "s301-en", "player": "Example",
        "label": "Example", "enabled": True,
    }
    page.set_accounts([{**current, "session_status": "not_connected"}])
    assert not page.create_button.isEnabled()
    assert not page.toggle_button.isEnabled()
    seen = []
    page.account_change_requested.connect(lambda revision, rows: seen.append((revision, rows)))
    try:
        page.set_editable_config({
            "enabled": True, "revision": "a" * 64, "accounts": [current],
        })
        assert page.create_button.isEnabled()
        assert page.toggle_button.isEnabled()
        page.table.selectRow(0)
        monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.No)
        page._toggle()
        assert seen == []  # Denial never triggers backend mutation.
        monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.Yes)
        page._toggle()
        assert seen == [("a" * 64, [{**current, "enabled": False}])]
        monkeypatch.setattr(page, "_metadata_dialog", lambda existing=None: {
            "id": "beta", "world": "s302-en", "player": "Second",
            "label": "Second", "enabled": True,
        })
        page._create()
        assert len(seen[-1][1]) == 2
        page._remove()
        assert seen[-1][1] == []
        page.set_editable_config({"enabled": False, "revision": None, "accounts": []})
        assert not page.create_button.isEnabled()
        assert not page.toggle_button.isEnabled()
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_login_assistance_requires_selected_account_and_separate_consent(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = AccountsPage()
    row = {
        "id": "alpha", "world": "s301-en", "player": "Alice",
        "label": "Alice", "enabled": True, "session_status": "needs_assistance",
    }
    page.set_accounts([row])
    seen_checks = []
    seen_approvals = []
    page.assistance_check_requested.connect(seen_checks.append)
    page.assistance_approve_requested.connect(
        lambda account_id, ticket_id: seen_approvals.append((account_id, ticket_id))
    )
    ticket_id = "12345678-1234-4123-8123-123456789abc"
    try:
        assert not page.assistance_check_button.isEnabled()
        assert not page.assistance_approve_button.isEnabled()
        page.table.selectRow(0)
        assert page.assistance_check_button.isEnabled()
        page._check_assistance()
        assert seen_checks == ["alpha"]
        page.set_assistance({"enabled": True, "account_id": "alpha", "ticket": {
            "ticket_id": ticket_id, "reason": "manual_challenge",
            "state": "waiting_operator",
        }})
        assert page.assistance_approve_button.isEnabled()
        monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.No)
        page._approve_assistance()
        assert seen_approvals == []
        monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.Yes)
        page._approve_assistance()
        assert seen_approvals == [("alpha", ticket_id)]
        page.set_assistance({"enabled": True, "account_id": "alpha", "ticket": {
            "ticket_id": ticket_id, "reason": "manual_challenge",
            "state": "operator_ready",
        }})
        assert not page.assistance_approve_button.isEnabled()
        page.set_assistance({"enabled": False, "account_id": "alpha", "ticket": None})
        assert "not enabled" in page.assistance_status.text()
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_synthetic_demo_connect_is_labeled_in_fluent_ui(qt_app):
    window = MainWindow()
    try:
        window._on_completed("connect", {
            "health": {"mode": "synthetic_demo", "synthetic_demo": True},
            "accounts": [{
                "id": "demo_alpha", "world": "s999-en", "player": "DemoExplorer",
                "label": "DEMO — Explorer", "enabled": True,
                "session_status": "not_connected", "synthetic": True,
            }],
            "capabilities": {"operations": [], "structured_engine_dispatch": False,
                             "synthetic_demo": True},
            "account_config": {"enabled": False, "revision": None, "accounts": []},
        })
        assert "SYNTHETIC DEMO" in window.windowTitle()
        assert "SYNTHETIC DEMO" in window.connection_page.status_label.text()
        assert "SYNTHETIC DEMO" in window.warehouses_page.demo_note.text()
        assert not window.accounts_page.create_button.isEnabled()
        assert not window.tasks_page.start_button.isEnabled()
        assert window.accounts_page.table.item(0, 0).text().startswith("DEMO")
    finally:
        window.close()
        window.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_native_monitor_requires_account_selection_opt_in_and_consent(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = AccountsPage()
    account = {
        "id": "alpha", "world": "s301-en", "player": "Example",
        "enabled": True, "label": "Synthetic", "session_status": "not_connected",
    }
    requests = []
    page.monitor_requested.connect(requests.append)
    try:
        page.set_accounts([account])
        assert not page.monitor_button.isEnabled()
        page.set_monitoring_enabled(True)
        assert not page.monitor_button.isEnabled()
        page.table.selectRow(0)
        assert page.monitor_button.isEnabled()
        monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.No)
        page._monitor_selected()
        assert requests == []
        monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.Yes)
        page._monitor_selected()
        assert requests == ["alpha"]
        page.set_monitoring_enabled(False)
        assert not page.monitor_button.isEnabled()
        page._monitor_selected()
        assert requests == ["alpha"]
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_native_assistance_notification_is_nonsecret_and_only_once(qt_app, monkeypatch):
    window = MainWindow()
    shown = []
    monkeypatch.setattr(window, "_notice", lambda title, content: shown.append((title, content)))
    sample = {"enabled": True, "tickets": [{
        "account_id": "alpha",
        "ticket_id": "12345678-1234-4123-8123-123456789abc",
        "reason": "session_expired", "state": "waiting_operator",
    }]}
    try:
        window._on_completed("assistance_pending", sample)
        window._on_completed("assistance_pending", sample)
        assert len(shown) == 1
        assert shown[0][0] == "Manual account assistance needed"
        assert "12345678" not in str(shown)
        assert "session_expired" not in str(shown)
        window._on_completed("monitor_attach", {
            "account_id": "alpha", "status": "monitoring_existing_session",
        })
        assert shown[-1][0] == "Session monitoring enabled"
    finally:
        window.close()
        window.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()


def test_native_oneclick_demo_shows_consent_action_without_token(qt_app, monkeypatch):
    page = ConnectionPage()
    invoked = []
    page.demo_requested.connect(lambda: invoked.append(True))
    try:
        page.demo_button.click()
        assert invoked == [True]
        assert "offline demo" in page.demo_button.text().lower()
        assert page.token_input.text() == ""
    finally:
        page.close()


def test_native_oneclick_demo_does_not_persist_ephemeral_bearer(qt_app, monkeypatch):
    window = MainWindow()
    attempted = []
    monkeypatch.setattr(
        window, "_connect",
        lambda url, token: attempted.append(
            (url, token, window.connection_page.remember_checkbox.isChecked())
        ),
    )
    try:
        window.connection_page.remember_checkbox.setChecked(True)
        window._start_offline_demo()
        assert window._embedded_demo is not None
        assert window._embedded_demo.running
        assert attempted
        url, token, saved_during_demo = attempted[0]
        assert url.startswith("http://127.0.0.1:")
        assert len(token) >= 32
        assert saved_during_demo is False
        assert window.connection_page.remember_checkbox.isChecked()
        assert window.connection_page.token_input.text() == ""
        # Reusing the same explicitly started demo does not spawn another backend.
        window._start_offline_demo()
        assert attempted[1] == attempted[0]
    finally:
        backend = window._embedded_demo
        window.close()
        assert backend is not None
        assert not backend.running
