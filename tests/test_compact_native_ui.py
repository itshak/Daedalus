"""UI-only compact Mac layout regression tests, using synthetic fixtures."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from daedalus.desktop.home_page import HomePage
from daedalus.desktop.pages import AccountsPage, WarehousesPage
from daedalus.desktop.task_page import TasksPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_accounts_are_table_first_with_compact_commands(app):
    page = AccountsPage()
    try:
        assert page.layout().indexOf(page.table) >= 0
        assert page.create_button.text() == "Add account"
        assert not hasattr(page, "master_detail")
        assert page.advanced_recovery_panel.isHidden()
        page.set_accounts([
            {"id": "a", "label": "Alpha", "world": "s1", "player": "A",
             "enabled": True, "session_status": "authenticated"},
            {"id": "b", "label": "Beta", "world": "s2", "player": "B",
             "enabled": True, "session_status": "needs_assistance"},
        ])
        assert page.table.rowCount() == 2
        assert page.selected_report_account_ids() == ["a", "b"]
        assert "Sign in all" == page.auto_login_all_button.text()
        menu = page.more_button.menu()
        assert menu is not None
        names = [a.text() for a in menu.actions()]
        assert "Edit account…" in names
        assert "Advanced recovery…" in names
        page.table.item(1, 6).setCheckState(Qt.Unchecked)
        assert page.selected_report_account_ids() == ["a"]
    finally:
        page.close()


def test_warehouses_keep_all_accounts_and_printing_in_compact_toolbar(app):
    page = WarehousesPage()
    try:
        assert page.load_all_button.text() == "All accounts"
        assert page.layout().indexOf(page.status_label) < page.layout().indexOf(page.table)
        assert "Print grouped report…" in [
            action.text() for action in page.export_button.menu().actions()
        ]
        assert page.table.columnCount() == len(page._COLUMNS)
    finally:
        page.close()


def test_overview_shortcuts_are_short_rows(app):
    page = HomePage()
    try:
        assert page.all_warehouse_card.maximumHeight() <= 72
        assert page.automation_card.maximumHeight() <= 72
        assert page.all_warehouse_card.open_button.text() == "Load all warehouses"
    finally:
        page.close()


def test_automation_gallery_is_optional_but_keeps_task_selection(app):
    page = TasksPage()
    try:
        assert not page._gallery_open
        assert page.discovery_scroll.isHidden()
        page.set_accounts([{"id": "a", "label": "Alpha", "enabled": True,
                            "session_status": "authenticated"}])
        page.set_capabilities([
            {"name": "alertAttacks", "kind": "background_task"}
        ], enabled=False)
        assert page.task_combo.count() == 1
        page._toggle_gallery()
        assert page._gallery_open
        assert page.browse_button.text() == "Hide automation gallery"
        assert not page.start_button.isEnabled()
    finally:
        page.close()


def test_account_identity_world_flag_and_status_icons(app):
    page = AccountsPage()
    try:
        page.set_accounts([
            {"id": "saved-01", "label": "Imported IkaBot identity 01",
             "email": "synthetic@example.invalid", "world": "s58-ru",
             "player": "Player", "enabled": True,
             "session_status": "authenticated"},
            {"id": "saved-02", "label": "Imported IkaBot identity 02",
             "world": "s53-ru", "player": "Other", "enabled": False,
             "session_status": "not_connected"},
        ])
        assert page.table.item(0, 0).text() == "synthetic@example.invalid"
        assert page.table.item(1, 0).text() == "Other"
        assert page.table.item(0, 1).text() == "🇷🇺 S58"
        assert page.table.item(1, 1).text() == "🇷🇺 Eurydike · S53"
        assert page.table.item(0, 3).text() == "✓"
        assert page.table.item(1, 3).text() == "✕"
        assert page.table.item(0, 4).text() == "✓"
        assert page.table.item(1, 4).text() == "✕"
        assert page.table.item(0, 5).text() == "?"
        assert "not been checked" in page.table.item(0, 5).toolTip()
        page.set_connected_ids(["saved-01"])
        assert page.table.item(0, 5).text() == "✓"
        assert page.table.item(1, 5).text() == "✕"
        assert "attached" in page.table.item(0, 5).toolTip()
    finally:
        page.close()
