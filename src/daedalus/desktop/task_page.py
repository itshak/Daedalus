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
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
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

# Fixed, reviewed display labels. Unknown built-ins get a readable fallback,
# but dispatch always uses the engine's canonical original task name.
_TASK_LABELS = {
    "alertAttacks": "Attack alerts", "alertLowWine": "Low wine alerts",
    "searchForIslandSpaces": "Find island spaces", "tavernManager": "Tavern manager",
    "constructionList": "Construction planner", "research": "Research manager",
    "resourceTransportManager": "Resource transport manager",
    "consolidateResources": "Consolidate resources", "distributeResources": "Distribute resources",
    "sendResources": "Send resources", "buyResources": "Buy resources",
    "sellResources": "Sell resources", "donationBot": "Island donations",
    "trainArmy": "Train army", "attackBarbarians": "Attack barbarians",
    "autoBarbarians": "Barbarian automation", "activateMiracle": "Activate miracle",
    "activateShrine": "Activate shrine", "UpgradeUnits": "Upgrade units",
    "loginDaily": "Daily login", "dumpWorld": "Export world data",
    "webServer": "IkaBot web server", "autoPirate": "Piracy automation",
}
_CATEGORIES = ("All automations", "Alerts & monitoring", "Resources & trade",
               "City management", "Military & missions", "Advanced")
_TASK_CATEGORIES = {
    "Alerts & monitoring": {"alertAttacks", "alertLowWine", "searchForIslandSpaces"},
    "Resources & trade": {"buyResources", "sellResources", "sendResources",
                          "resourceTransportManager", "consolidateResources",
                          "distributeResources", "donationBot"},
    "City management": {"constructionList", "tavernManager", "research",
                        "loginDaily", "activateMiracle", "activateShrine"},
    "Military & missions": {"trainArmy", "UpgradeUnits", "attackBarbarians",
                            "autoBarbarians", "autoPirate"},
}


def _friendly_task(name: str) -> str:
    if name in _TASK_LABELS:
        return _TASK_LABELS[name]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("_", " ").capitalize()


def _category(name: str) -> str:
    return next((category for category, names in _TASK_CATEGORIES.items()
                 if name in names), "Advanced")


class TasksPage(QWidget):
    refresh_requested = Signal(str)
    preflight_requested = Signal(str, str)
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
        self._all_task_names: list[str] = []
        self._dispatch_enabled = False
        self._prereq_ready: bool | None = None
        self._unresolved = False
        self._advanced_visible = False
        self._config_fields_by_task: dict[str, list[dict[str, object]]] = {}
        self._form_inputs: dict[str, LineEdit | CheckBox | QSpinBox | QDoubleSpinBox] = {}
        self._form_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = (
            "Wine automation" if workflow == "wine" else
            "Construction automation" if workflow == "construction" else
            "Automations"
        )
        layout.addWidget(SubtitleLabel(title))
        if workflow is not None:
            layout.addWidget(CaptionLabel(
                "Registered background tasks for this workflow use the same validated "
                "parameter forms, existing authenticated engine session and separate "
                "confirmation as the Tasks view. Interactive-only operations are read-only."
            ))
        self.status_label = CaptionLabel(
            "Connect to your backend to configure an automation."
        )
        layout.addWidget(self.status_label)

        account_row = QHBoxLayout()
        account_row.addWidget(BodyLabel("Account"))
        self.account_combo = ComboBox()
        self.account_combo.currentIndexChanged.connect(self._account_changed)
        account_row.addWidget(self.account_combo, 1)
        self.refresh_button = PushButton("Refresh tasks")
        self.refresh_button.clicked.connect(self._refresh)
        account_row.addWidget(self.refresh_button)
        layout.addLayout(account_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Category"))
        self.category_combo = ComboBox()
        self.category_combo.addItems(list(_CATEGORIES))
        self.category_combo.currentIndexChanged.connect(self._filter_tasks)
        filter_row.addWidget(self.category_combo, 1)
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("Search automations")
        self.search_input.textChanged.connect(self._filter_tasks)
        filter_row.addWidget(self.search_input, 2)
        layout.addLayout(filter_row)

        task_row = QHBoxLayout()
        task_row.addWidget(BodyLabel("Automation"))
        self.task_combo = ComboBox()
        task_row.addWidget(self.task_combo, 1)
        layout.addLayout(task_row)
        self.task_description = CaptionLabel(
            "Choose an automation. The game engine checks all parameters before launch."
        )
        self.task_description.setWordWrap(True)
        layout.addWidget(self.task_description)
        self.prerequisite_label = CaptionLabel("Select an automation to check readiness.")
        self.prerequisite_label.setWordWrap(True)
        layout.addWidget(self.prerequisite_label)


        layout.addWidget(CaptionLabel(
            "Settings are built from the engine's registered parameters. "
            "You can use the defaults or change the fields below."
        ))
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setMaximumHeight(225)
        self.parameter_container = QWidget()
        self.parameter_layout = QFormLayout(self.parameter_container)
        self.parameter_scroll.setWidget(self.parameter_container)
        layout.addWidget(self.parameter_scroll)
        self.advanced_toggle = PushButton("Show advanced JSON options")
        self.advanced_toggle.clicked.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_toggle)
        self.advanced_note = CaptionLabel(
            "Advanced mode overrides the guided settings with a custom JSON object. "
            "Use Build JSON to copy the current guided fields into the editor."
        )
        self.advanced_note.setWordWrap(True)
        layout.addWidget(self.advanced_note)
        self.build_json_button = PushButton("Build JSON from guided settings")
        self.build_json_button.clicked.connect(self._build_config_from_form)
        layout.addWidget(self.build_json_button)
        self.config_editor = QPlainTextEdit()
        self.config_editor.setPlaceholderText('{"minutes": 20}')
        self.config_editor.setPlainText("{}")
        self.config_editor.setMaximumHeight(108)
        layout.addWidget(self.config_editor)
        self.advanced_note.hide()
        self.build_json_button.hide()
        self.config_editor.hide()
        self.config_editor.textChanged.connect(self._review_advanced_json)
        self.task_combo.currentIndexChanged.connect(self._selected_task_changed)

        launch_row = QHBoxLayout()
        self.confirm_box = CheckBox("I reviewed this automation and approve starting it")
        launch_row.addWidget(self.confirm_box)
        launch_row.addStretch(1)
        self.start_button = PrimaryPushButton("Start automation")
        self.start_button.clicked.connect(self._start)
        launch_row.addWidget(self.start_button)
        layout.addLayout(launch_row)

        layout.addWidget(SubtitleLabel("Running automations"))
        self.task_table = _table(["Task", "Status", "PID", "Task ID"])
        layout.addWidget(self.task_table, 2)

        stop_row = QHBoxLayout()
        self.stop_button = PushButton("Stop selected task")
        self.stop_button.clicked.connect(self._stop)
        stop_row.addWidget(self.stop_button)
        stop_row.addStretch(1)
        layout.addLayout(stop_row)

        layout.addWidget(SubtitleLabel("Request history & recovery"))
        layout.addWidget(CaptionLabel(
            "If a request is uncertain, review its game state before clearing it. "
            "Daedalus never retries it automatically."
        ))
        self.request_table = _table(["Request ID", "Task", "Status", "Task ID"])
        layout.addWidget(self.request_table, 1)
        self.reconcile_button = PushButton("Mark checked request as reconciled")
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
        previous = self.selected_account_id()
        self._account_ids = [str(a["id"]) for a in accounts
                             if a.get("id") and a.get("enabled")]
        self.account_combo.blockSignals(True)
        try:
            self.account_combo.clear()
            for a in accounts:
                if a.get("id") in self._account_ids:
                    self.account_combo.addItem(str(
                        a.get("label") or a.get("player") or a["id"]
                    ))
            if previous in self._account_ids:
                self.account_combo.setCurrentIndex(self._account_ids.index(previous))
        finally:
            self.account_combo.blockSignals(False)
        self._account_changed()

    def select_account(self, account_id: str) -> None:
        if account_id in self._account_ids:
            index = self._account_ids.index(account_id)
            if self.account_combo.currentIndex() != index:
                self.account_combo.setCurrentIndex(index)

    def selected_task_name(self) -> str | None:
        index = self.task_combo.currentIndex()
        return self._task_names[index] if 0 <= index < len(self._task_names) else None

    def select_task(self, task_name: str) -> bool:
        if task_name not in self._all_task_names:
            return False
        self.category_combo.setCurrentIndex(0)
        self.search_input.clear()
        self._filter_tasks()
        self.task_combo.setCurrentIndex(self._task_names.index(task_name))
        return True

    def _account_changed(self, *_args: object) -> None:
        self._clear()
        self._selected_task_changed()

    def set_capabilities(self, operations: list[dict[str, object]], enabled: bool) -> None:
        self._dispatch_enabled = enabled
        self._all_task_names = sorted((
            str(item["name"]) for item in operations
            if item.get("kind") == "background_task" and item.get("name")
            and (self._workflow is None
                 or self._workflow in str(item["name"]).casefold())
        ), key=_friendly_task)
        self._config_fields_by_task = {}
        for item in operations:
            name = item.get("name")
            if name not in self._all_task_names:
                continue
            fields: list[dict[str, object]] = []
            raw_fields = item.get("config_fields")
            if isinstance(raw_fields, (list, tuple)):
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
        self.status_label.setText(
            "Choose an automation. Daedalus checks prerequisites before enabling Start."
            if enabled and self._all_task_names else
            "No background automations for this workflow."
            if enabled and self._workflow is not None else
            "Task control disabled on this backend; use a privately enabled server."
        )
        self._clear()
        self._filter_tasks()

    def _filter_tasks(self, *_args: object) -> None:
        old = self.selected_task_name()
        category = self.category_combo.currentText() or _CATEGORIES[0]
        search = self.search_input.text().strip().casefold()
        self._task_names = [name for name in self._all_task_names
            if (category == "All automations" or _category(name) == category)
            and (not search or search in _friendly_task(name).casefold()
                 or search in name.casefold())]
        self.task_combo.blockSignals(True)
        try:
            self.task_combo.clear()
            for name in self._task_names:
                self.task_combo.addItem(_friendly_task(name))
            if old in self._task_names:
                self.task_combo.setCurrentIndex(self._task_names.index(old))
        finally:
            self.task_combo.blockSignals(False)
        self._selected_task_changed()

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        for widget in (self.advanced_note, self.config_editor, self.build_json_button):
            widget.setVisible(self._advanced_visible)
        self.advanced_toggle.setText(
            "Hide advanced JSON options" if self._advanced_visible
            else "Show advanced JSON options"
        )
        if self._advanced_visible:
            self._build_config_from_form()

    def _review_advanced_json(self) -> None:
        """Hand-edited JSON supersedes unbuilt form values deliberately."""
        self._form_dirty = False

    def _mark_form_dirty(self, *_args: object) -> None:
        self._form_dirty = True

    def _selected_task_changed(self, *_args: object) -> None:
        while self.parameter_layout.rowCount():
            self.parameter_layout.removeRow(0)
        self._form_inputs.clear()
        name = self.selected_task_name()
        fields = self._config_fields_by_task.get(name or "", [])
        self.task_description.setText(
            f"{_friendly_task(name)}  ·  {_category(name)}. "
            "You approve every launch; nothing runs when you select an option."
            if name else "No automations match this filter."
        )
        for field in fields:
            key = str(field["name"])
            kind = str(field["type"])
            default = field.get("default")
            label = f"{key.replace('_', ' ').capitalize()}{' *' if field['required'] else ''}"
            if kind == "boolean":
                widget = CheckBox("Enabled")
                widget.setChecked(default is True)
                widget.stateChanged.connect(self._mark_form_dirty)
            elif kind == "integer" and type(default) is int and -1_000_000 <= default <= 1_000_000:
                widget = QSpinBox()
                widget.setRange(-1_000_000, 1_000_000)
                widget.setValue(default)
                if key == "minutes" and name == "alertAttacks":
                    widget.setMinimum(3)
                    widget.setSuffix(" min")
                widget.valueChanged.connect(self._mark_form_dirty)
            elif kind == "number" and type(default) in (int, float) and -1_000_000 <= default <= 1_000_000:
                widget = QDoubleSpinBox()
                widget.setRange(-1_000_000, 1_000_000)
                widget.setDecimals(2)
                widget.setValue(float(default))
                widget.valueChanged.connect(self._mark_form_dirty)
            else:
                widget = LineEdit()
                if kind == "json":
                    widget.setPlaceholderText(
                        'JSON value (e.g. 10, "text", [1,2])'
                        if field["required"] else "Optional value"
                    )
                    if default is not None:
                        widget.setText(json.dumps(default, ensure_ascii=False))
                elif default is not None:
                    widget.setText(str(default))
                else:
                    widget.setPlaceholderText("Required" if field["required"] else "Optional")
                widget.textChanged.connect(self._mark_form_dirty)
            self.parameter_layout.addRow(label, widget)
            self._form_inputs[key] = widget
        self.parameter_scroll.setVisible(bool(fields))
        self.build_json_button.setEnabled(bool(fields))
        self.confirm_box.setChecked(False)
        self.config_editor.setPlainText("{}")
        self._form_dirty = False
        self._prereq_ready = None
        self.prerequisite_label.setText(
            "Checking this account's task prerequisites…" if self._dispatch_enabled and name
            else "Select an automation to see whether it is ready."
        )
        self._set_controls()
        account_id = self.selected_account_id()
        if self._dispatch_enabled and account_id and name:
            self.preflight_requested.emit(account_id, name)

    def set_preflight(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or result.get("task") != self.selected_task_name()):
            return
        self._prereq_ready = result.get("ready") is True
        self._unresolved = result.get("unresolved_request") is True or self._unresolved
        if self._unresolved:
            self.prerequisite_label.setText(
                "A previous task request needs manual reconciliation below before "
                "starting any further automation."
            )
        elif self._prereq_ready:
            self.prerequisite_label.setText(
                "Ready to configure. Known prerequisites passed; the engine will "
                "perform its final checks before starting."
            )
        elif result.get("reason") == "notifications_required":
            self.prerequisite_label.setText(
                "Needs setup: attack/wine alerts require Telegram or Discord notifications. "
                "Configure notifications in IkaBot before starting this alert."
            )
        else:
            self.prerequisite_label.setText("Not ready: check this account in Accounts.")
        self._set_controls()

    def set_preflight_unavailable(self) -> None:
        if self._prereq_ready is None and self._dispatch_enabled:
            self.prerequisite_label.setText(
                "Could not check task readiness. Refresh your connection; no task was started."
            )
            self._set_controls()

    def _form_config(self) -> dict[str, object]:
        name = self.selected_task_name() or ""
        config: dict[str, object] = {}
        for field in self._config_fields_by_task.get(name, []):
            key = str(field["name"])
            kind = str(field["type"])
            widget = self._form_inputs[key]
            if isinstance(widget, CheckBox):
                config[key] = widget.isChecked()
                continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                config[key] = widget.value()
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
                    value = json.loads(text, parse_constant=lambda _: (
                        _ for _ in ()
                    ).throw(ValueError("Nonfinite number")))
                except ValueError as exc:
                    raise ValueError(f"Enter a valid value for {key}") from exc
                if kind == "number" and type(value) not in (float, int):
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
        self._unresolved = any(
            row.get("status") in {"dispatching", "unconfirmed"} for row in requests
        )
        _populate(self.task_table, [
            [_friendly_task(str(task.get("task", ""))), task.get("status"),
             task.get("pid"), task.get("task_id")] for task in tasks
        ])
        _populate(self.request_table, [
            [row.get("request_id"), _friendly_task(str(row.get("task", ""))),
             row.get("status"), row.get("task_id")] for row in requests
        ])
        if self._unresolved:
            self.prerequisite_label.setText(
                "A previous request is unconfirmed. Check game state, then "
                "reconcile it below before starting another task."
            )
        self._set_controls()

    def _clear(self, *_args: object) -> None:
        self.task_table.setRowCount(0)
        self.request_table.setRowCount(0)
        self._unresolved = False
        self._set_controls()

    def _set_controls(self) -> None:
        enabled = self._dispatch_enabled and bool(self._account_ids)
        self.start_button.setEnabled(
            enabled and bool(self._task_names)
            and self._prereq_ready is True and not self._unresolved
        )
        self.refresh_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.reconcile_button.setEnabled(enabled)

    def _refresh(self) -> None:
        account_id = self.selected_account_id()
        if account_id and self._dispatch_enabled:
            self.refresh_requested.emit(account_id)

    def _start(self) -> None:
        account_id = self.selected_account_id()
        task = self.selected_task_name()
        if not self._dispatch_enabled or account_id is None or task is None:
            return
        if self._unresolved:
            QMessageBox.warning(self, "Request needs review",
                "Resolve the earlier unconfirmed request before starting another task.")
            return
        if self._prereq_ready is not True:
            QMessageBox.warning(self, "Task not ready",
                "Check the setup message above. No game task was started.")
            return
        if not self.confirm_box.isChecked():
            QMessageBox.warning(self, "Confirm automation",
                "Check the authorization box before starting this automation.")
            return
        try:
            if self._advanced_visible:
                if self._form_dirty:
                    QMessageBox.warning(self, "Guided settings changed",
                        "Build JSON from guided settings or hide Advanced to use the form.")
                    return
                config = json.loads(self.config_editor.toPlainText())
                if not isinstance(config, dict):
                    raise ValueError("Advanced configuration must be a JSON object")
            else:
                config = self._form_config()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Invalid automation settings", str(exc))
            return
        params = ", ".join(f"{key}: {value}" for key, value in config.items()) or "Default settings"
        answer = QMessageBox.question(
            self, "Review automation",
            f"Start {_friendly_task(task)} for {account_id}?\n\n"
            f"Settings: {params[:600]}\n\n"
            "This automation can change game state. "
            "You can stop a running task on this page.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.launch_requested.emit(account_id, task, config, str(uuid.uuid4()))
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
