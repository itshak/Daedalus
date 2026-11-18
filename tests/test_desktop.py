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
    assert "Connected" in page.status_label.text()
    page.close()


def test_accounts_page_reports_real_nonsecret_states(qt_app):
    page = AccountsPage()
    page.set_accounts(
        [{"id": "alpha", "world": "s301-en", "player": "Example", "enabled": True,
          "session_status": "needs_assistance", "label": "Primary"}]
    )
    assert page.table.rowCount() == 1
    assert page.table.item(0, 4).text() == "needs_assistance"
    assert page.table.item(0, 5).text() == "Not checked"
    page.set_connected_ids(["alpha"])
    assert page.table.item(0, 5).text() == "Attached"
    page.set_connected_ids([])
    assert page.table.item(0, 5).text() == "Not attached"
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
        assert page.start_button.isEnabled()
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
    try:
        window._pending_client = fake
        window._pending_preferences = (url, token)
        window._on_completed("connect", {"accounts": [], "capabilities": {"operations": []}})
        assert window.client is fake
        assert stored == [(url, token)]
        assert window.connection_page.token_input.text() == ""
        assert token not in window.connection_page.status_label.text()
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
        {"city_name": "Athens", "island": "1:2",
         "resources": {"unsecured": {"wood": 300_000, "wine": 0}}},
        {"city_name": "Ephesus", "island": "1:2",
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
        assert content.count("Island 1:2") == 1
        assert "wine: 0" in content and "wine: —" in content
        page.only_220k.setChecked(True)
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "Athens"
    finally:
        page.close()
        page.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qt_app.processEvents()
