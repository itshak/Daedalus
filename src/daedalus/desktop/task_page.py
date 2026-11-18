"""Native Fluent task controls; all game mutations require explicit approval.

The page prepares JSON and sends it only to the Daedalus authenticated API,
not Gameforge. The backend and engine independently validate and own the task.
"""

from __future__ import annotations

import json
import uuid

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tasks_page")
        self._account_ids: list[str] = []
        self._task_names: list[str] = []
        self._dispatch_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Engine tasks"))
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
            "Enter a JSON task configuration. Only upstream background tasks are available; "
            "the engine validates parameters before starting."
        ))
        self.config_editor = QPlainTextEdit()
        self.config_editor.setPlaceholderText('{"minutes": 20}')
        self.config_editor.setPlainText("{}")
        self.config_editor.setMaximumHeight(108)
        layout.addWidget(self.config_editor)

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
            if item.get("kind") == "background_task" and item.get("name")
        )
        self.task_combo.clear()
        for name in self._task_names:
            self.task_combo.addItem(name)
        self.status_label.setText(
            "Task control enabled on this backend. Every start requires confirmation."
            if enabled else "Task control disabled; restart backend with explicit opt-in."
        )
        self._clear()
        self._set_controls()

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
