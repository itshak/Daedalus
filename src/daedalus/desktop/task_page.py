"""Native Fluent task controls; all game mutations require explicit approval.

The page prepares JSON and sends it only to the Daedalus authenticated API,
not Gameforge. The backend and engine independently validate and own the task.
"""

from __future__ import annotations

import json
import re
import uuid

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.pages import _populate, _table


class TasksPage(QWidget):
    refresh_requested = Signal(str)
    launch_requested = Signal(str, str, object, str)
    stop_requested = Signal(str, str)
    reconcile_requested = Signal(str, str)

    def __init__(self, parent=None, *, workflow: str | None = None) -> None:
        super().__init__(parent)
        if workflow not in {None, "wine", "construction"}:
            raise ValueError("Unsupported native task workflow")
        self._workflow = workflow
        self.setObjectName("tasks_page" if workflow is None else f"{workflow}_page")
        self._account_ids: list[str] = []
        self._task_names: list[str] = []
        self._dispatch_enabled = False
        self._config_fields_by_task: dict[str, list[dict[str, object]]] = {}
        self._form_inputs: dict[str, LineEdit | CheckBox] = {}
        self._form_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = (
            "Wine automation" if workflow == "wine" else
            "Construction automation" if workflow == "construction" else
            "Engine tasks"
        )
        layout.addWidget(SubtitleLabel(title))
        if workflow is not None:
            layout.addWidget(CaptionLabel(
                "Registered background tasks for this workflow use the same validated "
                "parameter forms, existing authenticated engine session and separate "
                "confirmation as the Tasks view. Interactive-only operations are read-only."
            ))
        self.status_label = CaptionLabel(
            "Task control disabled. Enable it explicitly on your private backend."
        )
        layout.addWidget(self.status_label)

        account_row = QHBoxLayout()
        account_row.addWidget(BodyLabel("Account"))
        self.account_combo = ComboBox()
        self.account_combo.currentIndexChanged.connect(self._clear)
        account_row.addWidget(self.account_combo, 1)
        self.refresh_button = PushButton("Refresh tasks")
        self.refresh_button.clicked.connect(self._refresh)
        account_row.addWidget(self.refresh_button)
        layout.addLayout(account_row)

        task_row = QHBoxLayout()
        task_row.addWidget(BodyLabel("IkaBot task"))
        self.task_combo = ComboBox()
        task_row.addWidget(self.task_combo, 1)
        layout.addLayout(task_row)

        layout.addWidget(CaptionLabel(
            "Parameters from the public IkaBot task signature. Unknown types accept JSON. "
            "Review the generated configuration before starting."
        ))
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setMaximumHeight(174)
        self.parameter_container = QWidget()
        self.parameter_layout = QFormLayout(self.parameter_container)
        self.parameter_scroll.setWidget(self.parameter_container)
        layout.addWidget(self.parameter_scroll)
        self.build_json_button = PushButton("Build JSON from parameters")
        self.build_json_button.clicked.connect(self._build_config_from_form)
        layout.addWidget(self.build_json_button)

        layout.addWidget(CaptionLabel(
            "Review the JSON configuration or paste an advanced IkaBot config. "
            "The engine validates every value before dispatch."
        ))
        self.config_editor = QPlainTextEdit()
        self.config_editor.setPlaceholderText('{"minutes": 20}')
        self.config_editor.setPlainText("{}")
        self.config_editor.setMaximumHeight(108)
        layout.addWidget(self.config_editor)
        self.config_editor.textChanged.connect(self._review_advanced_json)
        self.task_combo.currentIndexChanged.connect(self._selected_task_changed)

        launch_row = QHBoxLayout()
        self.confirm_box = CheckBox("I authorize the selected game operation")
        launch_row.addWidget(self.confirm_box)
        launch_row.addStretch(1)
        self.start_button = PrimaryPushButton("Start task")
        self.start_button.clicked.connect(self._start)
        launch_row.addWidget(self.start_button)
        layout.addLayout(launch_row)

        layout.addWidget(BodyLabel("Tasks managed by the connected IkaBot process"))
        self.task_table = _table(["Task", "Status", "PID", "Task ID"])
        layout.addWidget(self.task_table, 2)

        stop_row = QHBoxLayout()
        self.stop_button = PushButton("Stop selected task")
        self.stop_button.clicked.connect(self._stop)
        stop_row.addWidget(self.stop_button)
        stop_row.addStretch(1)
        layout.addLayout(stop_row)

        layout.addWidget(BodyLabel("Durable task requests (no credentials or configuration stored)"))
        self.request_table = _table(["Request ID", "Task", "Status", "Task ID"])
        layout.addWidget(self.request_table, 1)
        self.reconcile_button = PushButton("Acknowledge manually reconciled request")
        self.reconcile_button.setToolTip(
            "Only use after checking engine and game state to resolve an uncertain launch"
        )
        self.reconcile_button.clicked.connect(self._reconcile)
        layout.addWidget(self.reconcile_button)
        self._set_controls()

    def selected_account_id(self) -> str | None:
        idx = self.account_combo.currentIndex()
        return self._account_ids[idx] if 0 <= idx < len(self._account_ids) else None

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        selected = self.selected_account_id()
        self._account_ids = [
            str(account["id"]) for account in accounts
            if account.get("id") and account.get("enabled")
        ]
        self.account_combo.clear()
        for account in accounts:
            if account.get("id") in self._account_ids:
                self.account_combo.addItem(
                    str(account.get("label") or account.get("player") or account["id"])
                )
        if selected in self._account_ids:
            self.account_combo.setCurrentIndex(self._account_ids.index(selected))
        self._clear()
        self._set_controls()

    def set_capabilities(self, operations: list[dict[str, object]], enabled: bool) -> None:
        self._dispatch_enabled = enabled
        self._task_names = sorted(
            str(item["name"]) for item in operations
            if (
                item.get("kind") == "background_task"
                and item.get("name")
                and (
                    self._workflow is None
                    or self._workflow in str(item["name"]).casefold()
                )
            )
        )
        self._config_fields_by_task = {}
        for item in operations:
            name = item.get("name")
            if name not in self._task_names:
                continue
            raw_fields = item.get("config_fields")
            fields: list[dict[str, object]] = []
            if isinstance(raw_fields, list | tuple):
                for field in raw_fields[:32]:
                    if not isinstance(field, dict):
                        continue
                    key = field.get("name")
                    if (
                        not isinstance(key, str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", key)
                        or key.casefold() in {"session", "token", "password", "cookie"}
                        or field.get("type") not in {"boolean", "integer", "number", "text", "json"}
                    ):
                        continue
                    fields.append({
                        "name": key, "type": field["type"],
                        "required": field.get("required") is True,
                        **({"default": field["default"]} if "default" in field else {}),
                    })
            self._config_fields_by_task[str(name)] = fields
        self.task_combo.clear()
        for name in self._task_names:
            self.task_combo.addItem(name)
        self._selected_task_changed()
        self.status_label.setText(
            "Task control enabled on this backend. Every start requires confirmation."
            if enabled and self._task_names else
            "No compatible background tasks registered for this workflow."
            if enabled and self._workflow is not None else
            "Task control disabled; restart backend with explicit opt-in."
        )
        self._clear()
        self._set_controls()

    def _review_advanced_json(self) -> None:
        """Hand-edited JSON supersedes unbuilt form values deliberately."""
        self._form_dirty = False

    def _mark_form_dirty(self, *_args: object) -> None:
        self._form_dirty = True

    def _selected_task_changed(self, *_args: object) -> None:
        while self.parameter_layout.rowCount():
            self.parameter_layout.removeRow(0)
        self._form_inputs.clear()
        index = self.task_combo.currentIndex()
        name = self._task_names[index] if 0 <= index < len(self._task_names) else ""
        fields = self._config_fields_by_task.get(name, [])
        for field in fields:
            field_name = str(field["name"])
            kind = str(field["type"])
            label = f"{field_name} ({kind}{', required' if field['required'] else ''})"
            if kind == "boolean":
                widget = CheckBox()
                widget.setChecked(field.get("default") is True)
                widget.stateChanged.connect(self._mark_form_dirty)
            else:
                widget = LineEdit()
                if kind == "json":
                    widget.setPlaceholderText(
                        'JSON value (e.g. 10, "text", [1,2])'
                        if field["required"] else "Optional JSON value"
                    )
                elif field.get("default") is not None:
                    widget.setPlaceholderText(f"Default: {str(field['default'])[:80]}")
                else:
                    widget.setPlaceholderText("Required" if field["required"] else "Optional")
                widget.textChanged.connect(self._mark_form_dirty)
            self.parameter_layout.addRow(label, widget)
            self._form_inputs[field_name] = widget
        self.parameter_scroll.setVisible(bool(fields))
        self.build_json_button.setEnabled(bool(fields))
        self.confirm_box.setChecked(False)
        self.config_editor.setPlainText("{}")
        self._form_dirty = False

    def _form_config(self) -> dict[str, object]:
        index = self.task_combo.currentIndex()
        name = self._task_names[index] if 0 <= index < len(self._task_names) else ""
        config: dict[str, object] = {}
        for field in self._config_fields_by_task.get(name, []):
            key = str(field["name"])
            kind = str(field["type"])
            widget = self._form_inputs[key]
            if isinstance(widget, CheckBox):
                config[key] = widget.isChecked()
                continue
            text = widget.text().strip()
            if not text:
                if field["required"]:
                    raise ValueError(f"Missing required parameter: {key}")
                continue
            if len(text) > 2000:
                raise ValueError(f"Parameter too long: {key}")
            if kind == "text":
                value: object = text
            elif kind == "integer":
                if not re.fullmatch(r"-?[0-9]{1,15}", text):
                    raise ValueError(f"Enter a whole number for {key}")
                value = int(text)
            else:
                try:
                    value = json.loads(
                        text,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite number")),
                    )
                except ValueError as exc:
                    raise ValueError(f"Enter valid JSON for {key}") from exc
                if kind == "number" and (type(value) not in (float, int)):
                    raise ValueError(f"Enter a number for {key}")
            config[key] = value
        if len(json.dumps(config, allow_nan=False).encode("utf-8")) > 16384:
            raise ValueError("Task configuration exceeds the safe size limit")
        return config

    def _build_config_from_form(self) -> None:
        try:
            config = self._form_config()
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid task parameters", str(exc))
            return
        self.config_editor.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))
        self._form_dirty = False

    def set_tasks(self, data: dict[str, object]) -> None:
        tasks = data.get("engine_tasks", [])
        requests = data.get("requests", [])
        _populate(
            self.task_table,
            [[task.get("task"), task.get("status"), task.get("pid"), task.get("task_id")]
             for task in tasks],
        )
        _populate(
            self.request_table,
            [[row.get("request_id"), row.get("task"), row.get("status"), row.get("task_id")]
             for row in requests],
        )

    def _clear(self, *_args: object) -> None:
        self.task_table.setRowCount(0)
        self.request_table.setRowCount(0)

    def _set_controls(self) -> None:
        enabled = self._dispatch_enabled and bool(self._account_ids)
        self.start_button.setEnabled(enabled and bool(self._task_names))
        self.refresh_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.reconcile_button.setEnabled(enabled)

    def _refresh(self) -> None:
        account_id = self.selected_account_id()
        if account_id and self._dispatch_enabled:
            self.refresh_requested.emit(account_id)

    def _start(self) -> None:
        account_id = self.selected_account_id()
        task_index = self.task_combo.currentIndex()
        if not self._dispatch_enabled or account_id is None or not 0 <= task_index < len(self._task_names):
            return
        if self._form_dirty:
            QMessageBox.warning(
                self, "Review task parameters",
                "Press Build JSON from parameters and review the result before starting."
            )
            return
        if not self.confirm_box.isChecked():
            QMessageBox.warning(self, "Confirm task", "Check the authorization box first.")
            return
        try:
            config = json.loads(self.config_editor.toPlainText())
        except ValueError:
            QMessageBox.warning(self, "Invalid JSON", "Task configuration must be valid JSON.")
            return
        if not isinstance(config, dict):
            QMessageBox.warning(self, "Invalid configuration", "Use a JSON object for task arguments.")
            return
        answer = QMessageBox.question(
            self, "Start IkaBot game task",
            f"Start {self._task_names[task_index]} for {account_id}? "
            "This can change game state through the existing authenticated session.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.launch_requested.emit(
            account_id, self._task_names[task_index], config, str(uuid.uuid4())
        )
        self.confirm_box.setChecked(False)

    def _stop(self) -> None:
        account_id = self.selected_account_id()
        row = self.task_table.currentRow()
        if account_id is None or row < 0 or not self._dispatch_enabled:
            return
        item = self.task_table.item(row, 3)
        if item is None:
            return
        task_id = item.text()
        answer = QMessageBox.question(
            self, "Stop IkaBot task",
            "Stop this Daedalus-managed background task? No unrelated task will be stopped.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.stop_requested.emit(account_id, task_id)

    def _reconcile(self) -> None:
        account_id = self.selected_account_id()
        row = self.request_table.currentRow()
        if account_id is None or row < 0 or not self._dispatch_enabled:
            return
        status = self.request_table.item(row, 2)
        item = self.request_table.item(row, 0)
        if item is None or status is None or status.text() not in {"unconfirmed", "dispatching"}:
            return
        answer = QMessageBox.question(
            self, "Manual game-state reconciliation",
            "Have you independently checked the task list and game state to confirm that "
            "this uncertain request will not be replayed? This action does not start a task.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.reconcile_requested.emit(account_id, item.text())
