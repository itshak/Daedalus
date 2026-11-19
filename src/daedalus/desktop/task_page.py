"""Native Fluent task controls; all game mutations require explicit approval.

The page prepares JSON and sends it only to the Daedalus authenticated API,
not Gameforge. The backend and engine independently validate and own the task.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
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

from daedalus.desktop.design_system import FEATURE_ICONS, PageHeading, style_form_input
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
    cities_requested = Signal(str)
    buildings_requested = Signal(str, int)

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
        self._selection_generation = 0
        self._unresolved = False
        self._advanced_visible = False
        self._config_fields_by_task: dict[str, list[dict[str, object]]] = {}
        self._catalog_operations: list[dict[str, object]] = []
        self._form_inputs: dict[str, LineEdit | CheckBox | ComboBox | QSpinBox | QDoubleSpinBox | QListWidget] = {}
        self._form_dirty = False
        self._reviewed = False
        self._pending_launch = False
        self._bulk_account_ids: list[str] = []
        self._account_metadata: list[dict[str, object]] = []
        self._all_account_metadata: list[dict[str, object]] = []
        self._status_account_ids: list[str] = []
        # Authenticated, account-bound read-only city options; never invent IDs.
        self._cities_by_account: dict[str, list[dict[str, object]]] = {}
        self._buildings_scope: tuple[str, int] | None = None
        self._building_rows: list[dict[str, object]] = []

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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        title = (
            "Wine automation" if workflow == "wine" else
            "Construction automation" if workflow == "construction" else
            "Automations"
        )
        layout.addWidget(PageHeading(
            title, "Choose an automation, review its settings, then start."
        ))
        self.status_label = CaptionLabel(
            "Connect to your backend to configure an automation."
        )
        layout.addWidget(self.status_label)

        template_row = QHBoxLayout()
        self.wine_template_button = PushButton("Wine", icon=FEATURE_ICONS["wine"])
        self.wine_template_button.setToolTip("Find tavern and low-wine automations")
        self.wine_template_button.clicked.connect(lambda: self.select_workflow("wine"))
        template_row.addWidget(self.wine_template_button)
        self.construction_template_button = PushButton(
            "Construction", icon=FEATURE_ICONS["construction"]
        )
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
        self.catalog_button = PushButton("Explore catalog…", icon=FEATURE_ICONS["catalog"])
        self.catalog_button.clicked.connect(self._open_catalog)
        template_row.addWidget(self.catalog_button)
        template_row.addStretch(1)
        if workflow is None:
            # Category tabs below replace the duplicated template toolbar.
            pass
        else:
            for button in (
                self.wine_template_button, self.construction_template_button,
                self.all_templates_button, self.catalog_button,
            ):
                button.setParent(self)
                button.hide()

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
        self.view_all_button.setToolTip("Read-only task status for every configured account, including disabled accounts")
        self.view_all_button.clicked.connect(self._refresh_all)
        scope_row.addWidget(self.view_all_button)
        self.view_selected_button = PushButton("View selected statuses")
        self.view_selected_button.clicked.connect(self._refresh_selected)
        scope_row.addWidget(self.view_selected_button)
        scope_row.addStretch(1)
        layout.addLayout(scope_row)

        self.category_combo = ComboBox(self)
        self.category_combo.addItems(list(_CATEGORIES))
        self.category_combo.currentIndexChanged.connect(self._filter_tasks)
        self.group_tabs = Pivot(self)
        self.group_tabs.setAccessibleName("Automation categories")
        for index, category in enumerate(_CATEGORIES):
            self.group_tabs.addItem(
                routeKey=f"group-{index}", text=category,
                onClick=lambda index=index: self.category_combo.setCurrentIndex(index),
            )
        self.group_tabs.setCurrentItem("group-0")
        layout.addWidget(self.group_tabs)
        filter_row = QHBoxLayout()
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("Search automations")
        self.search_input.textChanged.connect(self._filter_tasks)
        filter_row.addWidget(self.search_input, 1)
        layout.addLayout(filter_row)

        # Discover is a task gallery, not an unlabelled engine-name dropdown.
        # These are read-only selection cards; only the separate, reviewed
        # Start action can contact the backend with a game mutation.
        self.browse_button = PushButton("Browse actions ▾")
        self.browse_button.setToolTip("Show or hide available automation choices")
        self._gallery_open = False
        self.browse_button.clicked.connect(self._toggle_gallery)
        layout.addWidget(self.browse_button)
        self.discovery_scroll = QScrollArea(self)
        self.discovery_scroll.setWidgetResizable(True)
        self.discovery_scroll.setFrameShape(QScrollArea.NoFrame)
        self.discovery_scroll.setMinimumHeight(100)
        self.discovery_scroll.setMaximumHeight(185)
        self.discovery_container = QWidget(self.discovery_scroll)
        self.discovery_layout = QGridLayout(self.discovery_container)
        self.discovery_layout.setContentsMargins(2, 2, 10, 2)
        self.discovery_layout.setSpacing(10)
        self.discovery_scroll.setWidget(self.discovery_container)
        layout.addWidget(self.discovery_scroll)
        self.discovery_note = CaptionLabel("")
        self.discovery_note.setWordWrap(True)
        self.discovery_note.hide()
        self.discovery_scroll.hide()
        layout.addWidget(SubtitleLabel("Configure"))

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


        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setMinimumHeight(110)
        self.parameter_scroll.setMaximumHeight(290)
        self.parameter_container = QWidget()
        self.parameter_layout = QFormLayout(self.parameter_container)
        self.parameter_scroll.setWidget(self.parameter_container)
        layout.addWidget(self.parameter_scroll)
        # Source-backed construction inventory: never a fabricated plan.
        self.building_header = SubtitleLabel("Buildings in this city")
        layout.addWidget(self.building_header)
        self.building_table = _table([
            "Choose", "Building", "Slot", "Current level", "Target level", "Status"
        ])
        self.building_table.setAccessibleName("Read-only verified city building levels and draft targets")
        self.building_table.setMinimumHeight(180)
        self.building_table.setMaximumHeight(320)
        layout.addWidget(self.building_table)
        self.building_note = CaptionLabel(
            "Choose a city to inspect its actual buildings. Upgrade targets are drafts; "
            "starting requires an upstream-validated construction plan, not raw values."
        )
        self.building_note.setWordWrap(True)
        layout.addWidget(self.building_note)
        self.building_header.hide()
        self.building_table.hide()
        self.building_note.hide()
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
        self.confirm_box.stateChanged.connect(self._approval_changed)
        launch_row.addWidget(self.confirm_box)
        launch_row.addStretch(1)
        self.start_button = PrimaryPushButton("Review and start…")
        self.start_button.setAccessibleDescription(
            "Review the account, task, and settings in a separate confirmation dialog."
        )
        self.start_button.clicked.connect(self._start)
        launch_row.addWidget(self.start_button)
        layout.addLayout(launch_row)

        batch_row = QHBoxLayout()
        self.bulk_note = CaptionLabel(
            "Multi-account actions require a separate review. Each selected account is "
            "checked independently; dispatch stops if any account is not ready."
        )
        self.bulk_note.setWordWrap(True)
        self.bulk_note.hide()
        batch_row.addStretch(1)
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
        running_scope = QHBoxLayout()
        running_scope.addWidget(BodyLabel("Selected account"))
        self.running_account_combo = ComboBox()
        self.running_account_combo.setAccessibleName("Account for running automations")
        self.running_account_combo.currentIndexChanged.connect(
            self.account_combo.setCurrentIndex
        )
        running_scope.addWidget(self.running_account_combo, 1)
        self.running_all_button = PushButton("All account statuses")
        self.running_all_button.clicked.connect(self._refresh_all)
        running_scope.addWidget(self.running_all_button)
        layout.addLayout(running_scope)
        self.running_refresh_button = PushButton("Refresh selected account")
        self.running_refresh_button.clicked.connect(self._refresh)
        layout.addWidget(self.running_refresh_button)
        self.task_table = _table(["Automation", "Status", "Started", "Scope"])
        self.task_table.setAccessibleName("Daedalus-managed automations for the chosen account")
        self.task_table.itemSelectionChanged.connect(self._set_controls)
        layout.addWidget(self.task_table, 2)

        stop_row = QHBoxLayout()
        self.stop_button = PushButton("Stop selected task")
        self.stop_button.clicked.connect(self._stop)
        stop_row.addWidget(self.stop_button)
        self.running_details_button = PushButton("Task details…")
        self.running_details_button.clicked.connect(self._show_running_details)
        stop_row.addWidget(self.running_details_button)
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
        history_scope = QHBoxLayout()
        history_scope.addWidget(BodyLabel("Selected account"))
        self.history_account_combo = ComboBox()
        self.history_account_combo.setAccessibleName("Account for request history")
        self.history_account_combo.currentIndexChanged.connect(
            self.account_combo.setCurrentIndex
        )
        history_scope.addWidget(self.history_account_combo, 1)
        self.history_all_button = PushButton("All account statuses")
        self.history_all_button.clicked.connect(self._refresh_all)
        history_scope.addWidget(self.history_all_button)
        layout.addLayout(history_scope)
        self.history_refresh_button = PushButton("Refresh selected account")
        self.history_refresh_button.clicked.connect(self._refresh)
        layout.addWidget(self.history_refresh_button)
        self.request_table = _table(["Automation", "Status", "Managed task", "Review"])
        self.request_table.setAccessibleName("Account-scoped automation request history")
        self.request_table.itemSelectionChanged.connect(self._set_controls)
        layout.addWidget(self.request_table, 1)
        self.request_details_button = PushButton("Request details…")
        self.request_details_button.clicked.connect(self._show_request_details)
        layout.addWidget(self.request_details_button)
        self.reconcile_button = PushButton("Acknowledge manually verified request…")
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
        self.multi_summary.hide()
        self.multi_table = _table(["Account", "Running tasks", "Needs review", "Status"])
        self.multi_table.setMaximumHeight(185)
        layout.addWidget(self.multi_table)
        layout.addStretch(1)

        # The capability catalog belongs to this same workspace. It is not
        # a separate operations window with a second selection lifecycle.
        from daedalus.desktop.pages import OperationsPage

        self.catalog_panel = OperationsPage(self.stack)
        self.stack.addWidget(self.catalog_panel)
        self.pivot.addItem(
            routeKey="catalog", text="Catalog",
            onClick=lambda: self._show_section(4),
        )
        self.catalog_panel.configure_requested.connect(self.select_task)
        self._show_section(0)
        self._set_controls()

    def _toggle_gallery(self) -> None:
        self._gallery_open = not self._gallery_open
        self.discovery_scroll.setVisible(self._gallery_open and bool(self._task_names))
        self.discovery_note.setVisible(self._gallery_open)
        self.browse_button.setText(
            "Hide automation gallery" if self._gallery_open
            else "Browse automation gallery ▾"
        )

    def _show_section(self, index: int) -> None:
        """Fluent pivot for discover/configure, running, history and multi-account views."""
        keys = ("configure", "running", "history", "accounts", "catalog")
        if not 0 <= index < len(keys):
            raise ValueError("Unknown automation section")
        self.stack.setCurrentIndex(index)
        self.pivot.setCurrentItem(keys[index])

    def selected_account_id(self) -> str | None:
        idx = self.account_combo.currentIndex()
        return self._account_ids[idx] if 0 <= idx < len(self._account_ids) else None

    def reset_backend_context(self) -> None:
        """Discard account IDs, task drafts and reviews after backend origin changes."""
        self._selection_generation += 1
        self._pending_launch = False
        self._prereq_ready = None
        self._unresolved = False
        self._bulk_account_ids.clear()
        self._template_filter = None
        self.set_accounts([])
        self.set_capabilities([], False)
        self.multi_table.setRowCount(0)
        self.multi_summary.setText(
            "Connect to view authoritative task status for configured accounts."
        )
        self._show_section(0)

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        previous = self.selected_account_id()
        # Read-only "All accounts" includes disabled accounts; only enabled
        # accounts can be offered as candidates for task mutation.
        self._all_account_metadata = [
            dict(a) for a in accounts
            if isinstance(a.get("id"), str) and a["id"]
        ]
        self._status_account_ids = [str(a["id"]) for a in self._all_account_metadata]
        # A metadata refresh may represent a changed session, so discard city caches.
        self._cities_by_account.clear()
        self._buildings_scope = None
        self._building_rows = []
        self.building_table.setRowCount(0)
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
        for combo in (self.running_account_combo, self.history_account_combo):
            with QSignalBlocker(combo):
                combo.clear()
                for account in self._account_metadata:
                    combo.addItem(str(
                        account.get("label") or account.get("player") or account["id"]
                    ))
                combo.setCurrentIndex(self.account_combo.currentIndex())
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
        self._invalidate_review()
        if workflow not in {"all", "wine", "construction"}:
            raise ValueError("Unsupported automation template")
        self._template_filter = None if workflow == "all" else workflow
        self.category_combo.setCurrentIndex(0)
        self.search_input.clear()
        self._filter_tasks()

    def _open_catalog(self) -> None:
        """Show interactive-only and dispatchable operations in the same workspace."""
        self._show_section(4)

    def _account_changed(self, *_args: object) -> None:
        for combo in (self.running_account_combo, self.history_account_combo):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(self.account_combo.currentIndex())
        self._clear()
        self._invalidate_review()
        self._selected_task_changed()

    def _populate_city_picker(self, widget: ComboBox) -> None:
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        with QSignalBlocker(widget):
            widget.clear()
            widget.addItem("Choose a city…" if cities else "Cities unavailable — refresh to load")
            for city in cities:
                suffix = str(city.get("coords") or "")
                widget.addItem(f"{city['name']} ({suffix})" if suffix else str(city["name"]))
            # Never silently choose a city for a state-changing task.
            widget.setCurrentIndex(0)

    def _populate_city_list(self, widget: QListWidget) -> None:
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        with QSignalBlocker(widget):
            widget.clear()
            for city in cities:
                name = str(city["name"])
                coords = str(city.get("coords") or "")
                entry = QListWidgetItem(f"{name} ({coords})" if coords else name)
                entry.setData(Qt.UserRole, city["id"])
                entry.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                entry.setCheckState(Qt.Unchecked)
                widget.addItem(entry)
        widget.setToolTip(
            "Leave every city unchecked to use engine defaults" if cities else
            "City list unavailable — connect the account and refresh"
        )

    def set_cities(self, account_id: str, cities: list[dict[str, object]]) -> None:
        if account_id not in self._account_ids:
            return
        verified = []
        for city in cities[:500]:
            if (isinstance(city, dict) and type(city.get("id")) is int
                    and city["id"] > 0 and isinstance(city.get("name"), str)
                    and city["name"]):
                verified.append({
                    "id": city["id"], "name": city["name"][:120],
                    "coords": str(city.get("coords") or "")[:40],
                })
        self._cities_by_account[account_id] = verified
        if account_id == self.selected_account_id():
            picker = self._form_inputs.get("city_id")
            if self.selected_task_name() == "constructionList" and isinstance(picker, ComboBox):
                self._populate_city_picker(picker)
                self._construction_city_changed()
            for input_widget in self._form_inputs.values():
                if isinstance(input_widget, QListWidget):
                    self._populate_city_list(input_widget)
                    self._invalidate_review()

    def _selected_construction_city(self) -> int | None:
        if self.selected_task_name() != "constructionList":
            return None
        picker = self._form_inputs.get("city_id")
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
        return cities[index - 1]["id"] if 1 <= index <= len(cities) else None

    def _construction_city_changed(self, *_args: object) -> None:
        self._mark_form_dirty()
        self._building_rows = []
        self._buildings_scope = None
        self.building_table.setRowCount(0)
        city_id = self._selected_construction_city()
        account_id = self.selected_account_id()
        if account_id and city_id:
            self.building_note.setText("Loading real building levels for the chosen city…")
            self.buildings_requested.emit(account_id, city_id)
        else:
            self.building_note.setText("Choose an actual city to inspect its buildings.")

    def set_buildings(self, account_id: str, city_id: int,
                      buildings: list[dict[str, object]]) -> None:
        if account_id != self.selected_account_id() or city_id != self._selected_construction_city():
            return  # late result from a different account/city
        self._buildings_scope = (account_id, city_id)
        self._building_rows = [dict(item) for item in buildings]
        self.building_table.setRowCount(len(self._building_rows))
        for row_index, item in enumerate(self._building_rows):
            position, level = item["position"], item["level"]
            choice = QTableWidgetItem("")
            choice.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            choice.setCheckState(Qt.Unchecked)
            choice.setData(Qt.UserRole, position)
            self.building_table.setItem(row_index, 0, choice)
            for col, value in ((1, item["name"]), (2, position), (3, level),
                               (5, "Upgrading" if item["busy"] else
                                "Eligible" if item["can_upgrade"] else "Not available")):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.building_table.setItem(row_index, col, cell)
            target = QSpinBox(self.building_table)
            target.setAccessibleName(f"Draft target level for {item['name']}")
            target.setRange(level, 150)
            target.setValue(level)
            target.setEnabled(item["can_upgrade"] and not item["busy"])
            target.valueChanged.connect(self._mark_form_dirty)
            self.building_table.setCellWidget(row_index, 4, target)
            choice.setFlags(choice.flags() if item["can_upgrade"] and not item["busy"]
                            else Qt.ItemIsEnabled)
        self.building_note.setText(
            f"{len(self._building_rows)} actual buildings loaded. Select upgrade targets above. "
            "Cost, shipment and queue preparation are not yet provided by the engine; "
            "these draft selections cannot be started from this table. "
            "Experts may import a separately validated construction plan."
        )
        self._invalidate_review()

    def set_buildings_unavailable(self, account_id: str, city_id: int) -> None:
        if account_id == self.selected_account_id() and city_id == self._selected_construction_city():
            self._buildings_scope = None
            self._building_rows.clear()
            self.building_table.setRowCount(0)
            self.building_note.setText(
                "Building information is unavailable for this city. "
                "No upgrade assumptions were made; reconnect the account and refresh."
            )
            self._invalidate_review()

    def set_cities_unavailable(self, account_id: str) -> None:
        self._cities_by_account.pop(account_id, None)
        if account_id == self.selected_account_id():
            picker = self._form_inputs.get("city_id")
            if self.selected_task_name() == "constructionList" and isinstance(picker, ComboBox):
                self._populate_city_picker(picker)
                self._construction_city_changed()
            for input_widget in self._form_inputs.values():
                if isinstance(input_widget, QListWidget):
                    self._populate_city_list(input_widget)
                    self._invalidate_review()

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
            self._invalidate_review()
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
        # One city's construction plan cannot be dispatched against other account IDs.
        if self.selected_task_name() == "constructionList":
            can_start = False
        self.start_selected_button.setEnabled(
            self._dispatch_enabled and can_start
            and not self._pending_launch and bool(self._task_names)
        )
        if self.selected_task_name() == "constructionList":
            self.bulk_note.setText(
                "Construction plans are city- and account-specific. Configure each account "
                "separately; copying one city's building plan to another is unsafe."
            )
        elif count > 32:
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
        if (not self._dispatch_enabled or self._pending_launch
                or self.selected_task_name() == "constructionList"
                or not self._bulk_account_ids or len(self._bulk_account_ids) > 32
                or any(aid not in self._account_ids for aid in self._bulk_account_ids)
                or not self.selected_task_name()):
            return
        if not self._reviewed or not self.confirm_box.isChecked():
            # Invalid consent should be contextual, not an unexpected modal.
            # A modal also traps offscreen/keyboard-only users in this path.
            self.bulk_note.setText(
                "Review this automation and check the authorization box above "
                "before starting tasks for selected accounts."
            )
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
        # Display the *entire* approved scope, including worlds. Never hide
        # 20 accounts behind "and more" before an irreversible group action.
        names = [
            self._account_description(aid) for aid in self._bulk_account_ids
        ]
        summary = "\n".join(f"• {name}" for name in names)
        answer = QMessageBox.question(
            self, "Review multi-account automation",
            f"Start {_friendly_task(task)} for {len(names)} selected accounts?\n\n"
            f"Accounts (review all):\n{summary}\n\n"
            f"Settings: {configuration_summary(config)}\n\n"
            "Daedalus checks every account's readiness before starting any. "
            "Each account gets its own validated request; on an uncertain result "
            "dispatch stops without retrying. Game state can change.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._pending_launch = True
            self.batch_launch_requested.emit(list(self._bulk_account_ids), task, config)
            self._invalidate_review()

    def set_batch_launch_result(self, data: dict[str, object]) -> None:
        self.finish_launch()
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
        self.catalog_panel.set_operations(self._catalog_operations)
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
                    # Accept only metadata supplied by the authenticated
                    # backend, never guess valid city IDs or enum choices.
                    choices = field.get("choices")
                    safe_choices = (
                        list(choices) if isinstance(choices, (tuple, list))
                        and 0 < len(choices) <= 100
                        and all(type(choice) in (str, int, float, bool)
                                and len(str(choice)) <= 120 for choice in choices)
                        else None
                    )
                    fields.append({
                        "name": key, "type": field["type"],
                        "required": field.get("required") is True,
                        **({"default": field["default"]} if "default" in field else {}),
                        **({"choices": safe_choices} if safe_choices is not None else {}),
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
        self.group_tabs.setCurrentItem(f"group-{self.category_combo.currentIndex()}")
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
        self._render_discovery()
        self._update_bulk_buttons()

    def _render_discovery(self) -> None:
        """Build a small Fluent gallery from the actual advertised registry."""
        while self.discovery_layout.count():
            item = self.discovery_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        shown = self._task_names[:24]
        for index, name in enumerate(shown):
            card = CardWidget(self.discovery_container)
            card.setMinimumHeight(88)
            panel = QVBoxLayout(card)
            panel.setContentsMargins(13, 10, 13, 10)
            panel.setSpacing(4)
            heading = BodyLabel(_friendly_task(name))
            heading.setAccessibleName(_friendly_task(name))
            panel.addWidget(heading)
            detail = CaptionLabel(
                f"{_category(name)} · {task_explanation(name)}"
            )
            detail.setWordWrap(True)
            panel.addWidget(detail)
            permission_note = CaptionLabel(
                "Review and preflight required" if self._dispatch_enabled
                else "Read-only: backend task starts unavailable"
            )
            permission_note.setWordWrap(True)
            card.setToolTip(permission_note.text())
            panel.addStretch(1)
            category = _category(name)
            feature = (
                "alerts" if category == "Alerts & monitoring"
                else "resources" if category == "Resources & trade"
                else "construction" if category == "City management"
                else "catalog"
            )
            action = PushButton("Configure", icon=FEATURE_ICONS[feature])
            action.setAccessibleName(f"Configure {_friendly_task(name)}")
            action.setToolTip(
                "Choose this automation and inspect its settings; does not start it"
            )
            action.clicked.connect(
                lambda _checked=False, task_name=name:
                self._select_discovered_task(task_name)
            )
            panel.addWidget(action)
            self.discovery_layout.addWidget(card, index // 2, index % 2)
        self.discovery_note.setText(
            "No matching background automations. Try another category or search."
            if not self._task_names else
            f"Showing 24 of {len(self._task_names)} matches. "
            "Use the Automation selector for the full list."
            if len(self._task_names) > 24 else
            f"{len(self._task_names)} background automations available for selection. "
            "Selection alone never starts an operation."
        )
        self.discovery_scroll.setVisible(self._gallery_open and bool(shown))
        self.discovery_note.setVisible(self._gallery_open)

    def _select_discovered_task(self, name: str) -> None:
        if name in self._task_names:
            self.task_combo.setCurrentIndex(self._task_names.index(name))
            self.parameter_scroll.ensureVisible(0, 0)
            self._show_section(0)

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
        if self._advanced_visible and self.selected_task_name() != "constructionList":
            self._build_config_from_form()
        self._set_controls()

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
        self._invalidate_review()
        QMessageBox.information(
            self, "Configuration loaded",
            "Review the advanced settings and confirm the correct account "
            "before starting anything. The backend will still validate the task.",
        )

    def _approval_changed(self, *_args: object) -> None:
        # Consent is scoped to the current account, task and configuration.
        self._reviewed = self.confirm_box.isChecked()
        self._set_controls()

    def _invalidate_review(self) -> None:
        self._reviewed = False
        self.confirm_box.blockSignals(True)
        try:
            self.confirm_box.setChecked(False)
        finally:
            self.confirm_box.blockSignals(False)
        self._set_controls()

    def _review_advanced_json(self) -> None:
        """Hand-edited JSON supersedes unbuilt form values deliberately."""
        self._form_dirty = False
        self._invalidate_review()

    def _mark_form_dirty(self, *_args: object) -> None:
        self._form_dirty = True
        self._invalidate_review()

    def _selected_task_changed(self, *_args: object) -> None:
        # A response from a prior visit to the same account/task must not
        # unlock the new draft merely because its identifiers match again.
        self._selection_generation += 1
        while self.parameter_layout.rowCount():
            self.parameter_layout.removeRow(0)
        self._form_inputs.clear()
        self._buildings_scope = None
        self._building_rows = []
        self.building_table.setRowCount(0)
        name = self.selected_task_name()
        show_buildings = name == "constructionList"
        self.building_header.setVisible(show_buildings)
        self.building_table.setVisible(show_buildings)
        self.building_note.setVisible(show_buildings)
        if show_buildings:
            self.building_note.setText("Choose a city to load its actual buildings.")
        fields = self._config_fields_by_task.get(name or "", [])
        self.task_description.setText(
            f"{_friendly_task(name)}  ·  {_category(name)}. {task_explanation(name)}"
            if name else "No automations match this filter."
        )
        self.task_description.setAccessibleName(
            f"Automation description: {_friendly_task(name)}" if name else
            "No matching automations"
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
            if name == "constructionList" and key not in {"city_id", "city_name"}:
                # Complex planner internals belong to an expert imported plan,
                # never to the normal construction interface.
                continue
            if name == "constructionList" and key == "city_name":
                # The paired, verified name comes from the selected city's read-only record.
                continue
            kind = str(field["type"])
            default = field.get("default")
            label = (
                str(field.get("label") or key.replace("_", " ").capitalize())
                + (" *" if field["required"] else "")
            )
            if kind == "city_list":
                widget = QListWidget(self)
                widget.setAccessibleName(f"Choose account cities for {label}")
                widget.setMinimumHeight(105)
                widget.setMaximumHeight(135)
                self._populate_city_list(widget)
                widget.itemChanged.connect(self._mark_form_dirty)
            elif name == "constructionList" and key == "city_id":
                widget = ComboBox()
                widget.setAccessibleName("Choose a real city for construction")
                self._populate_city_picker(widget)
                widget.currentIndexChanged.connect(self._construction_city_changed)
            elif field.get("choices"):
                widget = ComboBox()
                choices = field["choices"]
                for choice in choices:
                    widget.addItem(str(choice))
                if default in choices:
                    widget.setCurrentIndex(choices.index(default))
                else:
                    widget.setCurrentIndex(-1)
                widget.currentIndexChanged.connect(self._mark_form_dirty)
            elif kind == "boolean":
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
            help_text = str(field.get("help") or "")
            if kind == "json" and not field.get("choices"):
                help_text = (help_text + " " if help_text else "") + (
                    "Structured JSON input; do not guess game identifiers or required plan values."
                )
            style_form_input(widget, label, help_text)
            self.parameter_layout.addRow(label, widget)
            self._form_inputs[key] = widget
        self.parameter_scroll.setVisible(bool(fields))
        if fields:
            # Match the form to its contents instead of leaving a large empty
            # box under single-parameter workflows.
            visible_fields = [f for f in fields if name != "constructionList"
                              or f.get("name") == "city_id"]
            list_extra = 78 if any(field.get("type") == "city_list" for field in visible_fields) else 0
            self.parameter_scroll.setFixedHeight(
                min(315, max(72, len(visible_fields) * 44 + 24 + list_extra))
            )
        self.build_json_button.setEnabled(bool(fields))
        self._invalidate_review()
        self.config_editor.setPlainText("{}")
        self._form_dirty = False
        self._invalidate_review()
        self._prereq_ready = None
        self.prerequisite_label.setText(
            "Checking this account's task prerequisites…" if self._dispatch_enabled and name
            else "Select an automation to see whether it is ready."
        )
        self._set_controls()
        account_id = self.selected_account_id()
        if self._dispatch_enabled and account_id and name:
            self.preflight_requested.emit(account_id, name)
        if (account_id and account_id not in self._cities_by_account
                and (name == "constructionList"
                     or any(field.get("type") == "city_list" for field in fields))):
            self.cities_requested.emit(account_id)

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
            if name == "constructionList":
                # Only the live city choice is exposed in the guided editor.
                # Full engine-prepared construction internals are expert-only.
                continue
            kind = str(field["type"])
            widget = self._form_inputs[key]
            if isinstance(widget, QListWidget):
                chosen = [str(widget.item(i).data(Qt.UserRole))
                          for i in range(widget.count())
                          if widget.item(i).checkState() == Qt.Checked]
                if not chosen:
                    if field["required"]:
                        raise ValueError(f"Select at least one city for {key}")
                    continue
                if name == "distributeResources" and len(chosen) < 2:
                    raise ValueError("Choose at least two cities to distribute resources")
                config[key] = chosen
                continue
            if isinstance(widget, ComboBox):
                index = widget.currentIndex()
                choices = field["choices"]
                if index < 0 or index >= len(choices):
                    if field["required"]:
                        raise ValueError(f"Choose an option for {key}")
                    continue
                config[key] = choices[index]
                continue
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
        if name == "distributeResources" and config.get("mode") == "producers" and config.get("resource") == "wood":
            raise ValueError("Every city produces wood; choose the Even distribution policy")
        if name == "constructionList":
            picker = self._form_inputs.get("city_id")
            cities = self._cities_by_account.get(self.selected_account_id() or "", [])
            index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
            if index < 1 or index > len(cities):
                raise ValueError("Select a city loaded from this account before starting construction")
            config["city_id"] = cities[index - 1]["id"]
            config["city_name"] = cities[index - 1]["name"]
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
        self._invalidate_review()

    def set_tasks(self, data: dict[str, object]) -> None:
        task_rows = data.get("engine_tasks")
        request_rows = data.get("requests")
        tasks = [row for row in task_rows if isinstance(row, dict)] if isinstance(task_rows, list) else []
        requests = [row for row in request_rows if isinstance(row, dict)] if isinstance(request_rows, list) else []
        self._unresolved = any(
            row.get("status") in {"dispatching", "unconfirmed"} for row in requests
        )
        _populate(self.task_table, [
            [_friendly_task(str(task.get("task", ""))),
             str(task.get("status", "unknown")).replace("_", " ").capitalize(),
             task.get("started_at") or "Not provided", "Selected account"]
            for task in tasks
        ])
        for index, task in enumerate(tasks):
            # Raw UUID/PID are available in deliberate Details, not the
            # everyday table. Never use a process PID for Stop.
            self.task_table.item(index, 0).setData(Qt.UserRole, task)
        _populate(self.request_table, [
            [_friendly_task(str(row.get("task", ""))),
             str(row.get("status", "unknown")).replace("_", " ").capitalize(),
             "Tracked" if row.get("task_id") else "Not confirmed",
             "Needs reconciliation" if row.get("status") in
             {"dispatching", "unconfirmed"} else "Recorded"]
            for row in requests
        ])
        for index, row in enumerate(requests):
            self.request_table.item(index, 0).setData(Qt.UserRole, row)
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
            and not self._pending_launch
            # Live building selection alone is NOT a prepared engine plan.
            and (self.selected_task_name() != "constructionList" or self._advanced_visible)
        )
        # Status/history is read-only even on a backend that refuses dispatch.
        has_read_scope = bool(self._account_ids)
        self.refresh_button.setEnabled(has_read_scope)
        self.running_refresh_button.setEnabled(has_read_scope)
        self.history_refresh_button.setEnabled(has_read_scope)
        selected_task = self._selected_running_record()
        selected_request = self._selected_request_record()
        self.stop_button.setEnabled(
            enabled and isinstance(selected_task, dict)
            and selected_task.get("status") == "running"
            and bool(selected_task.get("task_id"))
        )
        self.running_details_button.setEnabled(isinstance(selected_task, dict))
        self.request_details_button.setEnabled(isinstance(selected_request, dict))
        self.reconcile_button.setEnabled(
            enabled and isinstance(selected_request, dict)
            and selected_request.get("status") in {"unconfirmed", "dispatching"}
            and bool(selected_request.get("request_id"))
        )
        self._update_bulk_buttons()

    def _refresh(self) -> None:
        account_id = self.selected_account_id()
        if account_id:
            self.refresh_requested.emit(account_id)

    def _account_description(self, account_id: str) -> str:
        record = next(
            (a for a in self._all_account_metadata if a["id"] == account_id),
            {},
        )
        label = str(record.get("label") or record.get("player") or account_id)
        world = str(record.get("world") or "world unspecified")
        return f"{label} · {world} (account {account_id})"

    def _start(self) -> None:
        account_id = self.selected_account_id()
        task = self.selected_task_name()
        if (not self._dispatch_enabled or account_id is None or task is None
                or self._pending_launch):
            return
        if self._unresolved:
            QMessageBox.warning(self, "Request needs review",
                "Resolve the earlier unconfirmed request before starting another task.")
            return
        if self._prereq_ready is not True:
            QMessageBox.warning(self, "Task not ready",
                "Check the setup message above. No game task was started.")
            return
        if not self._reviewed or not self.confirm_box.isChecked():
            QMessageBox.warning(self, "Confirm automation",
                "Check the authorization box before starting this automation.")
            return
        try:
            if self._advanced_visible:
                if self._form_dirty and task != "constructionList":
                    QMessageBox.warning(self, "Guided settings changed",
                        "Build JSON from guided settings or hide Advanced to use the form.")
                    return
                config = json.loads(self.config_editor.toPlainText())
                if not isinstance(config, dict):
                    raise ValueError("Advanced configuration must be a JSON object")
                if task == "constructionList":
                    city_id = self._selected_construction_city()
                    cities = self._cities_by_account.get(account_id, [])
                    matching = next((city for city in cities if city["id"] == city_id), None)
                    if (matching is None or config.get("city_id") != city_id
                            or config.get("city_name") != matching["name"]):
                        raise ValueError(
                            "Prepared construction plan must match the selected "
                            "authenticated city and its exact name"
                        )
                    if any(key not in config for key in (
                        "buildings", "shipments", "expand_overall", "wait_resources",
                        "construction_queue", "total_time",
                    )):
                        raise ValueError("Import a complete upstream-prepared construction plan")
            else:
                config = self._form_config()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Invalid automation settings", str(exc))
            return
        params = configuration_summary(config)
        answer = QMessageBox.question(
            self, "Review automation",
            f"Start {_friendly_task(task)} for "
            f"{self._account_description(account_id)}?\n\n"
            f"Settings: {params[:600]}\n\n"
            "This automation can change game state. "
            "You can stop a running task on this page.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._pending_launch = True
        self._set_controls()
        self.launch_requested.emit(account_id, task, config, str(uuid.uuid4()))
        self._invalidate_review()

    def finish_launch(self) -> None:
        """Restore controls only after the asynchronous response is handled."""
        self._pending_launch = False
        self._invalidate_review()

    def _selected_running_record(self) -> dict[str, object] | None:
        item = self.task_table.item(self.task_table.currentRow(), 0)
        data = item.data(Qt.UserRole) if item else None
        return data if isinstance(data, dict) else None

    def _selected_request_record(self) -> dict[str, object] | None:
        item = self.request_table.item(self.request_table.currentRow(), 0)
        data = item.data(Qt.UserRole) if item else None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _display_identifier(value: object) -> str:
        token = str(value or "")
        return token if re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", token) else "Unavailable"

    def _show_running_details(self) -> None:
        task = self._selected_running_record()
        if not task:
            return
        QMessageBox.information(
            self, "Managed task details",
            f"Automation: {_friendly_task(str(task.get('task', '')))}\n"
            f"State: {str(task.get('status', 'unknown'))[:32]}\n"
            f"Task ID: {self._display_identifier(task.get('task_id'))}\n"
            f"Process ID (diagnostic only): {self._display_identifier(task.get('pid'))}\n"
            "Only tasks managed by this backend can be stopped here.",
        )

    def _show_request_details(self) -> None:
        record = self._selected_request_record()
        if not record:
            return
        QMessageBox.information(
            self, "Request details",
            f"Automation: {_friendly_task(str(record.get('task', '')))}\n"
            f"State: {str(record.get('status', 'unknown'))[:32]}\n"
            f"Request ID: {self._display_identifier(record.get('request_id'))}\n"
            f"Managed task: {self._display_identifier(record.get('task_id'))}\n"
            "An unconfirmed request must be checked in the game and backend "
            "before acknowledgement. Daedalus will not retry it automatically.",
        )

    def _stop(self) -> None:
        account_id = self.selected_account_id()
        task = self._selected_running_record()
        if (account_id is None or not self._dispatch_enabled
                or not task or task.get("status") != "running"
                or not isinstance(task.get("task_id"), str)):
            return
        task_id = task["task_id"]
        answer = QMessageBox.question(
            self, "Stop IkaBot task",
            "Stop this Daedalus-managed background task? No unrelated task will be stopped.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.stop_requested.emit(account_id, task_id)

    def _reconcile(self) -> None:
        account_id = self.selected_account_id()
        record = self._selected_request_record()
        if (account_id is None or not self._dispatch_enabled or not record
                or record.get("status") not in {"unconfirmed", "dispatching"}
                or not isinstance(record.get("request_id"), str)):
            return
        answer = QMessageBox.question(
            self, "Manual game-state reconciliation",
            "Have you independently checked the task list and game state to confirm that "
            "this uncertain request will not be replayed? This action does not start a task.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.reconcile_requested.emit(account_id, record["request_id"])
