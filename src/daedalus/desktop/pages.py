"""Native Fluent pages built from the existing Mac GUI's design vocabulary.

These pages never contact Ikariam or store authentication secrets. The main
window feeds them typed data from the Daedalus backend API.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidgetItem,
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

from daedalus.desktop.widgets import ScrollTableWidget
from daedalus.reporting import RESOURCES, report_csv, report_json, rows_for_warehouse


def _table(headers: list[str]) -> ScrollTableWidget:
    table = ScrollTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setBorderVisible(True)
    table.setBorderRadius(8)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setEditTriggers(ScrollTableWidget.NoEditTriggers)
    table.setSelectionBehavior(ScrollTableWidget.SelectRows)
    return table


def _populate(table: ScrollTableWidget, rows: list[list[object]]) -> None:
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            label = "—" if value is None else str(value)
            table.setItem(row_index, column_index, QTableWidgetItem(label))


class ConnectionPage(QWidget):
    connect_requested = Signal(str, str)
    reconnect_requested = Signal()
    forget_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("connection_page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Connection"))
        layout.addWidget(
            CaptionLabel(
                "Connect to the local API or an HTTPS/SSH-tunneled remote server. "
                "Bearer token stays in process memory only."
            )
        )
        layout.addWidget(BodyLabel("Backend URL"))
        self.url_input = LineEdit()
        self.url_input.setText("http://127.0.0.1:8765")
        self.url_input.setPlaceholderText("http://127.0.0.1:8765")
        # Private URL metadata is optional; malformed settings cannot prevent launch.
        from daedalus.connection_prefs import PreferenceError, load_connection_url

        try:
            saved_url = load_connection_url()
        except PreferenceError:
            saved_url = None
        if saved_url is not None:
            self.url_input.setText(saved_url)
        layout.addWidget(self.url_input)
        layout.addWidget(BodyLabel("API bearer token"))
        self.token_input = LineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("Paste the token from your local backend")
        layout.addWidget(self.token_input)
        self.connect_button = PrimaryPushButton("Connect")
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)

        self.remember_checkbox = CheckBox("Remember URL and token in OS keychain")
        self.remember_checkbox.setToolTip(
            "Off by default. URL is stored in owner-only local settings; the token uses OS keyring."
        )
        self.remember_checkbox.setChecked(saved_url is not None)
        layout.addWidget(self.remember_checkbox)

        connection_actions = QHBoxLayout()
        self.reconnect_button = PushButton("Reconnect")
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)
        self.forget_button = PushButton("Forget saved connection")
        self.forget_button.clicked.connect(self.forget_requested.emit)
        connection_actions.addWidget(self.reconnect_button)
        connection_actions.addWidget(self.forget_button)
        layout.addLayout(connection_actions)
        self.status_label = CaptionLabel("Not connected")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _connect(self) -> None:
        self.connect_requested.emit(self.url_input.text().strip(), self.token_input.text())

    def set_connected(self, connected: bool) -> None:
        self.status_label.setText("Connected to Daedalus backend" if connected else "Not connected")
        if connected:
            self.token_input.clear()


class AccountsPage(QWidget):
    refresh_requested = Signal()
    check_engine_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("accounts_page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("Accounts"))
        header.addStretch(1)
        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_button)
        self.check_engine_button = PushButton("Check IkaBot sessions")
        self.check_engine_button.clicked.connect(self.check_engine_requested.emit)
        header.addWidget(self.check_engine_button)
        layout.addLayout(header)
        layout.addWidget(CaptionLabel(
            "Read-only account status. IkaBot sessions are checked only when requested."
        ))
        self._accounts: list[dict[str, object]] = []
        self._connected_ids: set[str] | None = None
        self.table = _table(["Account", "World", "Player", "Enabled", "Session", "IkaBot"])
        layout.addWidget(self.table, 1)

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        self._accounts = accounts
        self._render()

    def set_connected_ids(self, account_ids: list[str]) -> None:
        self._connected_ids = set(account_ids)
        self._render()

    def _render(self) -> None:
        _populate(
            self.table,
            [
                [
                    acc.get("label") or acc.get("id"),
                    acc.get("world"),
                    acc.get("player"),
                    "Yes" if acc.get("enabled") else "No",
                    acc.get("session_status") or "not_connected",
                    "Not checked" if self._connected_ids is None else (
                        "Attached" if acc.get("id") in self._connected_ids else "Not attached"
                    ),
                ]
                for acc in self._accounts
            ],
        )


class OperationsPage(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("operations_page")
        self._operations: list[dict[str, object]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("IkaBot operations"))
        header.addStretch(1)
        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)
        self.status_label = CaptionLabel(
            "Read-only inventory. Task execution will be enabled after worker integration."
        )
        layout.addWidget(self.status_label)
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("Filter operations by name or module")
        self.search_input.textChanged.connect(self._render)
        layout.addWidget(self.search_input)
        self.table = _table(["Operation", "Kind", "Module", "Parameters"])
        layout.addWidget(self.table, 1)

    def set_operations(self, operations: list[dict[str, object]]) -> None:
        self._operations = operations
        self._render()

    def _render(self, *_args: object) -> None:
        search = self.search_input.text().casefold()
        filtered = [
            item
            for item in self._operations
            if search in str(item.get("name", "")).casefold()
            or search in str(item.get("module", "")).casefold()
        ]
        _populate(
            self.table,
            [
                [
                    item.get("name") or "",
                    item.get("kind") or "",
                    item.get("module") or "",
                    ", ".join(str(value) for value in (item.get("parameters") or [])),
                ]
                for item in filtered
            ],
        )


class WarehousesPage(QWidget):
    load_requested = Signal(str)

    _COLUMNS = ("City", "World", *RESOURCES, "Capacity", "Captured", "Incomplete")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("warehouses_page")
        self._account_ids: list[str] = []
        self._accounts: dict[str, dict[str, object]] = {}
        self._selected_account: dict[str, object] = {}
        self._snapshots: list[dict[str, object]] = []
        self._rows: list[dict[str, object]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Warehouses"))
        layout.addWidget(
            CaptionLabel(
                "Unsecured resources from the IkaBot session. Unknown values display as —, not zero."
            )
        )

        controls = QHBoxLayout()
        controls.addWidget(BodyLabel("Account"))
        self.account_combo = ComboBox()
        controls.addWidget(self.account_combo, 1)
        self.load_button = PrimaryPushButton("Load warehouses")
        self.load_button.clicked.connect(self._load)
        controls.addWidget(self.load_button)
        self.only_220k = CheckBox("Only 220K+")
        self.only_220k.setToolTip(
            "Show cities with at least 220,000 known unsecured resources in total"
        )
        self.only_220k.stateChanged.connect(self._render)
        controls.addWidget(self.only_220k)
        layout.addLayout(controls)

        self.status_label = CaptionLabel("No warehouse snapshots loaded")
        layout.addWidget(self.status_label)
        self.table = _table(list(self._COLUMNS))
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.copy_button = PushButton("Copy CSV")
        self.copy_button.clicked.connect(self._copy_csv)
        self.csv_button = PushButton("Save CSV")
        self.csv_button.clicked.connect(lambda: self._save("csv"))
        self.json_button = PushButton("Save JSON")
        self.json_button.clicked.connect(lambda: self._save("json"))
        for button in (self.copy_button, self.csv_button, self.json_button):
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        previous = self.selected_account_id()
        self._accounts = {str(account["id"]): account for account in accounts if account.get("id")}
        self._account_ids = list(self._accounts)
        self.account_combo.clear()
        for account in self._accounts.values():
            self.account_combo.addItem(str(account.get("label") or account.get("player") or account["id"]))
        if previous in self._account_ids:
            self.account_combo.setCurrentIndex(self._account_ids.index(previous))

    def selected_account_id(self) -> str | None:
        index = self.account_combo.currentIndex()
        return self._account_ids[index] if 0 <= index < len(self._account_ids) else None

    def _load(self) -> None:
        account_id = self.selected_account_id()
        if account_id is not None:
            self.load_requested.emit(account_id)

    def set_snapshots(self, account_id: str, snapshots: list[dict[str, object]]) -> None:
        self._selected_account = self._accounts.get(account_id, {"id": account_id})
        self._snapshots = snapshots
        self._render()

    def _render(self, *_args: object) -> None:
        self._rows = rows_for_warehouse(
            self._selected_account, self._snapshots, only_220k=self.only_220k.isChecked()
        )
        _populate(
            self.table,
            [
                [
                    row.get("city"),
                    row.get("world"),
                    *(row.get(name) for name in RESOURCES),
                    row.get("capacity"),
                    row.get("captured_at"),
                    "Yes" if row.get("incomplete") else "No",
                ]
                for row in self._rows
            ],
        )
        self.status_label.setText(f"{len(self._rows)} cities shown")
        for button in (self.copy_button, self.csv_button, self.json_button):
            button.setEnabled(bool(self._rows))

    def _copy_csv(self) -> None:
        QGuiApplication.clipboard().setText(report_csv(self._rows))

    def _save(self, format_name: str) -> None:
        suffix = ".csv" if format_name == "csv" else ".json"
        filename, _selected = QFileDialog.getSaveFileName(
            self, "Save warehouse report", f"daedalus-warehouses{suffix}"
        )
        if not filename:
            return
        output = report_csv(self._rows) if format_name == "csv" else report_json(self._rows)
        with open(filename, "w", encoding="utf-8", newline="") as handle:
            handle.write(output)
