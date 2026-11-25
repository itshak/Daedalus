"""Native Qt task control smoke tests; all backend calls are mocked/offline."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from daedalus.desktop.task_page import TasksPage


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def page(app):
    widget = TasksPage()
    widget.set_accounts([
        {"id": "alpha", "label": "Primary", "world": "s301-en",
         "player": "ExamplePlayer", "enabled": True},
        {"id": "disabled", "label": "Disabled", "world": "s302-en",
         "player": "ExampleTwo", "enabled": False},
    ])
    widget.set_capabilities([
        {"name": "alertAttacks", "kind": "background_task"},
        {"name": "constructionList", "kind": "background_task"},
        {"name": "getStatus", "kind": "interactive_menu"},
    ], enabled=False)
    yield widget
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def test_disabled_backend_cannot_launch_any_game_task(page):
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    assert not page.start_button.isEnabled()
    assert not page.stop_button.isEnabled()
    assert page.selected_account_id() == "alpha"
    assert "disabled" not in page._account_ids
    assert "getStatus" not in page._task_names
    page._start()
    assert emitted == []


def test_enabled_task_explicit_confirmation_and_uuid(page, monkeypatch):
    page.set_capabilities([
        {"name": "alertAttacks", "kind": "background_task", "config_fields": [
            {"name": "minutes", "type": "integer", "default": 20, "required": False},
        ]},
    ], enabled=True)
    assert not page.start_button.isEnabled()
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks", "ready": True, "reason": "none"})
    assert page.start_button.isEnabled()
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    answers = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: (answers.append(True) or QMessageBox.Yes))
    assert not hasattr(page, "config_editor")
    page.confirm_box.setChecked(True)
    page._start()
    assert answers == [True]
    assert len(emitted) == 1
    account_id, task, config, rid = emitted[0]
    assert account_id == "alpha"
    assert task == "alertAttacks"
    assert config == {"minutes": 20}
    assert uuid.UUID(rid).version == 4
    assert page.confirm_box.isChecked() is False


def test_no_raw_configuration_entry_points(page):
    for name in ("config_editor", "advanced_toggle", "import_config_button",
                 "build_json_button", "_toggle_advanced", "_import_advanced_config"):
        assert not hasattr(page, name)


def test_task_listing_stop_only_selected_managed_id(page, monkeypatch):
    page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}], enabled=True)
    page.set_tasks({
        "engine_tasks": [{"task": "alertAttacks", "status": "running",
                         "pid": 4242, "task_id": "f" * 24}],
        "requests": [{"request_id": str(uuid.uuid4()), "task": "alertAttacks",
                      "status": "started", "task_id": "f" * 24}],
    })
    assert page.task_table.rowCount() == 1
    assert page.request_table.rowCount() == 1
    page.task_table.setCurrentCell(0, 0)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    emitted = []
    page.stop_requested.connect(lambda *args: emitted.append(args))
    page._stop()
    assert emitted == [("alpha", "f" * 24)]


def test_uncertain_task_request_needs_manual_review(page, monkeypatch):
    page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}], enabled=True)
    rid = str(uuid.uuid4())
    page.set_tasks({
        "engine_tasks": [],
        "requests": [{"request_id": rid, "task": "alertAttacks",
                      "status": "unconfirmed", "task_id": None}],
    })
    page.request_table.setCurrentCell(0, 0)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    emitted = []
    page.reconcile_requested.connect(lambda *args: emitted.append(args))
    page._reconcile()
    assert emitted == [("alpha", rid)]


def test_parameter_form_builds_internal_payload_and_requires_explicit_review(page, monkeypatch):
    from daedalus.engine_registry import inspect_engine

    record = next(cap for cap in inspect_engine() if cap.name == "alertAttacks")
    page.set_capabilities([record.to_dict()], enabled=True)
    assert "minutes" in page._form_inputs
    widget = page._form_inputs["minutes"]
    assert widget.value() == 20
    assert widget.minimum() == 3

    emitted = []
    warnings = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)

    widget.setValue(42)
    assert page._form_dirty is True
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks", "ready": True, "reason": "none"})
    page.confirm_box.setChecked(True)
    page._start()
    assert warnings == []
    assert emitted[0][2] == {"minutes": 42}
    assert not hasattr(page, "config_editor")


def test_required_and_boolean_fields_are_typed_and_validated(page):
    from daedalus.engine_registry import inspect_engine

    record = next(cap for cap in inspect_engine() if cap.name == "alertLowWine")
    page.set_capabilities([record.to_dict()], enabled=True)
    with pytest.raises(ValueError):
        page._form_config()
    page._form_inputs["hours"].setValue(4)
    page._form_inputs["auto_transfer"].setChecked(True)
    page._form_inputs["transfer_amount"].setValue(1500)
    assert page._form_config() == {
        "hours": 4, "auto_transfer": True, "transfer_amount": 1500,
    }
    page._form_inputs["hours"].setValue(0)
    with pytest.raises(ValueError):
        page._form_config()


def test_switching_tasks_clears_previous_task_configuration_and_confirmation(page):
    from daedalus.engine_registry import inspect_engine

    operations = [
        cap.to_dict() for cap in inspect_engine()
        if cap.name in {"alertAttacks", "alertLowWine"}
    ]
    page.set_capabilities(operations, enabled=True)
    page._form_inputs["minutes"].setValue(15)
    assert page._form_config() == {"minutes": 15}
    page.confirm_box.setChecked(True)
    page.task_combo.setCurrentIndex(1)
    assert "minutes" not in page._form_inputs
    assert not page.confirm_box.isChecked()
    assert "hours" in page._form_inputs


def test_alert_requires_verified_prerequisites_before_gui_dispatch(page, monkeypatch):
    page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}], enabled=True)
    assert page.selected_task_name() == "alertAttacks"
    assert not page.start_button.isEnabled()
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks",
                        "ready": False, "reason": "notifications_required"})
    assert not page.start_button.isEnabled()
    assert "Telegram or Discord" in page.prerequisite_label.text()
    page.set_preflight({"account_id": "another", "task": "alertAttacks",
                        "ready": True, "reason": "none"})
    assert not page.start_button.isEnabled()  # another account cannot unlock it
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks",
                        "ready": True, "reason": "none"})
    assert page.start_button.isEnabled()
    page.set_tasks({"engine_tasks": [], "requests": [
        {"request_id": str(uuid.uuid4()), "task": "alertAttacks", "status": "unconfirmed"},
    ]})
    assert not page.start_button.isEnabled()
    assert "reconcile" in page.prerequisite_label.text()


def test_category_filter_and_friendly_labels_preserve_engine_identifiers(page):
    records = [{"name": t, "kind": "background_task"} for t in
               ("alertAttacks", "constructionList", "sellResources")]
    page.set_capabilities(records, enabled=True)
    assert page.task_combo.count() == 3
    assert "Attack alerts" in [page.task_combo.itemText(i)
                                for i in range(page.task_combo.count())]
    page.category_combo.setCurrentIndex(1)
    assert page._task_names == ["alertAttacks"]
    page.category_combo.setCurrentIndex(0)
    page.search_input.setText("sell")
    assert page._task_names == ["sellResources"]
    assert page.select_task("constructionList")
    assert page.selected_task_name() == "constructionList"
    assert page.category_combo.currentIndex() == 0
    assert page.search_input.text() == ""


def test_construction_city_picker_uses_only_account_bound_real_cities(page):
    requested = []
    page.cities_requested.connect(requested.append)
    page.set_capabilities([{
        "name": "constructionList",
        "kind": "background_task",
        "config_fields": [
            {"name": "city_id", "type": "json", "required": True},
            {"name": "city_name", "type": "json", "required": True},
        ],
    }], enabled=True)
    assert requested == ["alpha"]
    assert page.group_tabs is not None
    assert not page.start_selected_button.isEnabled()  # City-specific plan cannot be broadcast.
    picker = page._form_inputs["city_id"]
    assert picker.count() == 1
    with pytest.raises(ValueError, match="Select a city"):
        page._form_config()

    # A different account cannot contaminate this draft's choices.
    page.set_cities("disabled", [{"id": 77, "name": "Other account"}])
    assert picker.count() == 1
    page.set_cities("alpha", [
        {"id": 101, "name": "Olympia", "coords": "50:48"},
        {"id": 102, "name": "Sparta", "coords": "50:49"},
    ])
    assert picker.count() == 3
    assert "Olympia" in picker.itemText(1)
    with pytest.raises(ValueError, match="Select a city"):
        page._form_config()  # No automatic first-city selection.
    picker.setCurrentIndex(2)
    assert page._form_config() == {"city_id": 102, "city_name": "Sparta"}

    # Changing the account data revokes the selection and invalidates consent.
    page.confirm_box.setChecked(True)
    page.set_cities_unavailable("alpha")
    assert not page.confirm_box.isChecked()
    with pytest.raises(ValueError, match="Select a city"):
        page._form_config()


def test_category_pivot_mirrors_existing_canonical_task_filter(page):
    records = [{"name": t, "kind": "background_task"} for t in
               ("alertAttacks", "constructionList", "sellResources")]
    page.set_capabilities(records, enabled=True)
    page.category_combo.setCurrentIndex(3)
    assert page._task_names == ["constructionList"]
    assert page.category_combo.currentIndex() == 3
    assert page.group_tabs.isEnabled()


def test_construction_table_renders_real_building_levels_and_draft_target(page):
    requests = []
    page.buildings_requested.connect(lambda account_id, city_id: requests.append((account_id, city_id)))
    page.set_capabilities([{
        "name": "constructionList", "kind": "background_task",
        "config_fields": [
            {"name": "city_id", "type": "json", "required": True},
            {"name": "city_name", "type": "json", "required": True},
            {"name": "buildings", "type": "json", "required": True},
            {"name": "shipments", "type": "json", "required": True},
            {"name": "expand_overall", "type": "json", "required": True},
            {"name": "wait_resources", "type": "json", "required": True},
            {"name": "construction_queue", "type": "json", "required": True},
            {"name": "total_time", "type": "json", "required": True},
        ],
    }], enabled=True)
    page.set_cities("alpha", [{"id": 101, "name": "Olympia"}])
    page._form_inputs["city_id"].setCurrentIndex(1)
    assert requests == [("alpha", 101)]
    page.set_buildings("disabled", 101, [])
    assert page.building_table.rowCount() == 0
    page.set_buildings("alpha", 102, [])
    assert page.building_table.rowCount() == 0
    page.set_buildings("alpha", 101, [
        {"position": 2, "level": 10, "name": "Town Hall", "building": "townHall",
         "busy": False, "can_upgrade": True},
        {"position": 4, "level": 5, "name": "Academy", "building": "academy",
         "busy": True, "can_upgrade": False},
    ])
    assert page.building_table.rowCount() == 2
    assert page.building_table.item(0, 1).text() == "Town Hall"
    assert page.building_table.item(0, 3).text() == "10"
    target = page.building_table.cellWidget(0, 4)
    assert target.value() == 10
    assert target.isEnabled()
    target.setValue(12)
    assert page.building_table.cellWidget(1, 4).isEnabled() is False
    assert "actual IkaBot planner" in page.building_note.text()
    page.set_preflight({"account_id": "alpha", "task": "constructionList",
                        "ready": True, "reason": "none", "unresolved_request": False})
    # Rendering a read-only inventory is not permission to start an unprepared task.
    assert page.start_button.isEnabled() is False
    page._form_inputs["city_id"].setCurrentIndex(0)
    assert page.building_table.rowCount() == 0


def test_construction_has_no_raw_plan_override(page):
    page.set_capabilities([{
        "name": "constructionList", "kind": "background_task",
        "config_fields": [
            {"name": key, "type": "json", "required": True}
            for key in ("city_id", "city_name", "buildings", "shipments",
                        "expand_overall", "wait_resources", "construction_queue", "total_time")
        ],
    }], enabled=True)
    assert set(page._form_inputs) == {"city_id"}
    assert not hasattr(page, "config_editor")
    assert not page.start_button.isEnabled()


def test_distribution_uses_verified_resource_policy_and_actual_city_multiselect(page):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    requested = []
    page.cities_requested.connect(requested.append)
    page.set_capabilities([{
        "name": "distributeResources", "kind": "background_task",
        "config_fields": [
            {"name": "resource", "type": "json", "required": True},
            {"name": "mode", "type": "text", "default": "even", "required": False},
            {"name": "cities_ids", "type": "json", "required": False},
            {"name": "useFreighters", "type": "boolean", "required": False},
        ],
    }], enabled=True)
    assert requested == ["alpha"]
    cities = page._form_inputs["cities_ids"]
    assert isinstance(cities, QListWidget)
    assert cities.count() == 0
    page.set_cities("alpha", [
        {"id": 11, "name": "Athens", "coords": "1:2"},
        {"id": 12, "name": "Olympia", "coords": "1:3"},
        {"id": 13, "name": "Sparta", "coords": "1:4"},
    ])
    assert cities.count() == 3
    assert "Athens" in cities.item(0).text()
    resource = page._form_inputs["resource"]
    values = [resource.itemText(i) for i in range(resource.count())]
    assert values == ["wood", "wine", "marble", "crystal", "sulfur"]
    # Required resource is deliberately not assumed: user must choose one.
    with pytest.raises(ValueError, match="Choose an option for resource"):
        page._form_config()
    resource.setCurrentIndex(0)
    assert page._form_config()["resource"] == "wood"
    assert "cities_ids" not in page._form_config()  # all cities through upstream default

    cities.item(0).setCheckState(Qt.Checked)
    with pytest.raises(ValueError, match="at least two"):
        page._form_config()
    cities.item(1).setCheckState(Qt.Checked)
    assert page._form_config()["cities_ids"] == ["11", "12"]
    page._form_inputs["mode"].setCurrentIndex(1)
    with pytest.raises(ValueError, match="Every city produces wood"):
        page._form_config()
    resource.setCurrentIndex(1)
    assert page._form_config()["resource"] == "wine"

    # A refreshed authenticated city set invalidates the previous chosen IDs.
    page.set_cities_unavailable("alpha")
    assert cities.count() == 0
    assert "cities_ids" not in page._form_config()


def test_tavern_cities_are_native_and_never_fabricated(page):
    from PySide6.QtCore import Qt

    from daedalus.desktop.native_controls import TavernCitiesEditor

    page.set_capabilities([{
        "name": "tavernManager", "kind": "background_task",
        "config_fields": [
            {"name": "run_hours", "type": "json", "required": True},
            {"name": "cities_ids", "type": "json", "required": False},
        ],
    }], enabled=True)
    editor = page._form_inputs["cities_ids"]
    assert isinstance(editor, TavernCitiesEditor)
    # A list of city names is not sufficient: real tavern state must come
    # from the selected account before the UI can prepare an executable plan.
    page.set_cities("alpha", [{"id": 30, "name": "Ephesus"}])
    with pytest.raises(ValueError, match="Load real tavern"):
        page._form_config()
    page.set_taverns({
        "account_id": "other", "taverns": [],
    })
    with pytest.raises(ValueError, match="Load real tavern"):
        page._form_config()
    page.set_taverns({
        "account_id": "alpha",
        "taverns": [{
            "city_id": 30, "city_name": "Ephesus",
            "wine": 4000, "wine_per_hour": 25, "has_tavern": True,
            "serving_level": 3, "population": 150, "capacity": 300,
            "satisfaction": 50,
        }],
    })
    assert editor.table.rowCount() == 1
    editor.interval.setValue(1)
    assert page._form_config() == {
        "cities_ids": None, "run_hours": 1, "notification_mode": 2,
    }
    editor.all_cities.setChecked(False)
    with pytest.raises(ValueError, match="Choose at least one city"):
        page._form_config()
    editor.table.item(0, 0).setCheckState(Qt.Checked)
    assert page._form_config()["cities_ids"] == ["30"]


def test_construction_cannot_start_without_verified_preview(page):
    page.set_capabilities([{
        "name": "constructionList", "kind": "background_task",
        "config_fields": [
            {"name": key, "type": "json", "required": True}
            for key in ("city_id", "city_name", "buildings", "shipments", "expand_overall",
                        "wait_resources", "construction_queue", "total_time")
        ],
    }], enabled=True)
    page.set_cities("alpha", [{"id": 101, "name": "Olympia"}])
    page._form_inputs["city_id"].setCurrentIndex(1)
    page.set_preflight({"account_id": "alpha", "task": "constructionList",
                        "ready": True, "reason": "none"})
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    page.confirm_box.setChecked(True)
    assert not page.start_button.isEnabled()
    page._start()
    assert not emitted


def test_daily_rewards_use_three_actual_city_pickers_and_native_favour_options(page):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    requested = []
    page.cities_requested.connect(requested.append)
    page.set_capabilities([{
        "name": "loginDaily", "kind": "background_task",
        "config_fields": [
            {"name": "wine_city", "type": "json", "required": True},
            {"name": "wood_city", "type": "json", "required": False},
            {"name": "luxury_city", "type": "json", "required": False},
            {"name": "favour_tasks", "type": "json", "required": False},
            {"name": "collect_ambrosia", "type": "boolean", "required": False},
        ],
    }], enabled=True)
    assert requested == ["alpha"]
    with pytest.raises(ValueError, match="Select an actual city for wine_city"):
        page._form_config()
    page.set_cities("alpha", [
        {"id": 101, "name": "Olympia", "coords": "15:20"},
        {"id": 102, "name": "Sparta", "coords": "15:22"},
    ])
    wine = page._form_inputs["wine_city"]
    wood = page._form_inputs["wood_city"]
    luxury = page._form_inputs["luxury_city"]
    assert wine.count() == 3
    assert wood.itemText(0) == "Skip optional reward"
    assert luxury.itemText(0) == "Skip optional reward"
    wine.setCurrentIndex(1)
    assert page._form_config()["wine_city"] == 101
    assert "wood_city" not in page._form_config()
    wood.setCurrentIndex(2)
    assert page._form_config()["wood_city"] == 102
    options = page._form_inputs["favour_tasks"]
    assert isinstance(options, QListWidget)
    assert [options.item(i).text() for i in range(options.count())] == [
        "resource", "look", "online", "complete"
    ]
    options.item(0).setCheckState(Qt.Checked)
    options.item(3).setCheckState(Qt.Checked)
    assert page._form_config()["favour_tasks"] == ["resource", "complete"]
    # No city data available after session revocation: old IDs must not persist.
    page.set_cities_unavailable("alpha")
    assert wine.currentIndex() == 0
    assert wood.currentIndex() == 0
    with pytest.raises(ValueError, match="Select an actual city"):
        page._form_config()
    assert options.item(0).checkState() == Qt.Checked


def test_construction_preview_launch_requires_fresh_verified_queue(page, monkeypatch):
    from PySide6.QtCore import Qt

    fields = [{"name": name, "type": "json", "required": True}
              for name in ("city_id", "city_name", "buildings", "shipments",
                           "expand_overall", "wait_resources", "construction_queue",
                           "total_time")]
    page.set_capabilities([{
        "name": "constructionList", "kind": "background_task",
        "config_fields": fields,
    }], enabled=True)
    page.set_cities("alpha", [{"id": 101, "name": "Olympia"}])
    page._form_inputs["city_id"].setCurrentIndex(1)
    page.set_buildings("alpha", 101, [{
        "position": 2, "level": 10, "name": "Town Hall", "building": "townHall",
        "busy": False, "can_upgrade": True,
    }])
    page.set_preflight({
        "account_id": "alpha", "task": "constructionList",
        "ready": True, "reason": "none", "unresolved_request": False,
    })
    button = page.construction_preview_button
    assert button.isEnabled()
    assert not page.start_button.isEnabled()
    target = page.building_table.cellWidget(0, 4)
    target.setValue(11)
    choice = page.building_table.item(0, 0)
    choice.setCheckState(Qt.Checked)
    requests = []
    page.construction_preview_requested.connect(
        lambda aid, city, upgrades: requests.append((aid, city, upgrades))
    )
    page._request_construction_preview()
    assert requests == [("alpha", 101, [{"position": 2, "target_level": 11}])]
    assert not page.start_button.isEnabled()
    config = {
        "city_id": 101, "city_name": "Olympia", "buildings": [{
            "position": 2, "level": 10, "name": "Town Hall",
            "building": "townHall", "upgradeTo": 11, "isBusy": False,
            "constructionTime": 90, "constructionTimes": [90],
        }],
        "shipments": [], "expand_overall": True, "wait_resources": False,
        "construction_queue": [90], "total_time": 90,
    }
    page.set_construction_preview({
        "account_id": "disabled", "city_id": 101, "ready": True,
        "config": config, "costs": [400, 0, 0, 0, 0],
        "missing": [0] * 5, "estimated_seconds": 90,
    })
    assert not page.start_button.isEnabled()
    page.set_construction_preview({
        "account_id": "alpha", "city_id": 101, "ready": True,
        "config": config, "costs": [400, 0, 0, 0, 0],
        "missing": [0] * 5, "estimated_seconds": 90,
    })
    assert page.start_button.isEnabled()
    assert "Actual IkaBot costs" in page.building_note.text()
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    page.confirm_box.setChecked(True)
    page._start()
    assert len(emitted) == 1
    assert emitted[0][0:3] == ("alpha", "constructionList", config)


def test_editing_construction_queue_after_preview_revokes_approval(page):
    from PySide6.QtCore import Qt

    page.set_capabilities([{
        "name": "constructionList", "kind": "background_task",
        "config_fields": [
            {"name": key, "type": "json", "required": True}
            for key in ("city_id", "city_name", "buildings", "shipments",
                        "expand_overall", "wait_resources", "construction_queue",
                        "total_time")
        ],
    }], enabled=True)
    page.set_cities("alpha", [{"id": 101, "name": "Olympia"}])
    page._form_inputs["city_id"].setCurrentIndex(1)
    page.set_buildings("alpha", 101, [{
        "position": 2, "level": 10, "name": "Town Hall", "building": "townHall",
        "busy": False, "can_upgrade": True,
    }])
    target = page.building_table.cellWidget(0, 4)
    target.setValue(11)
    page.building_table.item(0, 0).setCheckState(Qt.Checked)
    page._request_construction_preview()
    page.set_construction_preview({
        "account_id": "alpha", "city_id": 101, "ready": False,
        "config": {"city_id": 101}, "costs": [400, 0, 0, 0, 0],
        "missing": [300, 0, 0, 0, 0], "estimated_seconds": 90,
    })
    assert page._construction_prepared is None
    assert "Missing: Wood" in page.building_note.text()
    page._request_construction_preview()
    page.set_construction_preview({
        "account_id": "alpha", "city_id": 101, "ready": True,
        "config": {"city_id": 101}, "costs": [400, 0, 0, 0, 0],
        "missing": [0] * 5, "estimated_seconds": 90,
    })
    assert page._construction_preview_ready
    target.setValue(12)
    assert not page._construction_preview_ready
    assert page._construction_prepared is None
    assert page._pending_preview_key is None
    page.set_cities_unavailable("alpha")
    assert not page._construction_preview_ready
    assert page.building_table.rowCount() == 0


def test_unknown_compound_engine_fields_do_not_create_raw_json_form_wall(page):
    """Unreviewed complex configs must not impersonate a native game plan."""
    page.set_capabilities([{
        "name": "attackBarbarians", "kind": "background_task",
        "config_fields": [
            {"name": "island", "type": "json", "required": True},
            {"name": "city", "type": "json", "required": True},
            {"name": "plan", "type": "json", "required": True},
            {"name": "ship_capacity", "type": "json", "required": True},
        ],
    }], enabled=True)
    assert not page._form_inputs
    assert page.expert_note.isVisible() is False or not page.expert_note.isHidden()
    page.set_preflight({
        "account_id": "alpha", "task": "attackBarbarians",
        "ready": True, "reason": "none", "unresolved_request": False,
    })
    assert not page.start_button.isEnabled()
    with pytest.raises(ValueError, match="dedicated native editor"):
        page._form_config()
    assert not page.start_selected_button.isEnabled()
    assert not hasattr(page, "advanced_toggle")


def test_donate_once_requires_scoped_preview(page, monkeypatch):
    from daedalus.engine_registry import inspect_engine

    capability = next(c for c in inspect_engine() if c.name == "donate")
    page.set_capabilities([capability.to_dict()], enabled=True)
    page.set_cities("alpha", [{"id": 1, "name": "Town"}])
    page.set_preflight({"account_id": "alpha", "task": "donate", "ready": True,
                        "reason": "none"})
    page._form_inputs["city_id"].setCurrentIndex(1)
    page._form_inputs["project"].setCurrentIndex(0)
    page._form_inputs["amount"].setValue(100)
    assert not page.start_button.isEnabled()
    calls = []
    page.donation_preview_requested.connect(lambda *args: calls.append(args))
    page._request_native_preview()
    assert calls[0][:2] == ("alpha", {"city_id": 1, "project": "resource", "amount": 100})
    nonce = calls[0][2]
    result = {"account_id": "alpha", "city_id": 1, "project": "resource",
              "city_name": "Town", "project_name": "Forest", "amount": 100,
              "stock": 1000, "remaining": 400, "level": 2, "ready": True,
              "preview_id": "a" * 43, "expires_in": 120}
    page.set_donation_preview(result, "wrong")
    assert not page.start_button.isEnabled()
    page.set_donation_preview(result, nonce)
    assert page.start_button.isEnabled()
    page.confirm_box.setChecked(True)
    page._form_inputs["amount"].setValue(101)
    assert not page.start_button.isEnabled()
    assert not page.confirm_box.isChecked()
    page._request_native_preview()
    page.set_donation_preview({**result, "amount": 101}, calls[-1][2])
    launched = []
    page.launch_requested.connect(lambda *args: launched.append(args))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    page.confirm_box.setChecked(True)
    page._start()
    assert launched[0][:3] == ("alpha", "donate", {"preview_id": "a" * 43})


@pytest.mark.parametrize("task", ["modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers"])
def test_worker_editor_requires_scope_bound_preview(page, monkeypatch, task):
    from daedalus.engine_registry import inspect_engine

    capability = next(c for c in inspect_engine() if c.name == task)
    page.set_capabilities([capability.to_dict()], enabled=True)
    page.set_cities("alpha", [{"id": 1, "name": "Town"}])
    page.set_preflight({"account_id": "alpha", "task": task, "ready": True,
                        "reason": "none"})
    page._form_inputs["city_id"].setCurrentIndex(1)
    page._form_inputs["percentage"].setValue(50)
    if task == "modifyProduction":
        page._form_inputs["project"].setCurrentIndex(0)
        page._form_inputs["overcharge"].setChecked(False)
    assert not page.start_button.isEnabled()
    calls = []
    page.worker_preview_requested.connect(lambda *args: calls.append(args))
    page._request_native_preview()
    account, name, draft, nonce = calls[0]
    assert account == "alpha" and name == task
    assert draft["percentage"] == 50 and draft["city_id"] == 1
    result = {"account_id": "alpha", "task": task, **draft, "city_name": "Town",
              "current": 25, "maximum": 100, "extra": 0, "target": 50, "ready": True,
              "preview_id": "a" * 43, "expires_in": 120}
    page.set_worker_preview(result, "wrong")
    assert not page.start_button.isEnabled()
    page.set_worker_preview(result, nonce)
    assert page.start_button.isEnabled()
    page.confirm_box.setChecked(True)
    page._form_inputs["percentage"].setValue(51)
    assert not page.start_button.isEnabled()
    assert not page.confirm_box.isChecked()
    page._request_native_preview()
    page.set_worker_preview({**result, "percentage": 51, "target": 51}, calls[-1][3])
    launched = []
    page.launch_requested.connect(lambda *args: launched.append(args))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)
    page.confirm_box.setChecked(True)
    page._start()
    assert launched[0][:3] == ("alpha", task, {"preview_id": "a" * 43})
