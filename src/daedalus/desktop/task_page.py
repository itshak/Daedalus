"""Native Fluent task controls; all game mutations require explicit approval.

The page prepares JSON and sends it only to the Daedalus authenticated API,
not Gameforge. The backend and engine independently validate and own the task.
"""

from __future__ import annotations

import json
import re
import time
import uuid

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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

from daedalus.account_display import account_player_name, account_player_names
from daedalus.desktop.design_system import FEATURE_ICONS, PageHeading, style_form_input
from daedalus.desktop.native_controls import (
    AcademyResearchEditor,
    BarbarianWavesEditor,
    DonationPoliciesEditor,
    ExternalDestinationEditor,
    MapAreaEditor,
    MarketOffersEditor,
    MiracleTempleEditor,
    OlympusShrineEditor,
    PiracyMissionsEditor,
    ResourceAmountsEditor,
    ResourceLimitsEditor,
    ShipmentRoutesEditor,
    TavernCitiesEditor,
    TrainableUnitsEditor,
    WorkshopUpgradesEditor,
)
from daedalus.desktop.pages import _populate, _table
from daedalus.desktop.task_presentation import (
    BATCH_TASKS,
    configuration_summary,
    expert_configuration_needed,
    present_fields,
    task_explanation,
)
from daedalus.reviewed_batch import BATCH_REVIEW_TASKS, validated_batch_entries
from daedalus.reviewed_operations import CITY_REVIEW_TASKS as ENGINE_REVIEW_TASKS
from daedalus.reviewed_operations import WORKER_TASKS, validated_worker_draft

CITY_REVIEW_TASKS = ENGINE_REVIEW_TASKS | {"sendResources"}

# Fixed, reviewed display labels. Unknown built-ins get a readable fallback,
# but dispatch always uses the engine's canonical original task name.
_TASK_LABELS = {
    "alertAttacks": "Attack alerts", "alertLowWine": "Low wine alerts",
    "searchForIslandSpaces": "Find island spaces", "tavernManager": "Tavern manager",
    "constructionList": "Construction planner", "research": "Research manager",
    "resourceTransportManager": "Resource transport manager",
    "consolidateResources": "Consolidate resources", "distributeResources": "Distribute resources",
    "sendResources": "Send resources", "buyResources": "Buy resources",
    "sellResources": "Sell resources", "donate": "Donate once", "donationBot": "Island donations",
    "trainArmy": "Train army", "attackBarbarians": "Attack barbarians",
    "autoBarbarians": "Barbarian automation", "activateMiracle": "Activate miracle",
    "activateShrine": "Activate shrine", "UpgradeUnits": "Upgrade units",
    "loginDaily": "Daily login", "dumpWorld": "Export world data",
    "vacationMode": "Activate vacation mode",
    "stationArmy": "Station troops or fleet",
    "constructBuilding": "Build new building",
    "reorganizeCityBuildings": "Copy city building layout",
    "modifyProduction": "Production workers", "modifyAcademyWorkers": "Academy scientists",
    "modifyTempleWorkers": "Temple priests",
    "webServer": "IkaBot web server", "autoPirate": "Piracy automation",
}
_CATEGORIES = ("All automations", "Alerts & monitoring", "Resources & trade",
               "City management", "Military & missions", "Advanced")
_TEMPLATE_TASKS = {
    "wine": {"alertLowWine", "tavernManager"},
    "construction": {"constructionList", "research"},
}
_TASK_CATEGORIES = {
    "Alerts & monitoring": {"alertAttacks", "alertLowWine", "searchForIslandSpaces", "testTelegramBot", "testDiscordBot"},
    "Resources & trade": {"buyResources", "sellResources", "sendResources",
                          "resourceTransportManager", "consolidateResources",
                          "distributeResources", "donationBot", "donate"},
    "City management": {"constructionList", "tavernManager", "research",
                        "loginDaily", "activateMiracle", "activateShrine",
                        "modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers", "reorganizeCityBuildings", "constructBuilding"},
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
    reviewed_batch_requested = Signal(object)
    cities_requested = Signal(str)
    island_destinations_requested = Signal(str, int, int, str)
    shipment_preview_requested = Signal(str, object, str)
    buildings_requested = Signal(str, int)
    construction_preview_requested = Signal(str, int, object)
    construction_supply_preview_requested = Signal(str, int, object, object)
    donation_preview_requested = Signal(str, object, str)
    worker_preview_requested = Signal(str, str, object, str)
    layout_preview_requested = Signal(str, object, str)
    station_preview_requested = Signal(str, object, str)
    training_preview_requested = Signal(str, object, str)
    grind_preview_requested = Signal(str, object, str)
    attack_inventory_requested = Signal(str, int, str)
    attack_preview_requested = Signal(str, object, str)
    vacation_preview_requested = Signal(str, int, str)
    build_options_requested = Signal(str, int, str)
    build_preview_requested = Signal(str, object, str)
    workshop_requested = Signal(str, int)
    trainable_units_requested = Signal(str, int, bool)
    market_quotes_requested = Signal(str, int, int, str)
    academies_requested = Signal(str)
    taverns_requested = Signal(str)
    miracles_requested = Signal(str)
    shrine_requested = Signal(str)
    pirate_fortresses_requested = Signal(str)

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
        self._config_fields_by_task: dict[str, list[dict[str, object]]] = {}
        self._catalog_operations: list[dict[str, object]] = []
        self._form_inputs: dict[str, QWidget] = {}
        self._form_dirty = False
        self._reviewed = False
        self._pending_launch = False
        self._review_queue = {}
        self._construction_ticket = None
        self._bulk_account_ids: list[str] = []
        self._account_metadata: list[dict[str, object]] = []
        self._all_account_metadata: list[dict[str, object]] = []
        self._account_names: dict[str, str] = {}
        self._status_account_ids: list[str] = []
        # Authenticated, account-bound read-only city options; never invent IDs.
        self._cities_by_account: dict[str, list[dict[str, object]]] = {}
        self._buildings_scope: tuple[str, int] | None = None
        self._construction_prepared: dict[str, object] | None = None
        self._construction_preview_ready = False
        self._pending_preview_key: tuple[object, ...] | None = None
        self._city_review_nonce: str | None = None
        self._city_review_plan: dict[str, object] | None = None
        self._city_review_expires = 0.0
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
        # A single vertical scroller owns the guided fields. Keep the exact
        # approval/launch actions visible in a compact, keyboard-reachable
        # footer instead of burying them beneath large live-data tables.
        configure_root = QWidget(self.stack)
        configure_layout = QVBoxLayout(configure_root)
        configure_layout.setContentsMargins(0, 0, 0, 0)
        configure_layout.setSpacing(0)
        configure_layout.addWidget(scroll, 1)
        self.stack.addWidget(configure_root)
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
            title, "Choose an account and action, then review and start."
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
        self.account_combo.setAccessibleName("Player account for automation")
        self.account_combo.currentIndexChanged.connect(self._account_changed)
        account_row.addWidget(self.account_combo, 1)
        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh)
        account_row.addWidget(self.refresh_button)

        scope_row = QHBoxLayout()
        self.choose_bulk_button = PushButton("Choose accounts…")
        self.choose_bulk_button.setAccessibleName("Choose accounts for automation actions")
        self.choose_bulk_button.clicked.connect(self._choose_bulk_accounts)
        account_row.addWidget(self.choose_bulk_button)
        layout.addLayout(account_row)
        self.view_all_button = PushButton("View all task statuses")
        self.view_all_button.setToolTip("Read-only task status for every configured account, including disabled accounts")
        self.view_all_button.clicked.connect(self._refresh_all)
        scope_row.addWidget(self.view_all_button)
        self.view_selected_button = PushButton("Refresh selected")
        self.view_selected_button.clicked.connect(self._refresh_selected)
        scope_row.addWidget(self.view_selected_button)
        self.overview_choose_button = PushButton("Choose accounts…")
        self.overview_choose_button.clicked.connect(self._choose_bulk_accounts)
        scope_row.addWidget(self.overview_choose_button)
        scope_row.addStretch(1)

        layout.addWidget(SubtitleLabel("Choose action"))
        self.category_combo = ComboBox(self)
        self.category_combo.hide()
        self.category_combo.addItems(list(_CATEGORIES))
        self.category_combo.currentIndexChanged.connect(self._filter_tasks)
        self.group_tabs = Pivot(self)
        self.group_tabs.setAccessibleName("Automation categories")
        for index, category in enumerate(("All", "Alerts", "Resources", "Cities", "Military", "Advanced")):
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

        # Discover is a task gallery, not an unlabelled engine-name dropdown.
        # These are read-only selection cards; only the separate, reviewed
        # Start action can contact the backend with a game mutation.
        self.browse_button = PushButton("Browse actions ▾")
        self.browse_button.setToolTip("Show or hide available automation choices")
        self._gallery_open = False
        self.browse_button.clicked.connect(self._toggle_gallery)
        filter_row.addWidget(self.browse_button)
        layout.addLayout(filter_row)
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
        layout.addWidget(self.discovery_note)

        task_row = QHBoxLayout()
        task_row.addWidget(BodyLabel("Action"))
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
        layout.addWidget(SubtitleLabel("Settings"))

        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setFrameShape(QScrollArea.NoFrame)
        self.parameter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.parameter_scroll.setMinimumHeight(72)
        self.parameter_scroll.setMaximumHeight(3200)
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
        self.building_table.itemChanged.connect(self._mark_form_dirty)
        layout.addWidget(self.building_table)
        self.construction_supply_panel = QWidget()
        supply_layout = QVBoxLayout(self.construction_supply_panel)
        supply_layout.setContentsMargins(0, 0, 0, 0)
        supply_layout.addWidget(QLabel("Construction supply (optional)"))
        self.construction_suppliers = QListWidget()
        self.construction_suppliers.setAccessibleName("Owned construction supplier cities")
        self.construction_suppliers.setMaximumHeight(115)
        self.construction_suppliers.itemChanged.connect(self._mark_form_dirty)
        supply_layout.addWidget(self.construction_suppliers)
        self.construction_supply_mode = ComboBox()
        self.construction_supply_mode.addItems(["Self-funded construction", "Send supplies and build", "Send supplies only"])
        self.construction_supply_mode.currentIndexChanged.connect(self._mark_form_dirty)
        supply_layout.addWidget(self.construction_supply_mode)
        self.construction_freighters = CheckBox("Use freighters")
        self.construction_round_up = CheckBox("Round up shipment amounts")
        for checkbox in (self.construction_freighters, self.construction_round_up):
            checkbox.stateChanged.connect(self._mark_form_dirty)
            supply_layout.addWidget(checkbox)
        layout.addWidget(self.construction_supply_panel)
        self.construction_supply_panel.hide()
        self.construction_preview_button = PushButton("Calculate actual upgrade costs & queue…")
        self.construction_preview_button.clicked.connect(self._request_native_preview)
        self.construction_preview_button.setAccessibleDescription(
            "Only reads IkaBot game information. Does not upgrade or ship anything."
        )
        layout.addWidget(self.construction_preview_button)
        self.building_note = CaptionLabel(
            "Choose a city to inspect its actual buildings. Upgrade targets are drafts; "
            "starting requires an upstream-validated construction plan, not raw values."
        )
        self.building_note.setWordWrap(True)
        layout.addWidget(self.building_note)
        self.building_header.hide()
        self.building_table.hide()
        self.building_note.hide()
        self.construction_preview_button.hide()
        self.task_combo.currentIndexChanged.connect(self._selected_task_changed)

        launch_row = QHBoxLayout()
        self.confirm_box = CheckBox("I approve starting this automation")
        self.confirm_box.stateChanged.connect(self._approval_changed)
        launch_row.addWidget(self.confirm_box)
        launch_row.addStretch(1)
        self.start_button = PrimaryPushButton("Review and start…")
        self.start_button.setAccessibleDescription(
            "Review the account, task, and settings in a separate confirmation dialog."
        )
        self.start_button.clicked.connect(self._start)
        launch_row.addWidget(self.start_button)
        self.queue_review_button = PushButton("Add reviewed account to batch")
        self.queue_review_button.clicked.connect(self._queue_review)
        launch_row.addWidget(self.queue_review_button)
        self.configure_footer = CardWidget(configure_root)
        self.configure_footer.setAccessibleName("Review and launch automation")
        footer_layout = QVBoxLayout(self.configure_footer)
        footer_layout.setContentsMargins(16, 9, 16, 9)
        footer_layout.setSpacing(5)
        footer_layout.addLayout(launch_row)

        batch_row = QHBoxLayout()
        self.bulk_note = CaptionLabel(
            "Multi-account actions require a separate review. Each selected account is "
            "checked independently; dispatch stops if any account is not ready."
        )
        self.bulk_note.setWordWrap(True)
        batch_row.addStretch(1)
        self.start_selected_button = PushButton("Start for selected…")
        self.start_selected_button.setToolTip(
            "Review all chosen accounts and run a distinct authorized task request per account"
        )
        self.start_selected_button.clicked.connect(self._start_selected)
        batch_row.addWidget(self.start_selected_button)
        footer_layout.addLayout(batch_row)
        footer_layout.addWidget(self.bulk_note)
        configure_layout.addWidget(self.configure_footer)

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
        layout.addLayout(scope_row)
        layout.addWidget(self.multi_summary)
        self.multi_table = _table(["Account", "Running tasks", "Needs review", "Status"])
        layout.addWidget(self.multi_table, 1)
        layout.addWidget(SubtitleLabel("Independently reviewed account batch"))
        self.review_queue_note = CaptionLabel("Configure and approve each account separately, then add its review. Tickets expire after two minutes.")
        self.review_queue_note.setWordWrap(True)
        layout.addWidget(self.review_queue_note)
        self.review_queue_table = _table(["Account", "Operation", "Reviewed settings"])
        self.review_queue_table.setMinimumHeight(110)
        layout.addWidget(self.review_queue_table, 1)
        queue_actions = QHBoxLayout()
        self.review_queue_remove = PushButton("Remove selected review")
        self.review_queue_remove.clicked.connect(self._remove_review)
        self.review_queue_clear = PushButton("Clear reviews")
        self.review_queue_clear.clicked.connect(self._clear_review_queue)
        self.review_queue_start = PrimaryPushButton("Review and start batch…")
        self.review_queue_start.clicked.connect(self._start_reviewed_batch)
        for button in (self.review_queue_remove, self.review_queue_clear, self.review_queue_start):
            queue_actions.addWidget(button)
        layout.addLayout(queue_actions)

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
            "Hide actions" if self._gallery_open
            else "Browse actions ▾"
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
        self._clear_review_queue()
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
        self._clear_review_queue()
        previous = self.selected_account_id()
        # Read-only "All accounts" includes disabled accounts; only enabled
        # accounts can be offered as candidates for task mutation.
        self._all_account_metadata = [
            dict(a) for a in accounts
            if isinstance(a.get("id"), str) and a["id"]
        ]
        self._status_account_ids = [str(a["id"]) for a in self._all_account_metadata]
        self._account_names = account_player_names(self._all_account_metadata)
        # A metadata refresh may represent a changed session, so discard city caches.
        self._cities_by_account.clear()
        self._buildings_scope = None
        self._building_rows = []
        self._construction_ticket = None
        self._construction_prepared = None
        self._construction_preview_ready = False
        self._pending_preview_key = None
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
            for aid in self._account_ids:
                self.account_combo.addItem(self._account_names[aid])
            if previous in self._account_ids:
                self.account_combo.setCurrentIndex(self._account_ids.index(previous))
        finally:
            self.account_combo.blockSignals(False)
        if not self._bulk_account_ids:
            self._bulk_account_ids = list(self._account_ids)
        for combo in (self.running_account_combo, self.history_account_combo):
            with QSignalBlocker(combo):
                combo.clear()
                for aid in self._account_ids:
                    combo.addItem(self._account_names[aid])
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

    def _populate_city_picker(self, widget: ComboBox, *, optional: bool = False) -> None:
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        with QSignalBlocker(widget):
            widget.clear()
            widget.addItem(
                ("Skip optional reward" if optional else "Choose a city…")
                if cities else "Cities unavailable — refresh to load"
            )
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

    def _populate_island_list(self, widget: QListWidget) -> None:
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        seen: set[str] = set()
        with QSignalBlocker(widget):
            widget.clear()
            for city in cities:
                coords = str(city.get("coords") or "").strip()
                if not re.fullmatch(r"\d{1,3}:\d{1,3}", coords) or coords in seen:
                    continue
                seen.add(coords)
                entry = QListWidgetItem(f"{coords} · {city['name']}")
                entry.setData(Qt.UserRole, coords)
                entry.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                entry.setCheckState(Qt.Unchecked)
                widget.addItem(entry)

    def _lookup_destinations(self, x, y, nonce):
        account = self.selected_account_id()
        if account and self.selected_task_name() in {"sendResources","resourceTransportManager"}:
            self.island_destinations_requested.emit(account, x, y, nonce)

    def set_island_destinations(self, result, nonce):
        if result.get("account_id") != self.selected_account_id() or self.selected_task_name() not in {"sendResources","resourceTransportManager"}:
            return
        editor = self._form_inputs.get("routes") or self._form_inputs.get("destination_city")
        if isinstance(editor, (ShipmentRoutesEditor,ExternalDestinationEditor)):
            editor.set_external(result, nonce)

    def set_island_destinations_unavailable(self, account, nonce):
        if account == self.selected_account_id() and self.selected_task_name() in {"sendResources","resourceTransportManager"}:
            editor = self._form_inputs.get("routes") or self._form_inputs.get("destination_city")
            if isinstance(editor, (ShipmentRoutesEditor,ExternalDestinationEditor)):
                editor.lookup_failed(nonce)

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
            if self.selected_task_name() in CITY_REVIEW_TASKS:
                self._city_review_plan = None
                self._city_review_nonce = None
            picker = self._form_inputs.get("city_id")
            if self.selected_task_name() == "constructionList" and isinstance(picker, ComboBox):
                self._populate_city_picker(picker)
                self._construction_city_changed()
            for key, input_widget in self._form_inputs.items():
                if isinstance(input_widget, QListWidget):
                    if input_widget.property("city_scope") is True:
                        self._populate_city_list(input_widget)
                    elif input_widget.property("island_scope") is True:
                        self._populate_island_list(input_widget)
                    else:
                        continue
                    self._invalidate_review()
                elif (isinstance(input_widget, ComboBox)
                      and input_widget.property("city_picker") is True):
                    self._populate_city_picker(input_widget, optional=not
                                               self._field_is_required(key))
                    self._invalidate_review()
                    if self.selected_task_name() == "attackBarbarians" and key == "city_id":
                        self._clear_attack_inventory()
                    if self.selected_task_name() == "constructBuilding" and key == "city_id":
                        self._clear_build_options()
                elif isinstance(input_widget, (
                    ShipmentRoutesEditor, ExternalDestinationEditor, DonationPoliciesEditor, WorkshopUpgradesEditor,
                    TrainableUnitsEditor, MarketOffersEditor,
                )):
                    # Account-scoped read data are never portable between cities/worlds.
                    input_widget.set_cities(self._cities_by_account.get(account_id, []))
                    self._invalidate_review()

    def _field_is_required(self, key: str) -> bool:
        return any(field["name"] == key and field["required"]
                   for field in self._config_fields_by_task.get(self.selected_task_name() or "", []))

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
        self._reset_construction_preview()
        self.building_table.setRowCount(0)
        self.construction_preview_button.setEnabled(False)
        city_id = self._selected_construction_city()
        account_id = self.selected_account_id()
        self._populate_construction_suppliers()
        if account_id and city_id:
            self.building_note.setText("Loading real building levels for the chosen city…")
            self.buildings_requested.emit(account_id, city_id)
        else:
            self.building_note.setText("Choose an actual city to inspect its buildings.")

    def _populate_construction_suppliers(self):
        selected = self._selected_construction_city()
        with QSignalBlocker(self.construction_suppliers):
            self.construction_suppliers.clear()
            for city in self._cities_by_account.get(self.selected_account_id() or "", []):
                if city["id"] == selected:
                    continue
                item = QListWidgetItem(city["name"] + (" · " + city["coords"] if city.get("coords") else ""))
                item.setData(Qt.UserRole, city["id"])
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.construction_suppliers.addItem(item)
        with QSignalBlocker(self.construction_supply_mode):
            self.construction_supply_mode.setCurrentIndex(0)
        for checkbox in (self.construction_freighters, self.construction_round_up):
            with QSignalBlocker(checkbox):
                checkbox.setChecked(False)

    def _construction_supply_draft(self):
        from daedalus.reviewed_operations import validated_construction_supply

        mode = self.construction_supply_mode.currentIndex()
        if mode == 0:
            return None
        return validated_construction_supply(self._selected_construction_city(), {
            "source_ids": [self.construction_suppliers.item(i).data(Qt.UserRole)
                           for i in range(self.construction_suppliers.count())
                           if self.construction_suppliers.item(i).checkState() == Qt.Checked],
            "useFreighters": self.construction_freighters.isChecked(),
            "round_up": self.construction_round_up.isChecked(), "supply_only": mode == 2,
        })

    def set_buildings(self, account_id: str, city_id: int,
                      buildings: list[dict[str, object]]) -> None:
        if account_id != self.selected_account_id() or city_id != self._selected_construction_city():
            return  # late result from a different account/city
        self._reset_construction_preview()
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
                                "Maximum level" if not item["can_upgrade"] else
                                "Ready now" if item.get("can_upgrade_now", True) else
                                "Needs materials")):
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
            f"{len(self._building_rows)} actual buildings loaded. Check the desired "
            "buildings, set target levels and calculate costs using the actual IkaBot "
            "planner. Missing resources must be supplied before launching."
        )
        self.construction_preview_button.setEnabled(bool(self._building_rows))
        self._invalidate_review()

    def _reset_construction_preview(self) -> None:
        self._construction_ticket = None
        self._construction_ticket = None
        self._construction_prepared = None
        self._construction_preview_ready = False
        self._pending_preview_key = None
        self.construction_preview_button.setEnabled(bool(self._building_rows))
        self._invalidate_review()

    def _selected_building_upgrades(self) -> list[dict[str, int]]:
        upgrades: list[dict[str, int]] = []
        for row, building in enumerate(self._building_rows):
            checkbox = self.building_table.item(row, 0)
            target = self.building_table.cellWidget(row, 4)
            if checkbox is None or checkbox.checkState() != Qt.Checked:
                continue
            if not isinstance(target, QSpinBox) or not target.isEnabled():
                raise ValueError("A selected building cannot be upgraded")
            desired = target.value()
            current = building["level"]
            if desired <= current or desired > current + 10:
                raise ValueError("Select a higher target (at most 10 levels per building)")
            upgrades.append({"position": building["position"], "target_level": desired})
        if not 0 < len(upgrades) <= 12:
            raise ValueError("Select 1 to 12 real buildings before preview")
        return upgrades

    def _request_native_preview(self) -> None:
        task = self.selected_task_name()
        if task not in CITY_REVIEW_TASKS:
            self._request_construction_preview()
            return
        account = self.selected_account_id()
        if account is None:
            return
        if task == "attackBarbarians":
            editor = self._form_inputs.get("waves")
            picker = self._form_inputs.get("city_id")
            cities = self._cities_by_account.get(account, [])
            index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
            if not 1 <= index <= len(cities):
                QMessageBox.warning(self, "Choose origin city", "Choose an actual city first.")
                return
            if not isinstance(editor, BarbarianWavesEditor) or not editor.loaded:
                self._city_review_nonce = str(uuid.uuid4())
                self.building_note.setText("Loading actual troops and ships…")
                self.attack_inventory_requested.emit(account, cities[index-1]["id"], self._city_review_nonce)
                return
        if task == "constructBuilding":
            picker = self._form_inputs.get("city_id")
            choice = self._form_inputs.get("position")
            cities = self._cities_by_account.get(account, [])
            index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
            if not 1 <= index <= len(cities):
                QMessageBox.warning(self, "Choose construction city", "Choose an actual city first.")
                return
            if not isinstance(choice, ComboBox) or choice.currentIndex() <= 0:
                self._city_review_nonce = str(uuid.uuid4())
                self.building_note.setText("Loading current empty slots and building options…")
                self.build_options_requested.emit(account, cities[index-1]["id"], self._city_review_nonce)
                return
        try:
            draft = self._form_inputs['city'].reviewed_draft() if task == 'trainArmy' else self._form_config()
            if task in WORKER_TASKS:
                validated_worker_draft(task, {k: v for k, v in draft.items() if k != "city_id"})
        except ValueError as exc:
            QMessageBox.warning(self, "Choose operation settings", str(exc))
            return
        self._city_review_plan = None
        self._invalidate_review()
        self._city_review_nonce = str(uuid.uuid4())
        if task in WORKER_TASKS:
            self.building_note.setText("Reading the actual worker capacity…")
            self.worker_preview_requested.emit(account, task, draft, self._city_review_nonce)
        elif task == "sendResources":
            self.building_note.setText("Reading current fleet, stock and storage…")
            self.shipment_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "vacationMode":
            self.building_note.setText("Checking account jobs and automatic recovery policy…")
            self.vacation_preview_requested.emit(account, draft["city_id"], self._city_review_nonce)
        elif task == "attackBarbarians":
            self.building_note.setText("Checking actual village and planned waves…")
            self.attack_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "autoBarbarians":
            self.building_note.setText("Reading village level, unit requirements and ships…")
            self.grind_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "trainArmy":
            self.building_note.setText("Checking actual recruitable units and cost in every selected city…")
            self.training_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "stationArmy":
            self.building_note.setText("Checking actual available units and transport capacity…")
            self.station_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "constructBuilding":
            self.building_note.setText("Checking selected building and actual costs…")
            self.build_preview_requested.emit(account, draft, self._city_review_nonce)
        elif task == "reorganizeCityBuildings":
            self.building_note.setText("Comparing the actual city layouts…")
            self.layout_preview_requested.emit(account, draft, self._city_review_nonce)
        else:
            self.building_note.setText("Reading the actual island project and available wood…")
            self.donation_preview_requested.emit(account, draft, self._city_review_nonce)

    def set_shipment_preview(self, result, nonce):
        if (self.selected_task_name() != "sendResources" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if result.get("draft") != draft:
            return
        self._city_review_nonce = None
        self._city_review_plan = {**result, **draft} if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        lines = [f"{result['available_ships']:,}/{result['total_ships']:,} "
                 + ("freighters" if draft["useFreighters"] else "trade ships")
                 + f" available; {result['capacity']:,} cargo per vessel."]
        for row in result["routes"]:
            cargo = ", ".join(f"{n} {v:,}" for n,v in zip(
                ("wood", "wine", "marble", "crystal", "sulfur"), row["resources"]) if v)
            loads = row["minimum_loads"] if row["minimum_loads"] is not None else "unavailable"
            stock = ", ".join(f"{n} {v:,}" for n,v,w in zip(
                ("wood", "wine", "marble", "crystal", "sulfur"), row["stock"], row["resources"]) if w)
            lines.append(f"{row['origin_name']} → {row['destination_name']}: {cargo}. "
                         f"Origin stock: {stock}. "
                         f"First load ≤ {row['first_load_limit']:,}; minimum loads {loads}."
                         + (" Recipient storage unknown." if row["destination_space"] is None else ""))
            timing = row.get("first_load_timing")
            if timing:
                lines.append(f"First-load estimate: {timing['total_seconds']:,} s "
                             f"(queue {timing['queue_seconds']:,}, load {timing['loading_seconds']:,}, "
                             f"travel {timing['travel_seconds']:,} s).")
            else:
                lines.append("First-load timing unavailable.")
            model = row.get("full_route_model")
            if model:
                lines.append(f"Modeled final delivery: {model['delivery_seconds']:,} s ({model['loads']} sequential loads).")
        lines.append("Model assumes exclusive available fleet, symmetric return travel, unchanged loading and storage, no extra waits. Multiple routes share the fleet; no combined ETA.")
        if not result["ready"]:
            lines.append("No usable fleet; choose another fleet or acquire ships.")
        self.building_note.setText("\n".join(lines))
        self._invalidate_review()

    def set_shipment_unavailable(self, nonce):
        if self.selected_task_name() == "sendResources" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Shipment preview unavailable. Check stock, recipients and fleet.")
            self._invalidate_review()

    def set_donation_preview(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "donate" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(key) != draft.get(key) for key in ("city_id", "project", "amount")):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        self.building_note.setText(
            f"{result['city_name']} · {result['project_name']} (level {result['level']}). "
            f"Wood available: {result['stock']:,}; project remaining: {result['remaining']:,}. "
            f"Donate {result['amount']:,} wood once. "
            + ("Ready for review." if self._city_review_plan else
               "Project is upgrading or the amount is unavailable; adjust and preview again.")
        )
        self._invalidate_review()

    def set_donation_preview_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() == "donate" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Donation preview unavailable. Refresh and try again.")
            self._invalidate_review()

    def set_vacation_preview(self, result, nonce):
        if (self.selected_task_name() != "vacationMode" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if result.get("city_id") != draft.get("city_id"):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        warnings = []
        if result["active_jobs"] or result["managed_active"]:
            warnings.append("Stop all active account jobs first.")
        if not result["recovery_disabled"]:
            warnings.append("Disable automatic recovery in Recovery settings first.")
        self.building_note.setText(
            f"{result['city_name']}: vacation mode affects the entire account, not only this city. "
            "Game access and automation may be suspended. Keep recovery disabled until you manually end vacation. "
            + ("Ready for review." if self._city_review_plan else " ".join(warnings))
        )
        self._invalidate_review()

    def set_vacation_unavailable(self, nonce):
        if self.selected_task_name() == "vacationMode" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Vacation preview unavailable. Check account and recovery settings.")
            self._invalidate_review()

    def _clear_attack_inventory(self, *_args):
        editor = self._form_inputs.get("waves")
        if isinstance(editor, BarbarianWavesEditor):
            editor.clear()

    def set_attack_inventory(self, result, nonce):
        if (self.selected_task_name() != "attackBarbarians" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        picker = self._form_inputs.get("city_id")
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
        editor = self._form_inputs.get("waves")
        if (not isinstance(editor, BarbarianWavesEditor) or not 1 <= index <= len(cities)
                or result.get("city_id") != cities[index-1]["id"]):
            return
        editor.set_inventory(result)
        self.building_note.setText("Choose quantities, then preview the attack. No troops have been sent.")
        self._invalidate_review()

    def set_attack_preview(self, result, nonce):
        if (self.selected_task_name() != "attackBarbarians" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if (result.get("city_id") != draft.get("city_id") or result.get("target_city_id") != draft.get("target_city_id")
                or result.get("reviewed_waves") != draft.get("waves")):
            return
        self._city_review_nonce = None
        self._city_review_plan = {**result, "waves": draft["waves"]} if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        waves = "; ".join(f"Round {w['round']}: " + ", ".join(
            f"{u['name']} × {u['amount']}" for u in w["units"]) +
            (" (looting)" if w["loot"] else f"; loot ships {w['ships']}") for w in result["waves"])
        self.building_note.setText(f"{result['city_name']} → island of {result['target_name']}, "
                                   f"village level {result['level']}. Ships: {result['available_ships']:,}/{result['required_ships']:,}. "
                                   + waves + (". Ready for review." if self._city_review_plan else ". Prerequisites missing."))
        self._invalidate_review()

    def set_attack_unavailable(self, nonce):
        if self.selected_task_name() == "attackBarbarians" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Attack inventory or preview unavailable. Refresh and try again.")
            self._invalidate_review()

    def set_grind_preview(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "autoBarbarians" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(k) != v for k, v in draft.items()):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        requirements = "; ".join(f"{r['name']}: {r['available']:,}/{r['required']:,}" for r in result["requirements"])
        self.building_note.setText(
            f"{result['city_name']} → island of {result['target_name']}, village level {result['level']}. "
            f"Ships: {result['available_ships']:,}/{result['required_ships']:,}. {requirements}. "
            "Repeat using the upstream preset until stopped or unsupported. "
            + ("Ready for review." if self._city_review_plan else "Village destroyed or prerequisites missing.")
        )
        self._invalidate_review()

    def set_grind_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() == "autoBarbarians" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Automatic attack preview unavailable. Check the village and try again.")
            self._invalidate_review()

    def set_training_preview(self, result: dict[str, object], nonce: str) -> None:
        from daedalus.training_contract import RESOURCES, validate_training_review

        if (self.selected_task_name() != "trainArmy" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_inputs["city"].reviewed_draft()
            validate_training_review(self.selected_account_id(), draft, result)
        except (ValueError, TypeError, KeyError, IndexError):
            self.set_training_unavailable(nonce)
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        lines = [f"{result['cycles']} cycle(s); {len(result['rounds'])} ordered round(s)."]
        for row in result["cities"]:
            lines.append(row["city_name"] + (" — ready" if row["ready"] else " — insufficient initial stock"))
            for index, group in enumerate(row["rounds"], 1):
                lines.append(f"Round {index}: " + ", ".join(f"{u['local_name']} × {u['cantidad']:,}" for u in group))
            lines.append("Total commitment: " + ", ".join(f"{k} {v:g}" for k,v in zip(RESOURCES,row["total_costs"]) if v))
        lines.append("Later rounds stop if costs, resources, city or queue observations change. Manual recovery only.")
        self.building_note.setText("\n".join(lines))
        self._invalidate_review()

    def set_training_unavailable(self, nonce):
        if self.selected_task_name() == "trainArmy" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Recruitment preview unavailable. Check selected cities, buildings and units.")
            self._invalidate_review()

    def set_station_preview(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "stationArmy" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(k) != v for k, v in draft.items()):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        capacity = (f" Cargo weight {result['weight']:,} / capacity {result['capacity']:,}."
                    if result["ground"] else "")
        if result.get("deployments"):
            description = "\n".join(
                f"{row['city_name']} → {result['destination_name']}: {row['total']:,} "
                + ("ground units" if row["ground"] else "fleet units")
                for row in result["deployments"])
            description += "\nTotal: " + f"{result['total']:,} units." + capacity
        else:
            description = (f"{result['city_name']} → {result['destination_name']}: all {result['total']:,} "
                           + ("available ground units." if result["ground"] else "available fleet units.") + capacity)
        self.building_note.setText(description + (" Ready for review." if self._city_review_plan else
                                                " No units or insufficient shared capacity."))
        self._invalidate_review()

    def set_station_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() == "stationArmy" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Deployment preview unavailable. Refresh and try again.")
            self._invalidate_review()

    def _clear_build_options(self, *_args: object) -> None:
        choice = self._form_inputs.get("position")
        if self.selected_task_name() == "constructBuilding" and isinstance(choice, ComboBox):
            with QSignalBlocker(choice):
                choice.clear()
                choice.addItem("Load actual building options first…")
            self._mark_form_dirty()

    def set_build_options(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "constructBuilding" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        picker = self._form_inputs.get("city_id")
        choice = self._form_inputs.get("position")
        cities = self._cities_by_account.get(self.selected_account_id() or "", [])
        index = picker.currentIndex() if isinstance(picker, ComboBox) else -1
        if (not isinstance(choice, ComboBox) or not 1 <= index <= len(cities)
                or result.get("city_id") != cities[index-1]["id"]):
            return
        with QSignalBlocker(choice):
            choice.clear()
            choice.addItem("Choose an actual building and slot…")
            for row in result["options"]:
                label = f"{row['name']} · slot {row['position']} ({row['surface']})"
                if not row["ready"]:
                    label += " — not ready"
                choice.addItem(label, userData={"position": row["position"], "building_id": row["building_id"]})
            choice.setCurrentIndex(0)
        self._city_review_nonce = None
        self._city_review_plan = None
        self.building_note.setText(
            f"{len(result['options'])} actual building choices. Select one and preview the cost."
        )
        self._invalidate_review()

    def set_build_preview(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "constructBuilding" or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(k) != v for k, v in draft.items()):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        costs = ", ".join(f"{r}: {n:,}" for r, n in zip(("wood", "wine", "marble", "crystal", "sulfur"), result["costs"]))
        self.building_note.setText(
            f"{result['name']} · slot {result['position']}. Cost: {costs}. "
            + ("Ready for review." if self._city_review_plan else "City is busy or materials are missing.")
        )
        self._invalidate_review()

    def set_build_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() == "constructBuilding" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Building inventory or preview unavailable. Retry after refresh.")
            self._invalidate_review()

    def set_layout_preview(self, result: dict[str, object], nonce: str) -> None:
        if (self.selected_task_name() != "reorganizeCityBuildings"
                or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(k) != v for k, v in draft.items()):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        moves = result["moves"]
        summary = "; ".join(f"{m['building']} {m['from']} → {m['to']} (swap {m['displaced']})" for m in moves)
        self.building_note.setText(
            f"{result['template_name']} → {result['city_name']}: {len(moves)} swaps. "
            + (summary if moves else "No applicable layout swaps.")
        )
        self._invalidate_review()

    def set_layout_preview_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() == "reorganizeCityBuildings" and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Layout preview unavailable. Choose different owned cities.")
            self._invalidate_review()

    def set_worker_preview(self, result: dict[str, object], nonce: str) -> None:
        task = self.selected_task_name()
        if (task not in WORKER_TASKS or result.get("task") != task
                or nonce != self._city_review_nonce
                or result.get("account_id") != self.selected_account_id()):
            return
        try:
            draft = self._form_config()
        except ValueError:
            return
        if any(result.get(key) != value for key, value in draft.items()):
            return
        self._city_review_nonce = None
        self._city_review_plan = result if result.get("ready") and result.get("preview_id") else None
        self._city_review_expires = time.monotonic() + int(result.get("expires_in") or 0)
        rows = result.get("assignments") or [result]
        lines = []
        for row in rows:
            current = row["current"] if row["current"] is not None else "not reported"
            project = {"resource": "forest", "tradegood": "luxury resource"}.get(row.get("project"), task)
            lines.append(f"{row['city_name']} · {project}: current {current}; maximum {row['maximum']}; "
                         f"extra {row['extra']}; set to {row['target']} workers.")
        self.building_note.setText("\n".join(lines) +
            "\nThe game may reject assignments if population is insufficient. Review and approve before starting.")
        self._invalidate_review()

    def set_worker_preview_unavailable(self, nonce: str) -> None:
        if self.selected_task_name() in WORKER_TASKS and nonce == self._city_review_nonce:
            self._city_review_nonce = None
            self._city_review_plan = None
            self.building_note.setText("Worker preview unavailable. Check the city and try again.")
            self._invalidate_review()

    def _request_construction_preview(self) -> None:
        account_id = self.selected_account_id()
        city_id = self._selected_construction_city()
        if not account_id or city_id is None or self._buildings_scope != (account_id, city_id):
            QMessageBox.warning(self, "City data needed",
                                "Load real buildings for the selected city first.")
            return
        try:
            upgrades = self._selected_building_upgrades()
            supply = self._construction_supply_draft()
        except ValueError as exc:
            QMessageBox.warning(self, "Choose upgrades", str(exc))
            return
        self._reset_construction_preview()
        self._pending_preview_key = (
            account_id, city_id,
            tuple((row["position"], row["target_level"]) for row in upgrades),
            supply,
        )
        self.construction_preview_button.setEnabled(False)
        self.building_note.setText(
            "Reading IkaBot's actual building costs and queue durations. "
            "No upgrade or shipment has started."
        )
        if supply is None:
            self.construction_preview_requested.emit(account_id, city_id, upgrades)
        else:
            self.construction_supply_preview_requested.emit(account_id, city_id, upgrades, supply)

    def set_construction_preview(self, result: dict[str, object]) -> None:
        account_id, city_id = result.get("account_id"), result.get("city_id")
        try:
            upgrades = self._selected_building_upgrades()
            supply = self._construction_supply_draft()
        except ValueError:
            return
        scope = (account_id, city_id, tuple(
            (row["position"], row["target_level"]) for row in upgrades
        ), supply)
        if (self.selected_task_name() != "constructionList"
                or self._pending_preview_key != scope
                or self.selected_account_id() != account_id
                or self._selected_construction_city() != city_id):
            return
        self._pending_preview_key = None
        config = result.get("config")
        ready = result.get("ready") is True
        if not isinstance(config, dict):
            self.set_construction_preview_unavailable(account_id, city_id)
            return
        if supply is not None and (not isinstance(result.get("supply"), dict) or result["supply"].get("options") != supply):
            self.set_construction_preview_unavailable(account_id, city_id)
            return
        self._construction_prepared = config if ready else None
        key, ttl = result.get("preview_id"), result.get("expires_in")
        self._construction_ticket = (
            (key, time.monotonic() + ttl)
            if ready and isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", key)
            and type(ttl) is int and 0 < ttl <= 120 else None
        )
        self._construction_preview_ready = ready and (supply is None or self._construction_ticket is not None)
        names = ("Wood", "Wine", "Marble", "Crystal", "Sulfur")
        costs, missing = result["costs"], result["missing"]
        cost_text = " · ".join(f"{name} {qty:,}" for name, qty in zip(names, costs))
        shortages = " · ".join(
            f"{name} {qty:,}" for name, qty in zip(names, missing) if qty
        )
        seconds = result["estimated_seconds"]
        description = (f"Actual IkaBot costs: {cost_text}. Estimated queue: "
                       f"{seconds // 3600}h {(seconds % 3600) // 60}m. ")
        if supply is not None:
            observation = result["supply"]
            fleet = observation.get("shipment")
            description += "\n" + ("Supply only." if supply["supply_only"] else "Supply, then build when resources arrive.")
            if fleet:
                description += f"\n{'Freighters' if supply['useFreighters'] else 'Trade ships'}: {fleet['available_ships']} free / {fleet['total_ships']} total; capacity {fleet['capacity']:,} each."
                for row in fleet["routes"]:
                    amounts = ", ".join(f"{name} {n:,}" for name,n in zip(names,row["resources"]) if n)
                    description += f"\n{row['origin_name']} → {row['destination_name']}: {amounts}; minimum loads {row['minimum_loads']}."
                    timing = row.get("first_load_timing")
                    if timing:
                        description += f" First-load estimate: {timing['total_seconds']:,} s."
                    else:
                        description += " First-load timing unavailable."
                    model = row.get("full_route_model")
                    if model:
                        description += f" Modeled final delivery: {model['delivery_seconds']:,} s."
            if any(observation["remaining"]):
                description += "\nUncovered shortage: " + ", ".join(f"{n} {v:,}" for n,v in zip(names,observation["remaining"]) if v)
            description += "\nModel assumes exclusive fleet and unchanged route conditions; no combined ETA. Manual recovery only."
            if not ready:
                description += " Cannot start: choose more suppliers, check storage and fleet, or use self-funded construction."
        elif ready:
            description += "Resources are sufficient. Review and approve the queue to start."
        else:
            description += (f"Missing: {shortages}. Supply the shortages, then preview again. "
                            "This queue cannot start until it is affordable.")
        self.building_note.setText(description)
        self.construction_preview_button.setEnabled(True)
        self._invalidate_review()

    def set_construction_preview_unavailable(self, account_id: str, city_id: int) -> None:
        if (account_id == self.selected_account_id()
                and city_id == self._selected_construction_city()):
            self._reset_construction_preview()
            self.building_note.setText(
                "IkaBot could not safely calculate this upgrade queue. "
                "No upgrade has started; reconnect and recheck the building targets."
            )

    def _workshop_city_requested(self, city_id: int) -> None:
        account_id = self.selected_account_id()
        if (account_id and self.selected_task_name() == "UpgradeUnits"
                and type(city_id) is int):
            self.workshop_requested.emit(account_id, city_id)

    def set_workshop_upgrades(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "UpgradeUnits"):
            return
        editor = self._form_inputs.get("jobs")
        if isinstance(editor, WorkshopUpgradesEditor):
            editor.set_workshop_data(
                result["city_id"], result["upgrades"], result["workshop_level"]
            )

    def set_workshop_unavailable(self, account_id: str, city_id: int) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("jobs")
        if isinstance(editor, WorkshopUpgradesEditor):
            editor.set_unavailable(city_id)

    def _trainable_city_requested(self, city_id: int, train_troops: bool) -> None:
        account_id = self.selected_account_id()
        if (account_id and self.selected_task_name() == "trainArmy"
                and type(city_id) is int and type(train_troops) is bool):
            self.trainable_units_requested.emit(account_id, city_id, train_troops)

    def set_trainable_units(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "trainArmy"):
            return
        editor = self._form_inputs.get("city")
        if isinstance(editor, TrainableUnitsEditor):
            editor.set_trainables(result)

    def set_trainable_units_unavailable(
        self, account_id: str, city_id: int, train_troops: bool,
    ) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("city")
        if isinstance(editor, TrainableUnitsEditor):
            editor.set_unavailable(city_id, train_troops)

    def _market_quotes_requested(self, city_id: int, resource_type: int, side: str) -> None:
        account_id = self.selected_account_id()
        expected = "buy" if self.selected_task_name() == "buyResources" else (
            "sell_to_offers", "create_offer"
        ) if self.selected_task_name() == "sellResources" else ()
        if (account_id and type(city_id) is int and type(resource_type) is int
                and side in (expected if isinstance(expected, tuple) else (expected,))):
            self.market_quotes_requested.emit(account_id, city_id, resource_type, side)

    def set_market_quotes(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() not in {"buyResources", "sellResources"}):
            return
        key = "city" if self.selected_task_name() == "buyResources" else "mode"
        editor = self._form_inputs.get(key)
        if isinstance(editor, MarketOffersEditor):
            editor.set_quotes(result)

    def set_market_unavailable(self, account_id: str, city_id: int,
                               resource_type: int, side: str) -> None:
        if account_id != self.selected_account_id():
            return
        key = "city" if self.selected_task_name() == "buyResources" else "mode"
        editor = self._form_inputs.get(key)
        if isinstance(editor, MarketOffersEditor):
            editor.set_unavailable(city_id, resource_type, side)

    def set_academies(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "research"):
            return
        editor = self._form_inputs.get("cities_ids")
        if isinstance(editor, AcademyResearchEditor):
            editor.set_academies(result["academies"], result.get("studies"))

    def set_academies_unavailable(self, account_id: str) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("cities_ids")
        if isinstance(editor, AcademyResearchEditor):
            editor.set_unavailable()

    def set_taverns(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "tavernManager"):
            return
        editor = self._form_inputs.get("cities_ids")
        if isinstance(editor, TavernCitiesEditor):
            editor.set_taverns(result["taverns"])

    def set_taverns_unavailable(self, account_id: str) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("cities_ids")
        if isinstance(editor, TavernCitiesEditor):
            editor.set_unavailable()

    def set_miracles(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "activateMiracle"):
            return
        editor = self._form_inputs.get("wonder")
        if isinstance(editor, MiracleTempleEditor):
            editor.set_miracles(result["miracles"])

    def set_miracles_unavailable(self, account_id: str) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("wonder")
        if isinstance(editor, MiracleTempleEditor):
            editor.set_unavailable()

    def set_shrine(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "activateShrine"):
            return
        editor = self._form_inputs.get("godids")
        if isinstance(editor, OlympusShrineEditor):
            editor.set_shrine(result["shrine"])

    def set_pirate_fortresses(self, result: dict[str, object]) -> None:
        if (result.get("account_id") != self.selected_account_id()
                or self.selected_task_name() != "autoPirate"):
            return
        editor = self._form_inputs.get("pirateCount")
        if isinstance(editor, PiracyMissionsEditor):
            editor.set_fortresses(result["fortresses"])

    def set_pirate_fortresses_unavailable(self, account_id: str) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("pirateCount")
        if isinstance(editor, PiracyMissionsEditor):
            editor.set_unavailable()

    def set_shrine_unavailable(self, account_id: str) -> None:
        if account_id != self.selected_account_id():
            return
        editor = self._form_inputs.get("godids")
        if isinstance(editor, OlympusShrineEditor):
            editor.set_unavailable()

    def set_buildings_unavailable(self, account_id: str, city_id: int) -> None:
        if account_id == self.selected_account_id() and city_id == self._selected_construction_city():
            self._buildings_scope = None
            self._building_rows.clear()
            self._reset_construction_preview()
            self.building_table.setRowCount(0)
            self.construction_preview_button.setEnabled(False)
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
            for key, input_widget in self._form_inputs.items():
                if isinstance(input_widget, QListWidget):
                    if input_widget.property("city_scope") is True:
                        self._populate_city_list(input_widget)
                    elif input_widget.property("island_scope") is True:
                        self._populate_island_list(input_widget)
                    else:
                        continue
                    self._invalidate_review()
                elif (isinstance(input_widget, ComboBox)
                      and input_widget.property("city_picker") is True):
                    self._populate_city_picker(input_widget, optional=not
                                               self._field_is_required(key))
                    self._invalidate_review()
                elif isinstance(input_widget, (
                    ShipmentRoutesEditor, DonationPoliciesEditor, WorkshopUpgradesEditor,
                    TrainableUnitsEditor, MarketOffersEditor,
                )):
                    # Account-scoped read data are never portable between cities/worlds.
                    input_widget.set_cities(self._cities_by_account.get(account_id, []))
                    self._invalidate_review()

    def _choose_bulk_accounts(self) -> None:
        from daedalus.desktop.account_scope import AccountSelectionDialog

        dialog = AccountSelectionDialog(
            self._all_account_metadata, self._bulk_account_ids, self,
            title="Choose automation accounts",
            display_names=self._account_names,
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
        self.overview_choose_button.setEnabled(bool(self._status_account_ids))
        self.choose_bulk_button.setText(f"Choose accounts ({count})…")
        self.overview_choose_button.setText(f"Choose accounts ({count})…")
        self.view_selected_button.setText(f"Refresh selected ({count})")
        self.start_selected_button.setText(f"Start for selected ({count})…")
        ineligible = [aid for aid in self._bulk_account_ids
                      if aid not in self._account_ids]
        can_start = bool(count) and count <= 32 and not ineligible
        # One city's construction plan cannot be dispatched against other account IDs.
        if self.selected_task_name() not in BATCH_TASKS:
            can_start = False
        if expert_configuration_needed(
                self._config_fields_by_task.get(self.selected_task_name() or "", [])):
            can_start = False
        self.start_selected_button.setEnabled(
            self._dispatch_enabled and can_start
            and not self._pending_launch and bool(self._task_names)
        )
        if self.selected_task_name() not in BATCH_TASKS:
            self.bulk_note.setText(
                "Account-specific plans must be configured separately for each account."
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
                "Each selected account is checked separately before a batch starts."
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
            label = self._account_names.get(str(row["account_id"])) or str(row["account_id"])
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

    def _current_review_ticket(self):
        task = self.selected_task_name()
        if task == "constructionList":
            return self._construction_ticket
        if task in CITY_REVIEW_TASKS and self._city_review_plan:
            return self._city_review_plan.get("preview_id"), self._city_review_expires
        return None

    def _update_review_queue_controls(self):
        ticket = self._current_review_ticket()
        task = self.selected_task_name()
        account = self.selected_account_id()
        self.queue_review_button.setVisible(task in BATCH_REVIEW_TASKS)
        self.queue_review_button.setEnabled(bool(
            ticket and ticket[0] and ticket[1] > time.monotonic() and account
            and self.start_button.isEnabled() and self._reviewed and self.confirm_box.isChecked()
            and (account in self._review_queue or len(self._review_queue) < 32)))
        self.review_queue_remove.setEnabled(bool(self._review_queue) and not self._pending_launch)
        self.review_queue_clear.setEnabled(bool(self._review_queue) and not self._pending_launch)
        self.review_queue_start.setEnabled(bool(self._review_queue) and self._dispatch_enabled and not self._pending_launch)

    def _render_review_queue(self):
        _populate(self.review_queue_table, [
            [self._account_names.get(aid, aid), _friendly_task(row["task"]), row["summary"]]
            for aid,row in self._review_queue.items()
        ])
        self.review_queue_note.setText(
            f"{len(self._review_queue)} independently approved accounts. Expired reviews block the whole batch; no job starts until all checks pass."
            if self._review_queue else "Configure and approve each account separately, then add its review. Tickets expire after two minutes.")
        self._update_review_queue_controls()

    def _clear_review_queue(self):
        self._review_queue.clear()
        self._render_review_queue()

    def _remove_review(self):
        index = self.review_queue_table.currentRow()
        if 0 <= index < len(self._review_queue):
            self._review_queue.pop(list(self._review_queue)[index])
            self._render_review_queue()

    def _queue_review(self):
        ticket = self._current_review_ticket()
        account, task = self.selected_account_id(), self.selected_task_name()
        if (not self.queue_review_button.isEnabled() or not ticket or not account
                or task not in BATCH_REVIEW_TASKS or time.monotonic() >= ticket[1]):
            return
        # For construction include the exact queue of named building targets.
        summary = self.building_note.text()
        if task == "constructionList" and self._construction_prepared:
            buildings = self._construction_prepared.get("buildings", [])
            summary = "; ".join(f"{b['name']} {b['level']} → {b['upgradeTo']}" for b in buildings) + ". " + summary
        row = {"account_id": account, "task": task, "preview_id": ticket[0]}
        validated_batch_entries([row])
        self._review_queue[account] = {**row, "summary": summary, "expires": ticket[1]}
        self._city_review_plan = None
        self._construction_ticket = None
        self._construction_prepared = None
        self._construction_preview_ready = False
        self._invalidate_review()
        self._render_review_queue()
        self._show_section(3)

    def _start_reviewed_batch(self):
        if not self.review_queue_start.isEnabled():
            return
        if any(aid not in self._account_ids or row["expires"] <= time.monotonic()
               for aid,row in self._review_queue.items()):
            self.review_queue_note.setText("One or more reviews expired or the account is unavailable. Replace those reviews before starting.")
            return
        entries = validated_batch_entries([
            {k:row[k] for k in ("account_id", "task", "preview_id")}
            for row in self._review_queue.values()
        ])
        summaries = "\n\n".join(self._account_description(aid) + " · " + _friendly_task(row["task"]) +
                                 "\n" + row["summary"] for aid,row in self._review_queue.items())
        answer = QMessageBox.question(self, "Review independent account batch",
            summaries + "\n\nStart these exact independently approved operations? All tickets and prerequisites are checked first. Dispatch stops on uncertainty.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._pending_launch = True
            self._clear_review_queue()
            self.reviewed_batch_requested.emit(entries)
            self._invalidate_review()

    def _start_selected(self) -> None:
        # Preserve current form's explicit approval; all accounts get independent
        # server preflight and separate UUIDs inside the off-thread API worker.
        if (not self._dispatch_enabled or self._pending_launch
                or self.selected_task_name() not in BATCH_TASKS
                or not self._bulk_account_ids or len(self._bulk_account_ids) > 32
                or any(aid not in self._account_ids for aid in self._bulk_account_ids)
                or not self.selected_task_name()
                or expert_configuration_needed(self._config_fields_by_task.get(
                    self.selected_task_name() or "", []))):
            return
        if not self._reviewed or not self.confirm_box.isChecked():
            # Invalid consent should be contextual, not an unexpected modal.
            # A modal also traps offscreen/keyboard-only users in this path.
            self.bulk_note.setText(
                "Review this automation and check the authorization box above "
                "before starting tasks for selected accounts."
            )
            return
        try:
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
            and (not isinstance(item.get("workflow"), dict)
                 or item["workflow"].get("desktop") == "native")
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

    def _mark_form_dirty(self, *_args: object) -> None:
        self._form_dirty = True
        if self.selected_task_name() in CITY_REVIEW_TASKS:
            self._city_review_plan = None
            self._city_review_nonce = None
            self.building_note.setText("Preview the chosen city and settings before approval.")
        if self.selected_task_name() == "constructionList":
            self._construction_ticket = None
            self._construction_prepared = None
            self._construction_preview_ready = False
            self._pending_preview_key = None
            self.construction_preview_button.setEnabled(bool(self._building_rows))
        self._invalidate_review()

    def _selected_task_changed(self, *_args: object) -> None:
        # A response from a prior visit to the same account/task must not
        # unlock the new draft merely because its identifiers match again.
        self._selection_generation += 1
        self._city_review_plan = None
        self._city_review_nonce = None
        while self.parameter_layout.rowCount():
            self.parameter_layout.removeRow(0)
        self._form_inputs.clear()
        self._buildings_scope = None
        self._building_rows = []
        self._construction_ticket = None
        self._construction_prepared = None
        self._construction_preview_ready = False
        self._pending_preview_key = None
        self.building_table.setRowCount(0)
        name = self.selected_task_name()
        show_buildings = name == "constructionList"
        self.building_header.setVisible(show_buildings)
        self.building_table.setVisible(show_buildings)
        self.construction_supply_panel.setVisible(show_buildings)
        if show_buildings:
            self._populate_construction_suppliers()
        self.building_note.setVisible(show_buildings or name in CITY_REVIEW_TASKS)
        self.construction_preview_button.setVisible(show_buildings or name in CITY_REVIEW_TASKS)
        self.construction_preview_button.setText(
            "Preview island donation…" if name == "donate" else
            "Preview worker assignment…" if name in WORKER_TASKS else
            "Preview layout changes…" if name == "reorganizeCityBuildings" else
            "Preview shipment capacity…" if name == "sendResources" else
            "Preview vacation activation…" if name == "vacationMode" else
            "Load troops / preview attack…" if name == "attackBarbarians" else
            "Preview automatic attacks…" if name == "autoBarbarians" else
            "Preview recruitment rounds…" if name == "trainArmy" else
            "Preview deployment…" if name == "stationArmy" else
            "Load options / preview building…" if name == "constructBuilding" else "Calculate actual upgrade costs & queue…")
        self.construction_preview_button.setEnabled(name in CITY_REVIEW_TASKS)
        if name in CITY_REVIEW_TASKS:
            self.building_note.setText("Choose a city and settings, then preview.")

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
        expert_needed = name == "webServer" or (
            name != "constructionList" and expert_configuration_needed(fields)
        )
        self.expert_note.setVisible(expert_needed)
        if expert_needed:
            self.expert_note.setText(
                "Not yet available in the desktop app: this action needs a dedicated "
                "game-data editor. Starting is disabled until that editor is supported."
            )
        for field in fields:
            key = str(field["name"])
            if name == "constructionList" and key not in {"city_id", "city_name"}:
                # Construction internals are supplied by the verified preview.
                continue
            if (field.get("type") in {"hidden_derived", "json"}
                    and not (name == "constructionList" and key == "city_id")):
                # Opaque engine structures never become editable text fields.
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
            if kind == "resource_limits":
                widget = ResourceLimitsEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "resource_config":
                widget = ResourceAmountsEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "shipment_routes":
                widget = ShipmentRoutesEditor(self)
                widget.lookup_requested.connect(self._lookup_destinations)
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "donation_policies":
                widget = DonationPoliciesEditor(self)
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "map_center":
                widget = MapAreaEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "piracy_missions":
                widget = PiracyMissionsEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "olympus_shrine":
                widget = OlympusShrineEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "miracle_temple":
                widget = MiracleTempleEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "tavern_cities":
                widget = TavernCitiesEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "academy_research":
                widget = AcademyResearchEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind in {"market_buy", "market_sell"}:
                widget = MarketOffersEditor(self, buying=kind == "market_buy")
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.changed.connect(self._mark_form_dirty)
                widget.market_requested.connect(self._market_quotes_requested)
            elif kind == "train_units":
                widget = TrainableUnitsEditor(self)
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.changed.connect(self._mark_form_dirty)
                widget.city_requested.connect(self._trainable_city_requested)
            elif kind == "workshop_jobs":
                widget = WorkshopUpgradesEditor(self)
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.changed.connect(self._mark_form_dirty)
                widget.city_requested.connect(self._workshop_city_requested)
            elif kind == "island_list":
                widget = QListWidget(self)
                widget.setProperty("island_scope", True)
                widget.setMinimumHeight(110)
                widget.setMaximumHeight(140)
                self._populate_island_list(widget)
                widget.itemChanged.connect(self._mark_form_dirty)
            elif kind == "city_list":
                widget = QListWidget(self)
                widget.setProperty("city_scope", True)
                widget.setAccessibleName(f"Choose account cities for {label}")
                widget.setMinimumHeight(105)
                widget.setMaximumHeight(135)
                self._populate_city_list(widget)
                widget.itemChanged.connect(self._mark_form_dirty)
            elif kind == "choices_list":
                widget = QListWidget(self)
                widget.setAccessibleName(f"Choose options for {label}")
                widget.setMinimumHeight(105)
                widget.setMaximumHeight(135)
                for idx, choice in enumerate(field["choices"]):
                    labels = field.get("choice_labels", [])
                    item = QListWidgetItem(str(labels[idx] if idx < len(labels) else choice))
                    item.setData(Qt.UserRole, choice)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    widget.addItem(item)
                widget.itemChanged.connect(self._mark_form_dirty)
            elif kind == "external_destination":
                widget = ExternalDestinationEditor(self)
                widget.set_cities(self._cities_by_account.get(self.selected_account_id() or "", []))
                widget.lookup_requested.connect(self._lookup_destinations)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "attack_waves":
                widget = BarbarianWavesEditor(self)
                widget.changed.connect(self._mark_form_dirty)
            elif kind == "build_choice":
                widget = ComboBox()
                widget.addItem("Load actual building options first…")
                widget.currentIndexChanged.connect(self._mark_form_dirty)
            elif kind == "city_picker":
                widget = ComboBox()
                widget.setProperty("city_picker", True)
                widget.setAccessibleName(f"Choose actual city for {label}")
                self._populate_city_picker(widget, optional=not field["required"])
                widget.currentIndexChanged.connect(self._mark_form_dirty)
                if name == "attackBarbarians" and key == "city_id":
                    widget.currentIndexChanged.connect(self._clear_attack_inventory)
                if name == "constructBuilding" and key == "city_id":
                    widget.currentIndexChanged.connect(self._clear_build_options)
            elif name == "constructionList" and key == "city_id":
                widget = ComboBox()
                widget.setAccessibleName("Choose a real city for construction")
                self._populate_city_picker(widget)
                widget.currentIndexChanged.connect(self._construction_city_changed)
            elif field.get("choices"):
                widget = ComboBox()
                choices = field["choices"]
                choice_labels = field.get("choice_labels", [])
                for idx, choice in enumerate(choices):
                    text = choice_labels[idx] if idx < len(choice_labels) else choice
                    widget.addItem(str(text))
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
                widget.setRange(float(field.get("minimum", -1_000_000)),
                                float(field.get("maximum", 1_000_000)))
                widget.setDecimals(2)
                widget.setValue(float(default))
                if field.get("suffix"):
                    widget.setSuffix(str(field["suffix"]))
                widget.valueChanged.connect(self._mark_form_dirty)
            else:
                widget = LineEdit()
                if default is not None:
                    widget.setText(str(default))
                else:
                    widget.setPlaceholderText("Required" if field["required"] else "Optional")
                widget.textChanged.connect(self._mark_form_dirty)
            help_text = str(field.get("help") or "")
            style_form_input(widget, label, help_text)
            self.parameter_layout.addRow(label, widget)
            self._form_inputs[key] = widget
        self.parameter_scroll.setVisible(bool(self._form_inputs))
        if name == "research" and self.selected_account_id():
            self.academies_requested.emit(self.selected_account_id())
        if name == "tavernManager" and self.selected_account_id():
            self.taverns_requested.emit(self.selected_account_id())
        if name == "activateMiracle" and self.selected_account_id():
            self.miracles_requested.emit(self.selected_account_id())
        if name == "activateShrine" and self.selected_account_id():
            self.shrine_requested.emit(self.selected_account_id())
        if name == "autoPirate" and self.selected_account_id():
            self.pirate_fortresses_requested.emit(self.selected_account_id())
        if name == "donationBot":
            method = self._form_inputs.get("donate_method")
            policy = self._form_inputs.get("cities_dict")
            if isinstance(method, ComboBox) and isinstance(policy, DonationPoliciesEditor):
                method.currentIndexChanged.connect(
                    lambda _index: policy.update_method(
                        [1, 2, 3][method.currentIndex()]
                        if 0 <= method.currentIndex() < 3 else 1
                    )
                )
                policy.update_method([1, 2, 3][method.currentIndex()]
                                     if 0 <= method.currentIndex() < 3 else 1)
        if name in {"autoPirate", "activateShrine", "resourceTransportManager"}:
            driver = self._form_inputs.get("pirateSchedule" if name == "autoPirate" else "mode")
            if isinstance(driver, ComboBox):
                driver.currentIndexChanged.connect(self._update_native_visibility)
            elif isinstance(driver, CheckBox):
                driver.stateChanged.connect(self._update_native_visibility)
            self._update_native_visibility()
        if fields:
            # Match the form to its contents instead of leaving a large empty
            # box under single-parameter workflows.
            visible_fields = [f for f in fields if f.get("type") != "hidden_derived"
                              and (name != "constructionList" or f.get("name") == "city_id")]
            list_extra = 135 if any(field.get("type") in {
                "city_list", "choices_list", "island_list", "shipment_routes",
                "donation_policies", "resource_limits", "resource_config",
                "workshop_jobs", "train_units", "market_buy", "market_sell",
                "academy_research", "tavern_cities", "miracle_temple",
                "olympus_shrine", "piracy_missions",
            } for field in visible_fields) else 0
            # Use the outer page's one scrollbar: native tables and policy
            # editors should never create a second tiny scrolling viewport.
            self.parameter_container.adjustSize()
            content_height = max(
                self.parameter_container.sizeHint().height() + 16,
                len(visible_fields) * 44 + 24 + list_extra,
            )
            self.parameter_scroll.setFixedHeight(min(3000, max(72, content_height)))
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
                     or any(field.get("type") in {
                         "city_list", "city_picker", "island_list", "shipment_routes", "attack_waves", "external_destination",
                         "donation_policies", "workshop_jobs", "train_units",
                         "market_buy", "market_sell", "academy_research",
                         "tavern_cities", "miracle_temple", "olympus_shrine",
                     } for field in fields))):
            self.cities_requested.emit(account_id)

    def _update_native_visibility(self, *_args: object) -> None:
        """Hide irrelevant options in multi-mode upstream planners."""
        name = self.selected_task_name()
        visible: dict[str, bool] = {}
        if name == "autoPirate":
            schedule = self._form_inputs.get("pirateSchedule")
            active = isinstance(schedule, CheckBox) and schedule.isChecked()
            visible["pirateMissionChoice"] = not active
            for key in ("pirateMissionDayChoice", "pirateMissionNightChoice",
                        "dayStart", "dayEnd", "nightStart", "nightEnd"):
                visible[key] = active
        elif name == "activateShrine":
            mode = self._form_inputs.get("mode")
            visible["times"] = not (isinstance(mode, ComboBox)
                                    and mode.currentIndex() == 1)
        elif name == "resourceTransportManager":
            mode = self._form_inputs.get("mode")
            index = mode.currentIndex() if isinstance(mode, ComboBox) else -1
            for key in ("origin_cities", "destination_city", "send_mode"):
                visible[key] = index == 0
            for key in ("origin_city", "destination_cities"):
                visible[key] = index == 1
            visible["island"] = False  # external routes require separate verified location
        for key, show in visible.items():
            widget = self._form_inputs.get(key)
            if widget is None:
                continue
            widget.setVisible(show)
            label = self.parameter_layout.labelForField(widget)
            if label is not None:
                label.setVisible(show)
        self._mark_form_dirty()

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
                # Construction is assembled only by the engine preview.
                continue
            kind = str(field["type"])
            if kind == "hidden_derived":
                continue
            if kind == "json":
                if field["required"]:
                    raise ValueError("This action needs a dedicated native editor before it can start")
                # An optional opaque game value is intentionally left unset.
                continue
            if name == "autoPirate":
                schedule_widget = self._form_inputs.get("pirateSchedule")
                scheduled = isinstance(schedule_widget, CheckBox) and schedule_widget.isChecked()
                if (key in {"pirateMissionChoice"} and scheduled
                        or key in {"pirateMissionDayChoice", "pirateMissionNightChoice",
                                   "dayStart", "dayEnd", "nightStart", "nightEnd"}
                        and not scheduled):
                    continue
            if name == "activateShrine" and key == "times":
                mode_widget = self._form_inputs.get("mode")
                if isinstance(mode_widget, ComboBox) and mode_widget.currentIndex() == 1:
                    continue
            if name == "resourceTransportManager":
                mode_widget = self._form_inputs.get("mode")
                index = mode_widget.currentIndex() if isinstance(mode_widget, ComboBox) else -1
                if (key in {"origin_cities", "destination_city", "send_mode"} and index != 0
                        or key in {"origin_city", "destination_cities"} and index != 1
                        or key == "island"):
                    continue
            widget = self._form_inputs[key]
            if isinstance(widget, ExternalDestinationEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, BarbarianWavesEditor):
                config[key] = widget.to_config()
                continue
            if isinstance(widget, ResourceLimitsEditor):
                config[key] = widget.to_config()
                continue
            if isinstance(widget, ShipmentRoutesEditor):
                config[key] = widget.to_config()
                continue
            if isinstance(widget, PiracyMissionsEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, OlympusShrineEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, MiracleTempleEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, TavernCitiesEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, AcademyResearchEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, MarketOffersEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, TrainableUnitsEditor):
                config.update(widget.to_config())
                continue
            if isinstance(widget, WorkshopUpgradesEditor):
                config[key] = widget.to_config()
                continue
            if isinstance(widget, DonationPoliciesEditor):
                method_widget = self._form_inputs.get("donate_method")
                idx = method_widget.currentIndex() if isinstance(method_widget, ComboBox) else -1
                if idx < 0:
                    raise ValueError("Choose a donation method")
                config[key] = widget.to_config([1, 2, 3][idx])
                continue
            if isinstance(widget, ResourceAmountsEditor):
                mode_widget = self._form_inputs.get("send_mode")
                keep = (name == "resourceTransportManager"
                        and isinstance(mode_widget, ComboBox)
                        and mode_widget.currentIndex() == 0)
                config[key] = widget.to_config(ignore_allowed=keep)
                continue
            if isinstance(widget, MapAreaEditor):
                area = widget.to_config()
                if area is not None:
                    config[key], config["radius"] = area
                continue
            if isinstance(widget, QListWidget):
                chosen = [widget.item(i).data(Qt.UserRole)
                          for i in range(widget.count())
                          if widget.item(i).checkState() == Qt.Checked]
                if not chosen:
                    if field["required"] and kind != "island_list":
                        raise ValueError(f"Choose at least one option for {key}")
                    continue
                if name == "distributeResources" and kind == "city_list" and len(chosen) < 2:
                    raise ValueError("Choose at least two cities to distribute resources")
                config[key] = ([str(city) for city in chosen] if kind == "city_list"
                               else chosen)
                continue
            if kind == "build_choice" and isinstance(widget, ComboBox):
                selected = widget.currentData()
                if not isinstance(selected, dict) or set(selected) != {"position", "building_id"}:
                    raise ValueError("Choose a verified building option")
                config.update(selected)
                continue
            if kind == "city_picker" and isinstance(widget, ComboBox):
                cities = self._cities_by_account.get(self.selected_account_id() or "", [])
                index = widget.currentIndex()
                if 1 <= index <= len(cities):
                    config[key] = cities[index - 1]["id"]
                elif field["required"]:
                    raise ValueError(f"Select an actual city for {key}")
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
                if field.get("omit_zero") is True and value == 0:
                    continue
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
        if (name == "research" and type(config.get("qty")) is int and config["qty"] > 0
                and len(config.get("cities_ids", [])) != 1):
            raise ValueError("Choose exactly one academy city for a fixed number of experiments")
        if name == "consolidateResources":
            destination = config.get("destinationCityId")
            if destination is not None and str(destination) in config.get("sourceCityIds", []):
                raise ValueError("Destination cannot also be a source city")
        if name == "resourceTransportManager":
            if "mode" not in config:
                raise ValueError("Choose a transport strategy")
            if config["mode"] == "consolidate":
                if not config.get("origin_cities") or config.get("destination_city") is None:
                    raise ValueError("Choose source cities and a receiving city")
                if str(config["destination_city"]) in config["origin_cities"]:
                    raise ValueError("Destination cannot also be a source city")
                config["origin_cities"] = [int(c) for c in config["origin_cities"]]
        if name == "dumpWorld" and config.get("shallow") is True and "coords" in config:
            raise ValueError("Whole-world shallow scans cannot be limited to a map area")
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
        if name == "stationArmy":
            for option in ("all_origins", "both"):
                if not config.get(option):
                    config.pop(option, None)
            if config.get("both"):
                config["ground"] = True
        if name in WORKER_TASKS and "additional_city_ids" in config:
            config["additional_city_ids"] = [int(cid) for cid in config["additional_city_ids"]
                                             if int(cid) != config["city_id"]]
            if not config["additional_city_ids"]:
                config.pop("additional_city_ids")
        return config

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
             str(task.get("status", "unknown")).replace("_", " ").capitalize() + (
                 " · " + str(task["outcome"]).replace("_", " ") if task.get("outcome") in
                 {"accepted", "failed_or_uncertain"} else ""),
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
            and self.selected_task_name() != "webServer"
            and (self.selected_task_name() not in CITY_REVIEW_TASKS or self._city_review_plan is not None)
            # A native editor must cover all required structured parameters.
            and (self.selected_task_name() == "constructionList"
                 or not expert_configuration_needed(
                     self._config_fields_by_task.get(self.selected_task_name() or "", [])))
            and (self.selected_task_name() != "constructionList"
                 or self._construction_preview_ready)
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
        self._update_review_queue_controls()

    def _refresh(self) -> None:
        account_id = self.selected_account_id()
        if account_id:
            self.refresh_requested.emit(account_id)

    def _account_description(self, account_id: str) -> str:
        record = next(
            (a for a in self._all_account_metadata if a["id"] == account_id),
            {},
        )
        label = account_player_name(record or {"id": account_id})
        world = str(record.get("world") or "world unspecified")
        return f"{label} · {world} (account {account_id})"

    def _start(self) -> None:
        account_id = self.selected_account_id()
        task = self.selected_task_name()
        if (not self._dispatch_enabled or account_id is None or task is None
                or self._pending_launch or not self.start_button.isEnabled()):
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
            if task in CITY_REVIEW_TASKS:
                if self._city_review_plan is None or time.monotonic() >= self._city_review_expires:
                    raise ValueError("Operation preview expired; prepare a new preview")
                draft = self._form_inputs["city"].reviewed_draft() if task == "trainArmy" else self._form_config()
                if any(self._city_review_plan.get(key) != value for key, value in draft.items()):
                    raise ValueError("Operation settings changed; prepare a new preview")
                config = {"preview_id": self._city_review_plan["preview_id"]}
            elif task == "constructionList":
                if not self._construction_preview_ready or self._construction_prepared is None:
                    raise ValueError("Calculate and approve the actual IkaBot construction preview first")
                if self._construction_ticket is not None:
                    key, expires = self._construction_ticket
                    if time.monotonic() >= expires:
                        raise ValueError("Construction review expired; prepare a new preview")
                    config = {"preview_id": key}
                else:
                    config = dict(self._construction_prepared)
            else:
                config = self._form_config()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Invalid automation settings", str(exc))
            return
        params = self.building_note.text() if task in CITY_REVIEW_TASKS | {"constructionList"} else configuration_summary(config)
        if task == "resourceTransportManager" and config.get("mode") == "consolidate":
            editor = self._form_inputs.get("destination_city")
            names = {c["id"]:c["name"] for c in self._cities_by_account.get(account_id, [])}
            params = (", ".join(names[c] for c in config["origin_cities"]) + " → "
                      + editor.picker.currentText() + "\n"
                      + ("Keep reserve: " if config.get("send_mode") == "keep" else "Send: ")
                      + ", ".join(f"{n} {v:,}" for n,v in zip(
                          ("wood","wine","marble","crystal","sulfur"),config["resource_config"]) if v is not None)
                      + f"\nRepeat every {config['interval_hours']} hours; "
                      + ("freighters" if config.get("useFreighters") else "trade ships")
                      + f"; notifications: {config.get('notify','none')}"
                      + ("\nExternal shipments require manual recovery." if "recipient" in config else ""))
        if task in {"testTelegramBot", "testDiscordBot"}:
            params = "Send one fixed test message to the existing configured provider. Check task Activity for acceptance."
        answer = QMessageBox.question(
            self, "Review automation",
            f"Start {_friendly_task(task)} for "
            f"{self._account_description(account_id)}?\n\n"
            f"Settings: {params if task in {'sendResources', 'stationArmy', 'trainArmy', 'constructionList'} | WORKER_TASKS else params[:600]}\n\n"
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
        if task in CITY_REVIEW_TASKS:
            self._city_review_plan = None
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
