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
        {"name": "alertAttacks", "kind": "background_task"},
    ], enabled=True)
    assert page.start_button.isEnabled()
    emitted = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    answers = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: (answers.append(True) or QMessageBox.Yes))
    page.config_editor.setPlainText('{"minutes": 20}')
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
    assert widget.placeholderText() == "Default: 20"

    emitted = []
    warnings = []
    page.launch_requested.connect(lambda *args: emitted.append(args))
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.Yes)

    widget.setText("42")
    assert page._form_dirty is True
    page.confirm_box.setChecked(True)
    page._start()
    assert emitted == [] and warnings

    page._build_config_from_form()
    assert json.loads(page.config_editor.toPlainText()) == {"minutes": 42}
    assert page._form_dirty is False
    page.confirm_box.setChecked(True)
    page._start()
    assert emitted[0][2] == {"minutes": 42}


def test_json_required_and_boolean_fields_are_typed_and_validated(page, monkeypatch):
    from daedalus.engine_registry import inspect_engine

    record = next(cap for cap in inspect_engine() if cap.name == "alertLowWine")
    page.set_capabilities([record.to_dict()], enabled=True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    page._build_config_from_form()
    assert warnings
    assert page.config_editor.toPlainText() == "{}"
    page._form_inputs["hours"].setText("4")
    page._form_inputs["auto_transfer"].setChecked(True)
    page._form_inputs["transfer_amount"].setText("1500")
    page._build_config_from_form()
    assert json.loads(page.config_editor.toPlainText()) == {
        "hours": 4, "auto_transfer": True, "transfer_amount": 1500,
    }

    page._form_inputs["hours"].setText("NaN")
    page._build_config_from_form()
    assert warnings
    assert '"hours": 4' in page.config_editor.toPlainText()


def test_switching_tasks_clears_previous_task_configuration_and_confirmation(page):
    from daedalus.engine_registry import inspect_engine

    operations = [
        cap.to_dict() for cap in inspect_engine()
        if cap.name in {"alertAttacks", "alertLowWine"}
    ]
    page.set_capabilities(operations, enabled=True)
    page._form_inputs["minutes"].setText("15")
    page._build_config_from_form()
    page.confirm_box.setChecked(True)
    page.task_combo.setCurrentIndex(1)
    assert page.config_editor.toPlainText() == "{}"
    assert not page.confirm_box.isChecked()
    assert "hours" in page._form_inputs
