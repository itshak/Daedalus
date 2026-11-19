"""Native Qt task control smoke tests; all backend calls are mocked/offline."""

from __future__ import annotations

import json
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
    assert not page.config_editor.isVisible()
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


def test_bad_json_does_not_emit_task_start(page, monkeypatch):
    page.set_capabilities([{"name": "alertAttacks", "kind": "background_task"}], enabled=True)
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks", "ready": True, "reason": "none"})
    page._toggle_advanced()
    page.confirm_box.setChecked(True)
    page.config_editor.setPlainText("{not valid")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    page._start()
    assert warnings == [True]
    assert emitted == []


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


def test_parameter_form_generates_json_but_requires_explicit_review(page, monkeypatch):
    from daedalus.engine_registry import inspect_engine

    record = next(cap for cap in inspect_engine() if cap.name == "alertAttacks")
    page.set_capabilities([record.to_dict()], enabled=True)
    assert "minutes" in page._form_inputs
    assert page.build_json_button.isEnabled()
    widget = page._form_inputs["minutes"]
    assert widget.value() == 20
    assert widget.minimum() == 3
    assert page.config_editor.isHidden()

    emitted = []
    warnings = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)

    widget.setValue(42)
    assert page._form_dirty is True
    assert not page._advanced_visible
    page.set_preflight({"account_id": "alpha", "task": "alertAttacks", "ready": True, "reason": "none"})
    page.confirm_box.setChecked(True)
    page._start()
    assert warnings == []
    assert emitted[0][2] == {"minutes": 42}
    assert page.config_editor.isHidden()  # no manual JSON editing needed

    page._toggle_advanced()
    assert page._advanced_visible
    assert json.loads(page.config_editor.toPlainText()) == {"minutes": 42}


def test_json_required_and_boolean_fields_are_typed_and_validated(page, monkeypatch):
    from daedalus.engine_registry import inspect_engine

    record = next(cap for cap in inspect_engine() if cap.name == "alertLowWine")
    page.set_capabilities([record.to_dict()], enabled=True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    page._build_config_from_form()
    assert warnings
    assert page.config_editor.toPlainText() == "{}"
    # Upstream documents hours as an integer; the redesigned GUI uses a
    # native Fluent SpinBox with a mandatory empty sentinel, not free-form JSON.
    page._form_inputs["hours"].setValue(4)
    page._form_inputs["auto_transfer"].setChecked(True)
    page._form_inputs["transfer_amount"].setValue(1500)
    page._build_config_from_form()
    assert json.loads(page.config_editor.toPlainText()) == {
        "hours": 4, "auto_transfer": True, "transfer_amount": 1500,
    }

    previous_warnings = len(warnings)
    page._form_inputs["hours"].setValue(0)  # missing-value sentinel
    page._build_config_from_form()
    assert len(warnings) > previous_warnings
    assert '"hours": 4' in page.config_editor.toPlainText()


def test_switching_tasks_clears_previous_task_configuration_and_confirmation(page):
    from daedalus.engine_registry import inspect_engine

    operations = [
        cap.to_dict() for cap in inspect_engine()
        if cap.name in {"alertAttacks", "alertLowWine"}
    ]
    page.set_capabilities(operations, enabled=True)
    page._form_inputs["minutes"].setValue(15)
    page._build_config_from_form()
    page.confirm_box.setChecked(True)
    page.task_combo.setCurrentIndex(1)
    assert page.config_editor.toPlainText() == "{}"
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
    assert page.group_tabs.currentItem().routeKey() == "group-3" if hasattr(
        page.group_tabs.currentItem(), "routeKey"
    ) else page.category_combo.currentIndex() == 3
