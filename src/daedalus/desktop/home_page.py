"""Account-first Daedalus home: easy navigation, no new game operations.

All values originate from nonsecret, already-authorized backend account metadata.
The home page never sees a Gameforge token or starts a worker/task itself.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.design_system import PageHeading


class _ActionCard(CardWidget):
    def __init__(self, title: str, subtitle: str, button: str, action, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(146)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)
        label = SubtitleLabel(title)
        layout.addWidget(label)
        description = CaptionLabel(subtitle)
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addStretch(1)
        self.open_button = PushButton(button)
        self.open_button.clicked.connect(action)
        layout.addWidget(self.open_button)


class HomePage(QWidget):
    """Prominent account selector and task-oriented entry points."""

    view_warehouses = Signal(str)
    view_all_warehouses = Signal()
    view_all_automations = Signal()
    manage_automations = Signal(str)
    manage_accounts = Signal()
    connect_backend = Signal()
    account_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("home_page")
        self._accounts: list[dict[str, object]] = []
        self._account_ids: list[str] = []
        self._connected = False
        self._demo = False

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setFrameShape(QScrollArea.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        content = QWidget(self.content_scroll)
        self.content_scroll.setWidget(content)
        shell.addWidget(self.content_scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 28)
        layout.setSpacing(18)
        layout.addWidget(PageHeading(
            "Overview",
            "Everything you need for your accounts, reports and automations.",
            self,
        ))

        overview = CardWidget(self)
        overview_row = QVBoxLayout(overview)
        overview_row.setContentsMargins(20, 15, 20, 15)
        overview_row.setSpacing(10)
        self.connection_status = SubtitleLabel("Not connected")
        overview_row.addWidget(self.connection_status)
        self.account_summary = CaptionLabel("Connect to load your game accounts.")
        overview_row.addWidget(self.account_summary)
        account_row = QHBoxLayout()
        account_row.addWidget(BodyLabel("Active account"))
        self.account_combo = ComboBox()
        self.account_combo.setMinimumWidth(230)
        self.account_combo.currentIndexChanged.connect(self._selection_changed)
        account_row.addWidget(self.account_combo, 1)
        self.connection_button = PushButton("Connection settings")
        self.connection_button.clicked.connect(self.connect_backend.emit)
        account_row.addWidget(self.connection_button)
        overview_row.addLayout(account_row)
        self.selected_status = CaptionLabel("Select a connected account to view live data.")
        overview_row.addWidget(self.selected_status)
        layout.addWidget(overview)

        layout.addWidget(SubtitleLabel("Quick actions"))
        self.actions = QGridLayout()
        self.actions.setSpacing(14)
        self.warehouse_card = _ActionCard(
            "Warehouses", "See the resources in your cities. Viewing does not change your game.",
            "View warehouses", self._open_warehouses, self,
        )
        self.automation_card = _ActionCard(
            "Automations", "Set up tasks with guided controls and review them before starting.",
            "Manage automations", self._open_automations, self,
        )
        self.accounts_card = _ActionCard(
            "Accounts", "See connection and recovery status for your worlds.",
            "View accounts", self.manage_accounts.emit, self,
        )
        self.all_warehouse_card = _ActionCard(
            "All account warehouses",
            "Combine all warehouses into one report, with island grouping and exports.",
            "Load all warehouses", self.view_all_warehouses.emit, self,
        )
        self.all_automation_card = _ActionCard(
            "All account activity",
            "Check running tasks and requests across every account without starting anything.",
            "View all task status", self.view_all_automations.emit, self,
        )
        self.actions.addWidget(self.warehouse_card, 0, 0)
        self.actions.addWidget(self.all_warehouse_card, 0, 1)
        self.actions.addWidget(self.automation_card, 1, 0)
        self.actions.addWidget(self.all_automation_card, 1, 1)
        self.actions.addWidget(self.accounts_card, 2, 0)
        layout.addLayout(self.actions)
        self.help_text = CaptionLabel(
            "Automations only start after you review and confirm them. "
            "The Operations catalog is a reference list, not a Start button."
        )
        self.help_text.setWordWrap(True)
        layout.addWidget(self.help_text)
        layout.addStretch(1)
        self._update_controls()

    def selected_account_id(self) -> str | None:
        position = self.account_combo.currentIndex()
        if 0 <= position < len(self._account_ids):
            return self._account_ids[position]
        return None

    def set_connected(self, connected: bool, *, demo: bool = False) -> None:
        self._connected = connected
        self._demo = demo
        self._update_controls()

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        before = self.selected_account_id()
        self._accounts = [dict(a) for a in accounts if a.get("id") and a.get("enabled")]
        self._account_ids = [str(a["id"]) for a in self._accounts]
        self.account_combo.blockSignals(True)
        try:
            self.account_combo.clear()
            for account in self._accounts:
                self.account_combo.addItem(
                    str(account.get("label") or account.get("player") or account["id"])
                )
            if before in self._account_ids:
                self.account_combo.setCurrentIndex(self._account_ids.index(before))
            else:
                preferred = next((i for i, account in enumerate(self._accounts)
                    if account.get("session_status") == "authenticated"), 0)
                if self._account_ids:
                    self.account_combo.setCurrentIndex(preferred)
        finally:
            self.account_combo.blockSignals(False)
        self._update_controls()
        self._selection_changed()

    def select_account(self, account_id: str) -> None:
        if account_id in self._account_ids:
            self.account_combo.setCurrentIndex(self._account_ids.index(account_id))

    def _selection_changed(self, *_args: object) -> None:
        self._update_controls()
        account_id = self.selected_account_id()
        if account_id is not None:
            self.account_selected.emit(account_id)

    def _update_controls(self) -> None:
        if not self._connected:
            self.connection_status.setText("Connect to your Daedalus server")
            self.account_summary.setText("Your game accounts and tasks will appear here.")
        else:
            connected_count = sum(
                a.get("session_status") == "authenticated" for a in self._accounts
            )
            self.connection_status.setText(
                "Offline preview connected" if self._demo else "Backend connected"
            )
            self.account_summary.setText(
                f"{len(self._accounts)} accounts  ·  "
                f"{connected_count} authenticated sessions"
            )
        account_id = self.selected_account_id()
        selected = next((a for a in self._accounts if str(a["id"]) == account_id), None)
        status = str(selected.get("session_status", "not_connected")) if selected else "not_connected"
        self.selected_status.setText({
            "authenticated": "Ready: live account session verified",
            "needs_assistance": "Sign-in needed: open Accounts for recovery help",
            "paused": "Paused: check the session in Accounts",
            "not_connected": "Not connected: select a verified account",
            "disabled": "Disabled in backend account settings",
        }.get(status, "Status: " + status.replace("_", " ")))
        ready = bool(self._connected and selected)
        self.account_combo.setEnabled(ready)
        self.warehouse_card.open_button.setEnabled(ready and status == "authenticated")
        self.automation_card.open_button.setEnabled(ready and status == "authenticated")
        self.accounts_card.open_button.setEnabled(self._connected)
        self.all_warehouse_card.open_button.setEnabled(
            self._connected and bool(self._accounts)
        )
        self.all_automation_card.open_button.setEnabled(
            self._connected and bool(self._accounts)
        )

    def _open_warehouses(self) -> None:
        if (account_id := self.selected_account_id()) is not None:
            self.view_warehouses.emit(account_id)

    def _open_automations(self) -> None:
        if (account_id := self.selected_account_id()) is not None:
            self.manage_automations.emit(account_id)
