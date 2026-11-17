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
