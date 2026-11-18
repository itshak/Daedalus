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
