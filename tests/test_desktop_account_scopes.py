"""Multi-account Fluent desktop workflow contracts; entirely synthetic/offline."""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from daedalus.client import APIConnectionError
from daedalus.desktop.account_scope import AccountSelectionDialog
from daedalus.desktop.app import APIWorker, MainWindow
from daedalus.desktop.design_system import NAV_ICONS
from daedalus.desktop.pages import WarehousesPage
from daedalus.desktop.task_page import TasksPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _dispose(widget, app):
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def accounts(count=3):
    return [
        {"id": f"account-{i}", "label": f"Town {i}", "world": "s1-en",
         "player": f"Player {i}", "enabled": True, "session_status": "authenticated"}
        for i in range(count)
    ]


def test_navigation_has_unique_icons_and_only_one_regular_automation(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        assert len({icon.value for icon in NAV_ICONS.values()}) == len(NAV_ICONS) == 8
        assert window.military_page.objectName() == "military_page"
        assert NAV_ICONS["connection"] != NAV_ICONS["settings"]
        assert NAV_ICONS["automations"] != NAV_ICONS["activity"]
        assert window.tasks_page.objectName() == "tasks_page"
        assert len(window._task_views) == 1
        assert window._task_views[0] is window.tasks_page
        assert window.operations_page is window.tasks_page.catalog_panel
        assert hasattr(window.home_page, "all_warehouse_card")
    finally:
        _dispose(window, app)


def test_warehouse_all_accounts_and_arbitrary_selected_accounts(app):
    page = WarehousesPage()
    try:
        page.set_accounts(accounts(4))
        page.set_selected_accounts(["account-1", "account-3"])
        all_calls = []
        selected_calls = []
        page.load_all_requested.connect(all_calls.append)
        page.load_selected_requested.connect(selected_calls.append)
        page.load_all_button.click()
        assert all_calls == [["account-0", "account-1", "account-2", "account-3"]]
        page.load_selected_button.click()
        assert selected_calls == [["account-1", "account-3"]]
        assert page.load_selected_button.text() == "Selected (2)"
        page.set_accounts(accounts(4))
        assert page._included_ids == ["account-1", "account-3"]
    finally:
        _dispose(page, app)


def test_warehouse_more_than_32_uses_safe_full_read_path(app):
    page = WarehousesPage()
    try:
        page.set_accounts(accounts(40))
        page.set_selected_accounts([f"account-{i}" for i in range(35)])
        larger, short = [], []
        page.load_all_requested.connect(larger.append)
        page.load_selected_requested.connect(short.append)
        page._load_selected()
        assert len(larger[0]) == 35
        assert short == []
        page._load_all()
        assert len(larger[1]) == 40
    finally:
        _dispose(page, app)


def test_scoped_account_picker_select_all_and_some(app):
    dialog = AccountSelectionDialog(accounts(), ["account-1"])
    try:
        assert dialog.selected_ids() == ["account-1"]
        dialog.all_checkbox.setChecked(True)
        assert dialog.selected_ids() == ["account-0", "account-1", "account-2"]
        dialog.checkboxes["account-0"].setChecked(False)
        assert dialog.selected_ids() == ["account-1", "account-2"]
    finally:
        _dispose(dialog, app)


def test_automation_bulk_start_requires_approval_and_exact_accounts(app, monkeypatch):
    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_capabilities([{"name": "alertAttacks", "kind": "background_task",
                                 "config_fields": [{"name": "minutes", "type": "integer",
                                                    "default": 20}]}], enabled=True)
        page._bulk_account_ids = ["account-0", "account-2"]
        emitted = []
        page.batch_launch_requested.connect(lambda *args: emitted.append(args))
        confirmation_text = []
        def approve(*args, **kwargs):
            confirmation_text.append(str(args[2]))
            return QMessageBox.Yes
        monkeypatch.setattr(QMessageBox, "question", approve)
        page._start_selected()
        assert emitted == []
        page.confirm_box.setChecked(True)
        page._start_selected()
        assert len(emitted) == 1
        ids, task, config = emitted[0]
        assert ids == ["account-0", "account-2"]
        assert task == "alertAttacks"
        assert config == {"minutes": 20}
        assert len(confirmation_text) == 1
        assert "Player 0 · s1-en (account account-0)" in confirmation_text[0]
        assert "Player 2 · s1-en (account account-2)" in confirmation_text[0]
        assert "Player 1" not in confirmation_text[0]
    finally:
        _dispose(page, app)


def _run_batch(worker):
    completed = []
    failed = []
    worker.completed.connect(lambda action, response: completed.append(response))
    worker.failed.connect(lambda action, message: failed.append(message))
    worker.run()
    assert failed == []
    return completed[0]


def test_bulk_dispatch_rejects_any_blocked_account_before_game_mutation(app):
    class FakeBackend:
        def __init__(self):
            self.starts = []
        def task_preflight(self, aid, task):
            return {"ready": aid != "account-2", "reason": "notifications_required",
                    "unresolved_request": False}
        def start_task(self, aid, task, config, rid, *, confirmed):
            self.starts.append(aid)
            return {"status": "running"}

    backend = FakeBackend()
    result = _run_batch(APIWorker(backend, "task_start_batch", task_payload={
        "account_ids": ["account-0", "account-2"], "task": "alertAttacks", "config": {}
    }))
    assert backend.starts == []
    assert result["submitted"] == []
    assert result["blocked"][0]["account_id"] == "account-2"


def test_bulk_dispatch_stops_on_first_uncertain_receipt_without_retry(app):
    class FakeBackend:
        def __init__(self):
            self.starts = []
            self.rids = []
        def task_preflight(self, aid, task):
            return {"ready": True, "reason": "none", "unresolved_request": False}
        def start_task(self, aid, task, config, rid, *, confirmed):
            assert confirmed is True
            self.starts.append(aid)
            self.rids.append(rid)
            if aid == "account-1":
                raise APIConnectionError("Cannot connect to Daedalus backend")
            return {"status": "running"}

    backend = FakeBackend()
    result = _run_batch(APIWorker(backend, "task_start_batch", task_payload={
        "account_ids": ["account-0", "account-1", "account-2"],
        "task": "alertAttacks", "config": {"minutes": 20},
    }))
    assert backend.starts == ["account-0", "account-1"]
    assert result["halted"]["account_id"] == "account-1"
    assert len(result["submitted"]) == 1
    assert len(set(backend.rids)) == 2
    for rid in backend.rids:
        assert str(uuid.UUID(rid)) == rid


def test_multi_account_status_partial_result_is_not_fabricated(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_batch_status([
            {"account_id": "account-0", "engine_tasks": [
                {"task": "alertAttacks", "status": "running"}
            ], "requests": []},
            {"account_id": "account-1", "error": True},
            {"account_id": "account-2", "engine_tasks": [],
             "requests": [{"status": "unconfirmed"}]},
        ])
        assert page.multi_table.rowCount() == 3
        assert page.multi_table.item(0, 1).text() == "1"
        assert page.multi_table.item(1, 3).text() == "Unavailable"
        assert page.multi_table.item(2, 3).text() == "Needs review"
    finally:
        _dispose(page, app)


def test_fluent_automation_pivot_separates_configuration_and_history(app):
    page = TasksPage()
    try:
        assert page.stack.count() == 5
        page._open_catalog()
        assert page.stack.currentIndex() == 4
        page._show_section(3)
        assert page.stack.currentIndex() == 3
        page._show_section(1)
        assert page.stack.currentIndex() == 1
        page.select_workflow("wine")
        assert page.stack.currentIndex() == 0
    finally:
        _dispose(page, app)


def test_print_action_only_enabled_for_real_report_rows(app):
    page = WarehousesPage()
    try:
        page.set_accounts(accounts(2))
        assert not page.print_button.isEnabled()
        page.set_batch_snapshots([{"account_id": "account-0", "cities": [{
            "city_name": "Corinth", "resources": {"unsecured": {"wood": 7000}}
        }]}])
        assert page.print_button.isEnabled()
        assert "Print grouped report…" in [
            action.text() for action in page.export_button.menu().actions()
        ]
    finally:
        _dispose(page, app)


def test_overview_scrolls_in_a_short_mac_window(app):
    from PySide6.QtWidgets import QScrollArea

    from daedalus.desktop.home_page import HomePage

    page = HomePage()
    try:
        assert isinstance(page.content_scroll, QScrollArea)
        page.resize(900, 650)
        page.show()
        app.processEvents()
        assert page.all_warehouse_card.open_button.text() == "Load all warehouses"
        # Layout must scroll rather than clipping the final row of quick actions.
        assert page.content_scroll.verticalScrollBar().maximum() >= 0
        assert page.content_scroll.widget().layout().count() >= 5
    finally:
        _dispose(page, app)


def test_warehouse_print_toolbar_precedes_large_result_table(app):
    page = WarehousesPage()
    try:
        layout = page.layout()
        status_index = layout.indexOf(page.status_label)
        table_index = layout.indexOf(page.table)
        assert status_index > 0
        assert table_index > status_index
        assert layout.itemAt(status_index - 1).layout() is not None
        assert page.print_button.isEnabled() is False
    finally:
        _dispose(page, app)


def test_automation_parameter_form_uses_compact_height_for_one_field(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_capabilities([{
            "name": "alertAttacks", "kind": "background_task",
            "config_fields": [{"name": "minutes", "type": "integer", "default": 20}],
        }], enabled=True)
        assert page.parameter_scroll.height() <= 95
        assert page.parameter_scroll.maximumHeight() <= 100
        assert page.stack.count() == 5
    finally:
        _dispose(page, app)


def test_templates_include_wine_and_construction_related_tasks(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_capabilities([
            {"name": name, "kind": "background_task"} for name in (
                "tavernManager", "alertLowWine", "constructionList",
                "research", "alertAttacks",
            )
        ], enabled=True)
        page.select_workflow("wine")
        assert set(page._task_names) == {"tavernManager", "alertLowWine"}
        page.select_workflow("construction")
        assert set(page._task_names) == {"constructionList", "research"}
        page.select_workflow("all")
        assert len(page._task_names) == 5
    finally:
        _dispose(page, app)


def test_wine_alert_has_native_required_hours_and_safe_transfer_toggle(app):
    from PySide6.QtWidgets import QSpinBox

    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_capabilities([{
            "name": "alertLowWine", "kind": "background_task",
            "config_fields": [
                {"name": "hours", "type": "json", "required": True},
                {"name": "auto_transfer", "type": "boolean", "default": False},
                {"name": "transfer_amount", "type": "integer", "default": 0},
            ],
        }], enabled=True)
        hours = page._form_inputs["hours"]
        assert isinstance(hours, QSpinBox)
        with pytest.raises(ValueError, match="Choose a value"):
            page._form_config()  # no invented threshold

        hours.setValue(12)
        config = page._form_config()
        assert config == {"hours": 12, "auto_transfer": False, "transfer_amount": 0}
        page._form_inputs["auto_transfer"].setChecked(True)
        with pytest.raises(ValueError, match="positive transfer amount"):
            page._form_config()
        page._form_inputs["transfer_amount"].setValue(500)
        assert page._form_config()["transfer_amount"] == 500
    finally:
        _dispose(page, app)


def test_tavern_manager_native_hour_spinner_allows_explicit_one_time_run(app):
    from PySide6.QtWidgets import QSpinBox

    from daedalus.desktop.native_controls import TavernCitiesEditor

    page = TasksPage()
    try:
        page.set_accounts(accounts())
        page.set_capabilities([{
            "name": "tavernManager", "kind": "background_task",
            "config_fields": [
                {"name": "run_hours", "type": "json", "required": True},
                {"name": "cities_ids", "type": "json", "default": None},
            ],
        }], enabled=True)
        editor = page._form_inputs["cities_ids"]
        assert isinstance(editor, TavernCitiesEditor)
        assert "run_hours" not in page._form_inputs  # dedicated UI replaces raw JSON
        spinner = editor.interval
        assert isinstance(spinner, QSpinBox)
        with pytest.raises(ValueError, match="Load real tavern"):
            page._form_config()
        page.set_taverns({
            "account_id": page.selected_account_id(),
            "taverns": [{
                "city_id": 42, "city_name": "Athens", "wine": 10000,
                "has_tavern": True, "serving_level": 2, "wine_per_hour": 50,
                "satisfaction": 40, "population": 800, "capacity": 1000,
            }],
        })
        spinner.setValue(0)
        assert page._form_config() == {
            "cities_ids": None, "run_hours": 0, "notification_mode": 2,
        }
    finally:
        _dispose(page, app)


def test_automation_has_no_raw_plan_import(app):
    page = TasksPage()
    try:
        assert not hasattr(page, "import_config_button")
        assert not hasattr(page, "_import_advanced_config")
        assert not hasattr(page, "config_editor")
    finally:
        _dispose(page, app)


def test_configuration_dialog_summary_avoids_echoing_complex_private_values():
    from daedalus.desktop.task_presentation import configuration_summary

    summary = configuration_summary({
        "run_hours": 3,
        "routes": [{"private_secret": "do-not-show-me"}],
        "api_token": "a-sensitive-value",
    })
    assert "run hours: 3" in summary
    assert "routes: configured" in summary
    assert "do-not-show-me" not in summary
    assert "a-sensitive-value" not in summary



def test_all_account_warehouse_scope_is_not_silently_truncated_at_100(app):
    all_rows = accounts(125)
    picker = AccountSelectionDialog(all_rows, [a["id"] for a in all_rows])
    page = WarehousesPage()
    try:
        assert len(picker.selected_ids()) == 125
        page.set_accounts(all_rows)
        emitted = []
        page.load_all_requested.connect(emitted.append)
        page.load_all_button.click()
        assert emitted == [[a["id"] for a in all_rows]]

        class FakeReads:
            def warehouses(self, account_id):
                return []

        result = _run_batch(APIWorker(FakeReads(), "warehouses_all", task_payload={
            "account_ids": emitted[0]
        }))
        assert len(result) == 125
        assert all(row["cities"] == [] for row in result)
    finally:
        _dispose(picker, app)
        _dispose(page, app)


def test_all_account_automation_status_includes_disabled_without_bulk_mutation(app):
    rows = accounts(4)
    rows[1]["enabled"] = False
    page = TasksPage()
    try:
        page.set_accounts(rows)
        emitted = []
        page.batch_status_requested.connect(emitted.append)
        page.view_all_button.click()
        assert emitted == [[a["id"] for a in rows]]
        page.set_batch_status([
            {"account_id": a["id"], "engine_tasks": [], "requests": []}
            for a in rows
        ])
        assert page.multi_table.item(1, 3).text() == "Disabled account"
        page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}], True)
        page._bulk_account_ids = ["account-0", "account-1"]
        page._update_bulk_buttons()
        assert not page.start_selected_button.isEnabled()
        assert "enabled accounts only" in page.bulk_note.text()
        page._bulk_account_ids = [a["id"] for a in rows if a["enabled"]]
        page._update_bulk_buttons()
        assert page.start_selected_button.isEnabled()
    finally:
        _dispose(page, app)


def test_read_only_task_status_has_no_100_account_cutoff(app):
    class FakeReads:
        def tasks(self, account_id):
            return {"account_id": account_id, "engine_tasks": [], "requests": []}

    result = _run_batch(APIWorker(FakeReads(), "task_list_batch", task_payload={
        "account_ids": [a["id"] for a in accounts(125)]
    }))
    assert len(result) == 125
    assert all(row["requests"] == [] for row in result)



def test_bulk_launch_halts_if_successful_http_receipt_is_unconfirmed(app):
    class Backend:
        def __init__(self):
            self.started = []
        def task_preflight(self, account_id, task):
            return {"ready": True, "unresolved_request": False}
        def start_task(self, account_id, task, config, rid, *, confirmed):
            self.started.append(account_id)
            return {"account_id": account_id, "status": "unconfirmed"}

    backend = Backend()
    result = _run_batch(APIWorker(backend, "task_start_batch", task_payload={
        "account_ids": ["account-0", "account-1"], "task": "alertAttacks", "config": {}
    }))
    assert backend.started == ["account-0"]
    assert result["submitted"] == []
    assert result["halted"]["account_id"] == "account-0"
    assert result["halted"]["status"] == "unconfirmed"


def test_automation_approval_is_invalidated_by_parameter_and_scope_changes(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts(3))
        page.set_capabilities([{
            "name": "alertAttacks", "kind": "background_task",
            "config_fields": [{"name": "minutes", "type": "integer", "default": 20}],
        }], enabled=True)
        page.set_preflight({
            "account_id": "account-0", "task": "alertAttacks",
            "ready": True, "reason": "none",
        })
        page.confirm_box.setChecked(True)
        assert page._reviewed
        page._form_inputs["minutes"].setValue(21)
        assert not page._reviewed
        assert not page.confirm_box.isChecked()
        page.confirm_box.setChecked(True)
        page.select_account("account-2")
        assert not page._reviewed
        assert not page.start_button.isEnabled()
        page.set_preflight({
            "account_id": "account-2", "task": "alertAttacks",
            "ready": True, "reason": "none",
        })
        assert page.start_button.isEnabled()
        page.confirm_box.setChecked(True)
        page._pending_launch = True
        page._set_controls()
        assert not page.start_button.isEnabled()
        page.finish_launch()
        assert page.start_button.isEnabled()
        assert not page.confirm_box.isChecked()
    finally:
        _dispose(page, app)


def test_backend_declared_enum_uses_typed_fluent_picker_not_guesswork(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts(1))
        page.set_capabilities([{
            "name": "alertAttacks", "kind": "background_task",
            "config_fields": [{
                "name": "notification_mode", "type": "text", "required": True,
                "default": "telegram", "choices": ["telegram", "discord"],
            }],
        }], enabled=True)
        from qfluentwidgets import ComboBox
        widget = page._form_inputs["notification_mode"]
        assert isinstance(widget, ComboBox)
        assert widget.currentText() == "telegram"
        assert page._form_config() == {"notification_mode": "telegram"}
        widget.setCurrentIndex(1)
        assert page._form_config() == {"notification_mode": "discord"}
    finally:
        _dispose(page, app)


def test_activity_is_bounded_filtered_and_does_not_expose_unrecognized_messages(app):
    from daedalus.desktop.log_page import LogPage

    page = LogPage()
    try:
        page.add_event("INFO", "Connected to Daedalus API")
        assert "Connection established" in page.timeline.toPlainText()
        page.add_event("INFO", "token=private-secret account=private-name")
        assert "private-secret" not in page.timeline.toPlainText()
        page.add_event("WARNING", "Backend task_start request failed")
        assert "Action needs attention" in page.timeline.toPlainText()
        page.severity_combo.setCurrentIndex(1)
        assert "Connection established" in page.timeline.toPlainText()
        assert "Action needs attention" not in page.timeline.toPlainText()
        page.severity_combo.setCurrentIndex(2)
        assert "Action needs attention" in page.timeline.toPlainText()
        assert "Connection established" not in page.timeline.toPlainText()
    finally:
        _dispose(page, app)


def test_accounts_table_first_and_small_mac_layout(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window.resize(900, 650)
        assert window.minimumWidth() == 900
        assert window.minimumHeight() == 650
        # Ecobot-style table is the full-width primary workspace; no detail
        # panel is allowed to occupy half the account table.
        assert not hasattr(window.accounts_page, "master_detail")
        assert window.accounts_page.layout().indexOf(window.accounts_page.table) >= 0
        assert window.accounts_page.table.minimumHeight() >= 290
        assert window.accounts_page.advanced_recovery_panel.isHidden()
        window._show_accounts(accounts(5))
        assert window.accounts_page.table.rowCount() == 5
        assert len(window._task_views) == 1
        assert window._settings_shortcut.key().toString() == "Ctrl+,"
        assert window._refresh_shortcut.key().toString() == "Ctrl+R"
        assert window._search_shortcut.key().toString() == "Ctrl+F"
    finally:
        _dispose(window, app)


def test_single_automation_launch_does_not_allow_second_click_while_pending(app, monkeypatch):
    page = TasksPage()
    try:
        page.set_accounts(accounts(1))
        page.set_capabilities([{
            "name": "alertAttacks", "kind": "background_task",
            "config_fields": [{"name": "minutes", "type": "integer", "default": 20}],
        }], enabled=True)
        page.set_preflight({
            "account_id": "account-0", "task": "alertAttacks",
            "ready": True, "reason": "none",
        })
        emitted = []
        page.launch_requested.connect(lambda *args: emitted.append(args))
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        page.confirm_box.setChecked(True)
        page._start()
        page._start()
        assert len(emitted) == 1
        assert not page.start_button.isEnabled()
        page.finish_launch()
        assert page.start_button.isEnabled()
        assert not page.confirm_box.isChecked()
    finally:
        _dispose(page, app)


def test_old_preflight_reply_cannot_unlock_reselected_same_account_task(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window._show_accounts(accounts(2))
        window._show_capabilities({
            "operations": [{"name": "alertAttacks", "kind": "background_task"}],
            "structured_engine_dispatch": True,
        })
        view = window.tasks_page
        original_generation = view._selection_generation
        view.select_account("account-1")
        view.select_account("account-0")
        assert view._selection_generation > original_generation

        class PendingRead:
            def __init__(self):
                self.task_payload = {"task": "alertAttacks", "generation": original_generation}

        window._worker = PendingRead()
        window._on_completed("task_preflight", {
            "account_id": "account-0", "task": "alertAttacks",
            "ready": True, "reason": "none",
        })
        assert not view.start_button.isEnabled()
        assert view._prereq_ready is None
        window._worker = None
    finally:
        window._worker = None
        _dispose(window, app)


def test_catalog_is_embedded_and_routes_to_same_task_editor(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts(1))
        page.set_capabilities([
            {"name": "alertAttacks", "kind": "background_task"},
            {"name": "interactiveStatus", "kind": "interactive_menu"},
        ], enabled=True)
        page._open_catalog()
        assert page.stack.currentWidget() is page.catalog_panel
        assert page.catalog_panel.table.rowCount() == 2
        assert page.select_task("alertAttacks")
        assert page.stack.currentIndex() == 0
        assert page.selected_task_name() == "alertAttacks"
    finally:
        _dispose(page, app)


def test_activity_type_filter_is_not_a_fabricated_account_audit(app):
    from daedalus.desktop.log_page import LogPage

    page = LogPage()
    try:
        page.add_event("INFO", "Connected to Daedalus API")
        page.add_event("INFO", "Multi-account warehouse report updated")
        page.type_combo.setCurrentIndex(3)  # Warehouses
        assert "Combined warehouses refreshed" in page.timeline.toPlainText()
        assert "Connection established" not in page.timeline.toPlainText()
        assert "Combined warehouses refreshed" not in page.log_view.toPlainText()
    finally:
        _dispose(page, app)


def test_settings_reporting_scope_is_backend_local_and_read_only(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window._show_accounts(accounts(4))
        page = window.appearance_page
        assert "4 of 4" in page.report_scope_status.text()
        assert not page.report_all_button.isEnabled()
        assert page.report_choose_button.isEnabled()
        window.accounts_page.set_report_exclusions({"account-1", "account-3"})
        assert window.warehouses_page._included_ids == ["account-0", "account-2"]
        assert "2 of 4" in page.report_scope_status.text()
        page.report_all_button.click()
        assert window.accounts_page.report_exclusions() == set()
        assert window.warehouses_page._included_ids == [
            "account-0", "account-1", "account-2", "account-3"
        ]
        assert not page.report_all_button.isEnabled()
    finally:
        _dispose(window, app)


def test_automation_discovery_cards_are_selection_only(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts(2))
        page.set_capabilities([
            {"name": "tavernManager", "kind": "background_task"},
            {"name": "alertAttacks", "kind": "background_task"},
            {"name": "browserOnly", "kind": "interactive_menu"},
        ], enabled=True)
        launched = []
        page.launch_requested.connect(lambda *args: launched.append(args))
        page.batch_launch_requested.connect(lambda *args: launched.append(args))
        assert page.discovery_layout.count() == 2
        page.search_input.setText("tavern")
        assert page.discovery_layout.count() == 1
        page._select_discovered_task("tavernManager")
        assert page.selected_task_name() == "tavernManager"
        assert launched == []
        assert not page.start_button.isEnabled()
        page.reset_backend_context()
        assert page.selected_account_id() is None
        assert page.selected_task_name() is None
        assert not page.confirm_box.isChecked()
        assert not page.start_button.isEnabled()
    finally:
        _dispose(page, app)


def test_history_and_running_hide_technical_ids_but_preserve_managed_action(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = TasksPage()
    try:
        page.set_accounts(accounts(1))
        page.set_capabilities([
            {"name": "alertAttacks", "kind": "background_task"}
        ], enabled=True)
        page.set_tasks({
            "engine_tasks": [{
                "task": "alertAttacks", "status": "running",
                "task_id": "task-allowed", "pid": 8421,
            }],
            "requests": [{
                "task": "alertAttacks", "status": "unconfirmed",
                "request_id": "request-allowed",
            }],
        })
        assert "8421" not in page.task_table.item(0, 2).text()
        assert "task-allowed" not in page.task_table.item(0, 3).text()
        assert "request-allowed" not in page.request_table.item(0, 0).text()
        page.task_table.setCurrentCell(0, 0)
        page.request_table.setCurrentCell(0, 0)
        stopped, reconciled = [], []
        page.stop_requested.connect(lambda *args: stopped.append(args))
        page.reconcile_requested.connect(lambda *args: reconciled.append(args))
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
        page._stop()
        page._reconcile()
        assert stopped == [("account-0", "task-allowed")]
        assert reconciled == [("account-0", "request-allowed")]
    finally:
        _dispose(page, app)


def test_connection_progress_and_errors_never_echo_backend_secrets(app):
    from daedalus.desktop.pages import ConnectionPage

    page = ConnectionPage()
    try:
        page.token_input.setText("super-private-token")
        page.set_connecting(True)
        assert not page.connect_button.isEnabled()
        assert "Checking secure connection" in page.status_label.text()
        page.set_connection_error(
            "unauthorized super-private-token in HTTP response"
        )
        assert "super-private-token" not in page.status_label.text()
        assert "Access denied" in page.status_label.text()
        page.set_connecting(False)
        assert page.connect_button.isEnabled()
        page.set_connection_error("certificate verify failed")
        assert "Certificate not trusted" in page.status_label.text()
    finally:
        _dispose(page, app)


def test_automation_uses_player_names_across_account_scopes(app):
    from daedalus.account_display import account_player_name, account_player_names

    rows = [
        {"id": "one", "label": "Imported IkaBot identity 01", "player": "Monjo",
         "world": "s58-ru", "enabled": True, "email": "example@example.org"},
        {"id": "two", "label": "Imported IkaBot identity 02", "player": "Ais",
         "world": "s58-ru", "enabled": True},
    ]
    assert account_player_names(rows) == {"one": "Monjo", "two": "Ais"}
    assert account_player_name({"id": "unknown", "player": "Imported IkaBot identity 03",
                                "label": "Imported IkaBot identity 03"}) == "unknown"
    duplicates = account_player_names(rows + [dict(rows[0], id="three")])
    assert duplicates["one"] != duplicates["three"]
    assert duplicates["one"].startswith("Monjo")
    page = TasksPage()
    try:
        page.set_accounts(rows)
        page.select_account("two")
        for combo in (page.account_combo, page.running_account_combo, page.history_account_combo):
            assert combo.currentText() == "Ais"
        page.set_accounts(list(reversed(rows)))
        assert page.selected_account_id() == "two"
        assert page.account_combo.currentText() == "Ais"
        page.set_batch_status([{"account_id": row["id"], "engine_tasks": [], "requests": []}
                               for row in rows])
        assert page.multi_table.item(0, 0).text() == "Monjo"
        assert page.multi_table.item(1, 0).text() == "Ais"
    finally:
        _dispose(page, app)


def test_city_bound_bulk_plan_cannot_be_reused_for_other_accounts(app):
    page = TasksPage()
    try:
        page.set_accounts(accounts(3))
        page.set_capabilities([{"name": "sendResources", "kind": "background_task",
                                "config_fields": []}], enabled=True)
        page._bulk_account_ids = ["account-0", "account-1"]
        page._update_bulk_buttons()
        assert not page.start_selected_button.isEnabled()
    finally:
        page.deleteLater()
