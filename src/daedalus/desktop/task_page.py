"""Native Fluent task controls; all game mutations require explicit approval.

The page prepares JSON and sends it only to the Daedalus authenticated API,
not Gameforge. The backend and engine independently validate and own the task.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    DoubleSpinBox,
    LineEdit,
    Pivot,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    SpinBox,
    SubtitleLabel,
)

from daedalus.desktop.design_system import style_form_input
from daedalus.desktop.pages import _populate, _table
from daedalus.desktop.task_presentation import (
    configuration_summary,
    expert_configuration_needed,
    present_fields,
    task_explanation,
)

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
_TEMPLATE_TASKS = {
    "wine": {"alertLowWine", "tavernManager"},
    "construction": {"constructionList", "research"},
}
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
    batch_status_requested = Signal(object)
    batch_launch_requested = Signal(object, str, object)

    def __init__(self, parent=None, *, workflow: str | None = None) -> None:
        super().__init__(parent)
        if workflow not in {None, "wine", "construction"}:
            raise ValueError("Unsupported native task workflow")
        self._workflow = workflow
        self._template_filter: str | None = None
        self.setObjectName("tasks_page" if workflow is None else f"{workflow}_page")
        self._account_ids: list[str] = []
        self._task_names: list[str] = []
        self._all_task_names: list[str] = []
        self._dispatch_enabled = False
        self._prereq_ready: bool | None = None
        self._unresolved = False
        self._advanced_visible = False
        self._config_fields_by_task: dict[str, list[dict[str, object]]] = {}
        self._catalog_operations: list[dict[str, object]] = []
        self._form_inputs: dict[str, LineEdit | CheckBox | QSpinBox | QDoubleSpinBox] = {}
        self._form_dirty = False
        self._bulk_account_ids: list[str] = []
        self._account_metadata: list[dict[str, object]] = []
        self._all_account_metadata: list[dict[str, object]] = []
        self._status_account_ids: list[str] = []

        # Large native forms must scroll instead of clipping at 900x650.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        scroll.setWidget(content)
        self.pivot = Pivot(self)
        self.pivot.setAccessibleName("Automation workspace sections")
        self.stack = QStackedWidget(self)
        outer.addWidget(self.pivot)
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(scroll)
        self.pivot.addItem(
            routeKey="configure", text="Configure",
            onClick=lambda: self._show_section(0),
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
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

        template_row = QHBoxLayout()
        self.wine_template_button = PushButton("Wine")
        self.wine_template_button.setToolTip("Find tavern and low-wine automations")
        self.wine_template_button.clicked.connect(lambda: self.select_workflow("wine"))
        template_row.addWidget(self.wine_template_button)
        self.construction_template_button = PushButton("Construction")
        self.construction_template_button.setToolTip(
            "Find construction and research automations"
        )
        self.construction_template_button.clicked.connect(
            lambda: self.select_workflow("construction")
        )
        template_row.addWidget(self.construction_template_button)
        self.all_templates_button = PushButton("All automations")
        self.all_templates_button.clicked.connect(lambda: self.select_workflow("all"))
        template_row.addWidget(self.all_templates_button)
        self.catalog_button = PushButton("Explore catalog…")
        self.catalog_button.clicked.connect(self._open_catalog)
        template_row.addWidget(self.catalog_button)
        template_row.addStretch(1)
        layout.addLayout(template_row)

        account_row = QHBoxLayout()
        account_row.addWidget(BodyLabel("Account"))
        self.account_combo = ComboBox()
        self.account_combo.currentIndexChanged.connect(self._account_changed)
        account_row.addWidget(self.account_combo, 1)
        self.refresh_button = PushButton("Refresh tasks")
        self.refresh_button.clicked.connect(self._refresh)
        account_row.addWidget(self.refresh_button)
        layout.addLayout(account_row)

        scope_row = QHBoxLayout()
        self.choose_bulk_button = PushButton("Choose accounts…")
        self.choose_bulk_button.setAccessibleName("Choose accounts for automation actions")
        self.choose_bulk_button.clicked.connect(self._choose_bulk_accounts)
        scope_row.addWidget(self.choose_bulk_button)
        self.view_all_button = PushButton("View all task statuses")
        self.view_all_button.setToolTip("Read-only task status for every configured enabled account")
        self.view_all_button.clicked.connect(self._refresh_all)
        scope_row.addWidget(self.view_all_button)
        self.view_selected_button = PushButton("View selected statuses")
        self.view_selected_button.clicked.connect(self._refresh_selected)
        scope_row.addWidget(self.view_selected_button)
        scope_row.addStretch(1)
        layout.addLayout(scope_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Category"))
        self.category_combo = ComboBox()
        self.category_combo.addItems(list(_CATEGORIES))
        self.category_combo.currentIndexChanged.connect(self._filter_tasks)
        filter_row.addWidget(self.category_combo, 1)
        self.search_input = SearchLineEdit()
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
        self.expert_note = CaptionLabel("")
        self.expert_note.setWordWrap(True)
        self.expert_note.hide()
        layout.addWidget(self.expert_note)
        self.prerequisite_label = CaptionLabel("Select an automation to check readiness.")
        self.prerequisite_label.setWordWrap(True)
        layout.addWidget(self.prerequisite_label)


        layout.addWidget(CaptionLabel(
            "Settings are built from the engine's registered parameters. "
            "You can use the defaults or change the fields below."
        ))
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setMaximumHeight(320)
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
        self.import_config_button = PushButton("Import a prepared configuration…")
        self.import_config_button.setToolTip(
            "Load an explicitly chosen, small JSON configuration previously prepared "
            "for this engine task. Daedalus validates allowed parameter names."
        )
        self.import_config_button.clicked.connect(self._import_advanced_config)
        layout.addWidget(self.import_config_button)
        self.config_editor = QPlainTextEdit()
        self.config_editor.setPlaceholderText('{"minutes": 20}')
        self.config_editor.setPlainText("{}")
        self.config_editor.setMaximumHeight(108)
        layout.addWidget(self.config_editor)
        self.advanced_note.hide()
        self.build_json_button.hide()
        self.import_config_button.hide()
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

        batch_row = QHBoxLayout()
        self.bulk_note = CaptionLabel(
            "Multi-account actions require a separate review. Each selected account is "
            "checked independently; dispatch stops if any account is not ready."
        )
        self.bulk_note.setWordWrap(True)
        batch_row.addWidget(self.bulk_note, 1)
        self.start_selected_button = PushButton("Start for selected…")
        self.start_selected_button.setToolTip(
            "Review all chosen accounts and run a distinct authorized task request per account"
        )
        self.start_selected_button.clicked.connect(self._start_selected)
        batch_row.addWidget(self.start_selected_button)
        layout.addLayout(batch_row)

        running_panel = QWidget(self.stack)
        layout = QVBoxLayout(running_panel)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)
        self.stack.addWidget(running_panel)
        self.pivot.addItem(
            routeKey="running", text="Running",
            onClick=lambda: self._show_section(1),
        )
        layout.addWidget(SubtitleLabel("Running automations"))
        self.task_table = _table(["Task", "Status", "PID", "Task ID"])
        layout.addWidget(self.task_table, 2)

        stop_row = QHBoxLayout()
        self.stop_button = PushButton("Stop selected task")
        self.stop_button.clicked.connect(self._stop)
        stop_row.addWidget(self.stop_button)
        stop_row.addStretch(1)
        layout.addLayout(stop_row)

        history_panel = QWidget(self.stack)
        layout = QVBoxLayout(history_panel)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)
        self.stack.addWidget(history_panel)
        self.pivot.addItem(
            routeKey="history", text="History",
            onClick=lambda: self._show_section(2),
        )
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

        multi_panel = QWidget(self.stack)
        layout = QVBoxLayout(multi_panel)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)
        self.stack.addWidget(multi_panel)
        self.pivot.addItem(
            routeKey="accounts", text="All accounts",
            onClick=lambda: self._show_section(3),
        )
        layout.addWidget(SubtitleLabel("Multi-account task overview"))
        self.multi_summary = CaptionLabel(
            "View all accounts or selected accounts to see their task status side by side."
        )
        self.multi_summary.setWordWrap(True)
        layout.addWidget(self.multi_summary)
        self.multi_table = _table(["Account", "Running tasks", "Needs review", "Status"])
        self.multi_table.setMaximumHeight(185)
        layout.addWidget(self.multi_table)
        layout.addStretch(1)
        self._show_section(0)
        self._set_controls()

    def _show_section(self, index: int) -> None:
        """Fluent pivot for discover/configure, running, history and multi-account views."""
        keys = ("configure", "running", "history", "accounts")
        if not 0 <= index < len(keys):
            raise ValueError("Unknown automation section")
        self.stack.setCurrentIndex(index)
        self.pivot.setCurrentItem(keys[index])

    def selected_account_id(self) -> str | None:
        idx = self.account_combo.currentIndex()
        return self._account_ids[idx] if 0 <= idx < len(self._account_ids) else None

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        previous = self.selected_account_id()
        # Read-only "All accounts" includes disabled accounts; only enabled
        # accounts can be offered as candidates for task mutation.
        self._all_account_metadata = [
            dict(a) for a in accounts
            if isinstance(a.get("id"), str) and a["id"]
        ]
        self._status_account_ids = [str(a["id"]) for a in self._all_account_metadata]
        self._account_metadata = [
            a for a in self._all_account_metadata if a.get("enabled") is True
        ]
        self._account_ids = [str(a["id"]) for a in self._account_metadata]
        self._bulk_account_ids = [
            aid for aid in self._bulk_account_ids if aid in self._status_account_ids
        ]
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
        if not self._bulk_account_ids:
            self._bulk_account_ids = list(self._account_ids)
        self._update_bulk_buttons()
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
        self._template_filter = None
        self.category_combo.setCurrentIndex(0)
        self.search_input.clear()
        self._filter_tasks()
        self.task_combo.setCurrentIndex(self._task_names.index(task_name))
        self._show_section(0)
        return True

    def select_workflow(self, workflow: str) -> None:
        self._show_section(0)
        if workflow not in {"all", "wine", "construction"}:
            raise ValueError("Unsupported automation template")
        self._template_filter = None if workflow == "all" else workflow
        self.category_combo.setCurrentIndex(0)
        self.search_input.clear()
        self._filter_tasks()

    def _open_catalog(self) -> None:
        """Read-only interactive and background capability inventory in one workspace."""
        from daedalus.desktop.pages import OperationsPage

        dialog = QDialog(self)
        dialog.setWindowTitle("Explore IkaBot operations")
        dialog.resize(790, 540)
        content = QVBoxLayout(dialog)
        content.setContentsMargins(12, 12, 12, 12)
        catalog = OperationsPage(dialog)
        catalog.set_operations(self._catalog_operations)
        catalog.configure_requested.connect(
            lambda name: (dialog.accept(), self.select_task(name))
        )
        content.addWidget(catalog)
        dialog.exec()

    def _account_changed(self, *_args: object) -> None:
        self._clear()
        self._selected_task_changed()

    def _choose_bulk_accounts(self) -> None:
        from daedalus.desktop.account_scope import AccountSelectionDialog

        dialog = AccountSelectionDialog(
            self._all_account_metadata, self._bulk_account_ids, self,
            title="Choose automation accounts",
            explanation=(
                "View task status for any chosen accounts, including disabled accounts. "
                "Starting an automation is separate and requires explicit approval, "
                "at most 32 enabled accounts, and individual backend preflights."
            ),
        )
        if dialog.exec() == dialog.Accepted:
            self._bulk_account_ids = dialog.selected_ids()
            self._update_bulk_buttons()

    def _update_bulk_buttons(self) -> None:
        count = len(self._bulk_account_ids)
        self.view_all_button.setEnabled(bool(self._status_account_ids))
        self.view_selected_button.setEnabled(bool(count))
        self.choose_bulk_button.setEnabled(bool(self._status_account_ids))
        self.view_selected_button.setText(f"View selected ({count})")
        self.start_selected_button.setText(f"Start for selected ({count})…")
        ineligible = [aid for aid in self._bulk_account_ids
                      if aid not in self._account_ids]
        can_start = bool(count) and count <= 32 and not ineligible
        self.start_selected_button.setEnabled(
            self._dispatch_enabled and can_start and bool(self._task_names)
        )
        if count > 32:
            self.bulk_note.setText(
                "View status for any number of accounts. To start tasks, "
                "choose at most 32 accounts and review each one."
            )
        elif ineligible:
            self.bulk_note.setText(
                "Status viewing includes disabled accounts. To start tasks, "
                "select enabled accounts only."
            )
        else:
            self.bulk_note.setText(
                "Multi-account starts require approval and an independent preflight "
                "for each account. A blocked account stops the batch."
            )

    def _refresh_all(self) -> None:
        if self._status_account_ids:
            self._show_section(3)
            self.multi_summary.setText(
                f"Checking tasks across all {len(self._status_account_ids)} accounts…"
            )
            self.batch_status_requested.emit(list(self._status_account_ids))

    def _refresh_selected(self) -> None:
        if self._bulk_account_ids:
            self._show_section(3)
            self.multi_summary.setText(
                f"Checking tasks for {len(self._bulk_account_ids)} selected accounts…"
            )
            self.batch_status_requested.emit(list(self._bulk_account_ids))

    def set_batch_status(self, rows: list[dict[str, object]]) -> None:
        # Read-only, from each backend account's independently authorized status.
        data = []
        error_count = 0
        for row in rows:
            if not isinstance(row, dict) or row.get("account_id") not in self._status_account_ids:
                continue
            account = next(
                (a for a in self._all_account_metadata if a["id"] == row["account_id"]), {}
            )
            label = str(account.get("label") or account.get("player") or row["account_id"])
            if row.get("error"):
                error_count += 1
                data.append([label, "—", "—",
                             "Disabled · unavailable" if not account.get("enabled")
                             else "Unavailable"])
                continue
            tasks = row.get("engine_tasks")
            requests = row.get("requests")
            if not isinstance(tasks, list) or not isinstance(requests, list):
                error_count += 1
                data.append([label, "—", "—",
                             "Disabled · unavailable" if not account.get("enabled")
                             else "Unavailable"])
                continue
            running = sum(
                isinstance(item, dict) and item.get("status") == "running" for item in tasks
            )
            unresolved = sum(
                isinstance(item, dict)
                and item.get("status") in {"dispatching", "unconfirmed"}
                for item in requests
            )
            data.append([label, running, unresolved,
                         "Needs review" if unresolved else
                         "Disabled account" if not account.get("enabled") else
                         "Up to date"])
        _populate(self.multi_table, data)
        self.multi_summary.setText(
            f"{len(data)} accounts checked"
            + (f" · {error_count} unavailable — safe read-only retry available"
               if error_count else "")
        )

    def _start_selected(self) -> None:
        # Preserve current form's explicit approval; all accounts get independent
        # server preflight and separate UUIDs inside the off-thread API worker.
        if (not self._dispatch_enabled or not self._bulk_account_ids
                or len(self._bulk_account_ids) > 32
                or any(aid not in self._account_ids for aid in self._bulk_account_ids)
                or not self.confirm_box.isChecked() or not self.selected_task_name()):
            return
        if self._form_dirty and self._advanced_visible:
            QMessageBox.warning(
                self, "Review changed settings",
                "Build JSON from the guided form or hide Advanced before starting."
            )
            return
        try:
            if self._advanced_visible:
                config = json.loads(self.config_editor.toPlainText())
                if not isinstance(config, dict):
                    raise ValueError("Advanced configuration must be a JSON object")
            else:
                config = self._form_config()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Invalid automation settings", str(exc))
            return
        task = self.selected_task_name()
        names = [
            str(a.get("label") or a.get("player") or a["id"])
            for a in self._account_metadata if a["id"] in self._bulk_account_ids
        ]
        summary = ", ".join(names[:12])
        if len(names) > 12:
            summary += f" and {len(names) - 12} more"
        answer = QMessageBox.question(
            self, "Review multi-account automation",
            f"Start {_friendly_task(task)} for {len(names)} selected accounts?\n\n"
            f"Accounts: {summary}\n\n"
            f"Settings: {configuration_summary(config)}\n\n"
            "Daedalus checks every account's readiness before starting any. "
            "Each account gets its own validated request; on an uncertain result "
            "dispatch stops without retrying. Game state can change.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.batch_launch_requested.emit(list(self._bulk_account_ids), task, config)
            self.confirm_box.setChecked(False)

    def set_batch_launch_result(self, data: dict[str, object]) -> None:
        self._show_section(3)
        submitted = data.get("submitted", [])
        blocked = data.get("blocked", [])
        halted = data.get("halted")
        if blocked:
            details = ", ".join(
                str(x.get("account_id") or "") for x in blocked[:8]
            )
            self.multi_summary.setText(
                f"No tasks started: accounts not ready ({details}). "
                "Review prerequisites before trying again."
            )
        elif halted:
            self.multi_summary.setText(
                f"{len(submitted)} accounts received a task receipt; "
                f"dispatch stopped at {halted.get('account_id')}. "
                "Check this account's request ledger before any further action; "
                "Daedalus will not retry automatically."
            )
        else:
            self.multi_summary.setText(
                f"Start receipts received for {len(submitted)} selected accounts. "
                "View all statuses to verify their current state."
            )

    def set_capabilities(self, operations: list[dict[str, object]], enabled: bool) -> None:
        self._dispatch_enabled = enabled
        self._catalog_operations = [dict(item) for item in operations if isinstance(item, dict)]
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
            self._config_fields_by_task[str(name)] = present_fields(str(name), fields)
        self.status_label.setText(
            "Choose an automation. Daedalus checks prerequisites before enabling Start."
            if enabled and self._all_task_names else
            "No background automations for this workflow."
            if enabled and self._workflow is not None else
            "Task control disabled on this backend; use a privately enabled server."
        )
        self._clear()
        self._filter_tasks()
        self._update_bulk_buttons()

    def _filter_tasks(self, *_args: object) -> None:
        old = self.selected_task_name()
        category = self.category_combo.currentText() or _CATEGORIES[0]
        search = self.search_input.text().strip().casefold()
        self._task_names = [name for name in self._all_task_names
            if (category == "All automations" or _category(name) == category)
            and (self._template_filter is None
                 or name in _TEMPLATE_TASKS[self._template_filter])
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
        self._update_bulk_buttons()

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        for widget in (
            self.advanced_note, self.config_editor, self.build_json_button,
            self.import_config_button,
        ):
            widget.setVisible(self._advanced_visible)
        self.advanced_toggle.setText(
            "Hide advanced JSON options" if self._advanced_visible
            else "Show advanced JSON options"
        )
        if self._advanced_visible:
            self._build_config_from_form()

    def _import_advanced_config(self) -> None:
        """User-directed bounded JSON import, never a system or account-file search."""
        name = self.selected_task_name()
        if not name:
            return
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self, "Import reviewed IkaBot automation settings", "", "JSON files (*.json)"
        )
        if not filename:
            return
        try:
            source = Path(filename)
            if source.stat().st_size > 16384:
                raise ValueError("Configuration file exceeds the 16 KiB safety limit")
            raw = source.read_text(encoding="utf-8")
            config = json.loads(raw, parse_constant=lambda _x: (
                _ for _ in ()
            ).throw(ValueError("Invalid nonfinite value")))
            if not isinstance(config, dict):
                raise TypeError("Configuration must be one JSON object")
            allowed = {str(field["name"])
                       for field in self._config_fields_by_task.get(name, [])}
            if not allowed or not all(isinstance(key, str) and key in allowed
                                      for key in config):
                raise ValueError("File has parameters not registered for this automation")
            if len(json.dumps(config, ensure_ascii=False, allow_nan=False).encode()) > 16384:
                raise ValueError("Configuration exceeds the task size limit")
        except (OSError, UnicodeError, ValueError, TypeError):
            QMessageBox.warning(
                self, "Configuration not imported",
                "Choose a valid JSON object under 16 KiB containing only "
                "this automation's registered parameter names. "
                "No account operation was started.",
            )
            return
        if not self._advanced_visible:
            self._advanced_visible = True
            for widget in (
                self.advanced_note, self.config_editor, self.build_json_button,
                self.import_config_button,
            ):
                widget.show()
            self.advanced_toggle.setText("Hide advanced JSON options")
        self.config_editor.setPlainText(
            json.dumps(config, ensure_ascii=False, indent=2)
        )
        self._form_dirty = False
        self.confirm_box.setChecked(False)
        QMessageBox.information(
            self, "Configuration loaded",
            "Review the advanced settings and confirm the correct account "
            "before starting anything. The backend will still validate the task.",
        )

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
            f"{_friendly_task(name)}  ·  {_category(name)}. {task_explanation(name)}"
            if name else "No automations match this filter."
        )
        expert_needed = expert_configuration_needed(fields)
        self.expert_note.setVisible(expert_needed)
        if expert_needed:
            self.expert_note.setText(
                "This operation needs a prepared engine plan (for example, a "
                "validated city, building queue or route). Daedalus cannot "
                "invent those values. Use Advanced to import an existing "
                "configuration or supply reviewed fields."
            )
        for field in fields:
            key = str(field["name"])
            kind = str(field["type"])
            default = field.get("default")
            label = (
                str(field.get("label") or key.replace("_", " ").capitalize())
                + (" *" if field["required"] else "")
            )
            if kind == "boolean":
                widget = CheckBox("Enabled")
                widget.setChecked(default is True)
                widget.stateChanged.connect(self._mark_form_dirty)
            elif kind == "integer" and (
                (type(default) is int and -1_000_000 <= default <= 1_000_000)
                or field.get("explicit_input") is True
            ):
                widget = SpinBox()
                minimum = int(field.get("minimum", -1_000_000))
                maximum = int(field.get("maximum", 1_000_000))
                if field.get("explicit_input") is True:
                    # Native spinner with a *missing* sentinel rather than an
                    # invented game setting. The sentinel cannot be dispatched.
                    widget.setRange(minimum - 1, maximum)
                    widget.setSpecialValueText("Choose a value")
                    widget.setValue(minimum - 1)
                else:
                    widget.setRange(minimum, maximum)
                    widget.setValue(default)
                if key == "minutes" and name == "alertAttacks":
                    widget.setMinimum(3)
                    widget.setSuffix(" min")
                elif field.get("suffix"):
                    widget.setSuffix(str(field["suffix"]))
                widget.valueChanged.connect(self._mark_form_dirty)
            elif kind == "number" and type(default) in (int, float) and -1_000_000 <= default <= 1_000_000:
                widget = DoubleSpinBox()
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
            style_form_input(widget, label, str(field.get("help") or ""))
            self.parameter_layout.addRow(label, widget)
            self._form_inputs[key] = widget
        self.parameter_scroll.setVisible(bool(fields))
        if fields:
            # Match the form to its contents instead of leaving a large empty
            # box under single-parameter workflows.
            self.parameter_scroll.setFixedHeight(
                min(315, max(72, len(fields) * 44 + 24))
            )
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
                value = widget.value()
                if (field.get("explicit_input") is True
                        and value < int(field.get("minimum", 0))):
                    raise ValueError(f"Choose a value for {key} before starting")
                config[key] = value
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
        if (name == "alertLowWine" and config.get("auto_transfer") is True
                and (type(config.get("transfer_amount")) is not int
                     or config["transfer_amount"] < 1)):
            raise ValueError(
                "Set a positive transfer amount before enabling automatic wine transfers"
            )
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
        self._update_bulk_buttons()

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
        params = configuration_summary(config)
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
