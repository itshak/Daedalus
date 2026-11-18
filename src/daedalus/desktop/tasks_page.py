"""Native opt-in task controls for existing authenticated IkaBot workers.

Only discovered built-in background tasks are offered. User confirmation and
server-side validation are mandatory before a task launch or stop request.
"""

from __future__ import annotations

import json

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
    ComboBox,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.pages import _populate, _table


class TaskControlPage(QWidget):
    refresh_requested = Signal(str)
    start_requested = Signal(str, str, object)
    stop_requested = Signal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tasks_page")
        self._accounts: dict[str, dict[str, object]] = {}
        self._account_ids: list[str] = []
        self._task_names: list[str] = []
        self._enabled = False
        self._rows: list[dict[str, object]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel("Task control"))
        self.status_label = CaptionLabel(
            "Task execution disabled on backend. Restart with --enable-task-control "
            "to manage existing IkaBot sessions."
        )
        layout.addWidget(self.status_label)

        top = QHBoxLayout()
        top.addWidget(BodyLabel("Account"))
        self.account_combo = ComboBox()
        top.addWidget(self.account_combo, 1)
        self.refresh_button = PushButton("Refresh tasks")
        self.refresh_button.clicked.connect(self._refresh)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        task_row = QHBoxLayout()
        task_row.addWidget(BodyLabel("IkaBot background task"))
        self.task_combo = ComboBox()
        task_row.addWidget(self.task_combo, 1)
        layout.addLayout(task_row)

        layout.addWidget(
            CaptionLabel(
                "JSON task parameters. This is the same config object used by IkaBot's "
                "upstream --task/--config interface; the engine will validate it."
            )
        )
        self.config_edit = QPlainTextEdit()
        self.config_edit.setPlainText("{}")
        self.config_edit.setMaximumHeight(116)
        layout.addWidget(self.config_edit)

        self.start_button = PrimaryPushButton("Review and start task")
        self.start_button.clicked.connect(self._start)
        layout.addWidget(self.start_button)
        layout.addWidget(CaptionLabel(
            "Only tasks launched through this controller can be stopped here. "
            "Stopping does not affect unrelated IkaBot processes."
        ))
        self.table = _table(["PID", "Task", "Status", "Started"])
        layout.addWidget(self.table, 1)
        controls = QHBoxLayout()
        self.stop_button = PushButton("Stop selected task")
        self.stop_button.clicked.connect(self._stop)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.status_label.setText(
            "Task controls enabled for existing authenticated sessions. "
            "All game actions require explicit confirmation."
            if enabled else
            "Task execution disabled on backend; viewing operations remains read-only."
        )
        self._update_buttons()

    def _update_buttons(self) -> None:
        active = self._enabled and self.selected_account_id() is not None
        self.start_button.setEnabled(active and bool(self._task_names))
        self.refresh_button.setEnabled(active)
        self.stop_button.setEnabled(
            active and any(entry.get("status") == "running" for entry in self._rows)
        )

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        previous = self.selected_account_id()
        self._accounts = {
            str(account["id"]): account
            for account in accounts if account.get("id") and account.get("enabled")
        }
        self._account_ids = list(self._accounts)
        self.account_combo.clear()
        for account in self._accounts.values():
            label = account.get("label") or account.get("player") or account["id"]
            self.account_combo.addItem(str(label))
        if previous in self._account_ids:
            self.account_combo.setCurrentIndex(self._account_ids.index(previous))
        self._rows = []
        self.table.setRowCount(0)
        self._update_buttons()

    def set_operations(self, operations: list[dict[str, object]]) -> None:
        current = self.selected_task()
        self._task_names = sorted(
            {
                str(operation["name"])
                for operation in operations
                if operation.get("kind") == "background_task" and operation.get("name")
            }
        )
        self.task_combo.clear()
        self.task_combo.addItems(self._task_names)
        if current in self._task_names:
            self.task_combo.setCurrentIndex(self._task_names.index(current))
        self._update_buttons()

    def selected_account_id(self) -> str | None:
        index = self.account_combo.currentIndex()
        return self._account_ids[index] if 0 <= index < len(self._account_ids) else None

    def selected_task(self) -> str | None:
        index = self.task_combo.currentIndex()
        return self._task_names[index] if 0 <= index < len(self._task_names) else None

    def _refresh(self) -> None:
        account_id = self.selected_account_id()
        if self._enabled and account_id is not None:
            self.refresh_requested.emit(account_id)

    def _start(self) -> None:
        account_id, task = self.selected_account_id(), self.selected_task()
        if not self._enabled or account_id is None or task is None:
            return
        raw = self.config_edit.toPlainText()
        if len(raw.encode("utf-8")) > 65536:
            QMessageBox.warning(self, "Invalid config", "Task configuration is too large")
            return
        try:
            config = json.loads(raw)
        except ValueError:
            QMessageBox.warning(self, "Invalid JSON", "Enter a JSON object of task parameters")
            return
        if not isinstance(config, dict) or "session" in config:
            QMessageBox.warning(self, "Invalid config", "Task config must be a JSON object")
            return
        account = self._accounts[account_id]
        confirmation = (
            f"Start IkaBot task '{task}' on {account.get('player')} "
            f"({account.get('world')})?\n\nThis may execute game actions."
        )
        if QMessageBox.question(
            self, "Confirm task launch", confirmation,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.start_requested.emit(account_id, task, config)

    def set_tasks(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        _populate(self.table, [
            [row.get("pid"), row.get("task"), row.get("status"), row.get("started_at")]
            for row in rows
        ])
        self._update_buttons()

    def _stop(self) -> None:
        account_id = self.selected_account_id()
        row_idx = self.table.currentRow()
        if not self._enabled or account_id is None or row_idx < 0 or row_idx >= len(self._rows):
            return
        entry = self._rows[row_idx]
        pid = entry.get("pid")
        if type(pid) is not int or pid <= 0 or entry.get("status") != "running":
            return
        label = f"Stop only the Daedalus-managed '{entry.get('task')}' task (PID {pid})?"
        if QMessageBox.question(
            self, "Confirm task stop", label,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.stop_requested.emit(account_id, pid)
