"""Native Fluent pages built from the existing Mac GUI's design vocabulary.

These pages never contact Ikariam or store authentication secrets. The main
window feeds them typed data from the Daedalus backend API.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
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
from daedalus.reporting import RESOURCES, report_csv, report_json, report_txt, rows_for_warehouse


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

    def set_connected(self, connected: bool, *, demo: bool = False) -> None:
        self.status_label.setText(
            "SYNTHETIC DEMO connected — no real game accounts or sessions"
            if connected and demo else
            "Connected to Daedalus backend" if connected else "Not connected"
        )
        if connected:
            self.token_input.clear()


class AccountsPage(QWidget):
    refresh_requested = Signal()
    check_engine_requested = Signal()
    account_change_requested = Signal(str, object)
    assistance_check_requested = Signal(str)
    assistance_approve_requested = Signal(str, str)
    monitor_requested = Signal(str)

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
        self._edit_revision: str | None = None
        self._editable_accounts: list[dict[str, object]] = []
        self.table = _table(["Account", "World", "Player", "Enabled", "Session", "IkaBot"])
        layout.addWidget(self.table, 1)
        editor_actions = QHBoxLayout()
        self.create_button = PushButton("Add account")
        self.edit_button = PushButton("Edit selected")
        self.toggle_button = PushButton("Enable / Disable")
        self.remove_button = PushButton("Remove selected")
        for button, callback in (
            (self.create_button, self._create),
            (self.edit_button, self._edit),
            (self.toggle_button, self._toggle),
            (self.remove_button, self._remove),
        ):
            button.clicked.connect(callback)
            button.setEnabled(False)
            editor_actions.addWidget(button)
        editor_actions.addStretch(1)
        layout.addLayout(editor_actions)
        self.editor_status = CaptionLabel("Account editing is disabled on this backend")
        layout.addWidget(self.editor_status)
        assistance_actions = QHBoxLayout()
        self.assistance_check_button = PushButton("Check login assistance")
        self.assistance_approve_button = PushButton("Confirm manual step complete")
        self.assistance_check_button.clicked.connect(self._check_assistance)
        self.assistance_approve_button.clicked.connect(self._approve_assistance)
        self.assistance_check_button.setEnabled(False)
        self.assistance_approve_button.setEnabled(False)
        self._assistance_account_id: str | None = None
        self._assistance_ticket: dict[str, object] | None = None
        self.table.itemSelectionChanged.connect(self._update_assistance_buttons)
        assistance_actions.addWidget(self.assistance_check_button)
        assistance_actions.addWidget(self.assistance_approve_button)
        assistance_actions.addStretch(1)
        layout.addLayout(assistance_actions)
        self.assistance_status = CaptionLabel("Select an account to check for manual help")
        layout.addWidget(self.assistance_status)
        self._monitor_enabled = False
        self.monitor_button = PushButton("Monitor verified session")
        self.monitor_button.clicked.connect(self._monitor_selected)
        self.monitor_button.setEnabled(False)
        layout.addWidget(self.monitor_button)
        self.monitor_status = CaptionLabel("Existing-session monitoring is disabled")
        layout.addWidget(self.monitor_status)

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        self._accounts = accounts
        self._assistance_ticket = None
        self._assistance_account_id = None
        self._render()
        self._update_assistance_buttons()

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

    def _selected_visible_id(self) -> str | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._accounts):
            selected = self._accounts[index].get("id")
            if isinstance(selected, str):
                return selected
        return None

    def _update_assistance_buttons(self) -> None:
        account_id = self._selected_visible_id()
        self.assistance_check_button.setEnabled(account_id is not None)
        self.monitor_button.setEnabled(self._monitor_enabled and account_id is not None)
        ticket = self._assistance_ticket
        self.assistance_approve_button.setEnabled(
            account_id is not None
            and account_id == self._assistance_account_id
            and isinstance(ticket, dict)
            and ticket.get("state") == "waiting_operator"
        )

    def set_assistance(self, data: dict[str, object]) -> None:
        account_id = data.get("account_id")
        if not isinstance(account_id, str):
            return
        ticket = data.get("ticket")
        self._assistance_account_id = account_id
        self._assistance_ticket = ticket if isinstance(ticket, dict) else None
        if data.get("enabled") is not True:
            label = "Login assistance is not enabled on this backend"
        elif self._assistance_ticket is None:
            label = "No pending manual login assistance for this account"
        else:
            reason = str(self._assistance_ticket.get("reason", ""))
            state = str(self._assistance_ticket.get("state", ""))
            label = f"Login assistance: {reason} — {state}"
        self.assistance_status.setText(label)
        self._update_assistance_buttons()

    def set_monitoring_enabled(self, enabled: bool) -> None:
        self._monitor_enabled = enabled
        self.monitor_status.setText(
            "Verified session monitoring enabled; no new game login is started"
            if enabled else "Existing-session monitoring is disabled"
        )
        self._update_assistance_buttons()

    def _monitor_selected(self) -> None:
        account_id = self._selected_visible_id()
        if not self._monitor_enabled or account_id is None:
            return
        if QMessageBox.question(
            self, "Monitor verified existing IkaBot session",
            "This explicitly checks the existing account session with a read-only game request "
            "and holds its local Daedalus ownership lease. No login is created. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            self.monitor_requested.emit(account_id)

    def _check_assistance(self) -> None:
        account_id = self._selected_visible_id()
        if account_id is not None:
            self.assistance_check_requested.emit(account_id)

    def _approve_assistance(self) -> None:
        account_id = self._selected_visible_id()
        ticket = self._assistance_ticket
        if (
            account_id is None or account_id != self._assistance_account_id
            or not isinstance(ticket, dict) or ticket.get("state") != "waiting_operator"
        ):
            return
        ticket_id = ticket.get("ticket_id")
        if not isinstance(ticket_id, str):
            return
        if QMessageBox.question(
            self, "Confirm manual login step",
            "Confirm only that you finished the manual step in the trusted browser. "
            "The game worker still must independently validate authentication.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            self.assistance_approve_requested.emit(account_id, ticket_id)

    def set_editable_config(self, data: dict[str, object]) -> None:
        """Enable editing only after the authenticated backend opts in."""
        enabled = (
            data.get("enabled") is True
            and isinstance(data.get("revision"), str)
            and isinstance(data.get("accounts"), list)
        )
        self._edit_revision = str(data["revision"]) if enabled else None
        self._editable_accounts = [
            dict(row) for row in data["accounts"] if isinstance(row, dict)
        ] if enabled else []
        for button in (
            self.create_button, self.edit_button, self.toggle_button, self.remove_button,
        ):
            button.setEnabled(enabled)
        self.editor_status.setText(
            "Metadata-only editing enabled; changes require confirmation"
            if enabled else "Account editing is disabled on this backend"
        )

    def _selected_account(self) -> tuple[int, dict[str, object]] | None:
        index = self.table.currentRow()
        if index < 0 or index >= len(self._accounts):
            return None
        account_id = self._accounts[index].get("id")
        for position, item in enumerate(self._editable_accounts):
            if item.get("id") == account_id:
                return position, item
        return None

    def _metadata_dialog(
        self, existing: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit account metadata" if existing else "Add account metadata")
        layout = QFormLayout(dialog)
        fields = {}
        for key, title in (
            ("id", "Account ID"), ("world", "World"), ("player", "Player"), ("label", "Label"),
        ):
            widget = QLineEdit(dialog)
            widget.setText(str(existing.get(key, "")) if existing else "")
            fields[key] = widget
            layout.addRow(title, widget)
        enabled = CheckBox("Enabled")
        enabled.setChecked(bool(existing.get("enabled", True)) if existing else True)
        layout.addRow(enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        result: dict[str, object] = {key: field.text().strip() for key, field in fields.items()}
        result["enabled"] = enabled.isChecked()
        if any(not result[key] for key in fields):
            QMessageBox.warning(self, "Incomplete account", "All account fields are required.")
            return None
        return result

    def _propose(self, rows: list[dict[str, object]], message: str) -> None:
        if self._edit_revision is None:
            return
        if QMessageBox.question(
            self, "Confirm account metadata change",
            message + "\n\nOnly account metadata will change; no game login is performed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.account_change_requested.emit(self._edit_revision, rows)

    def _create(self) -> None:
        if self._edit_revision is None:
            return
        new = self._metadata_dialog()
        if new is not None:
            self._propose([*self._editable_accounts, new], "Add this account?")

    def _edit(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        index, existing = selected
        edited = self._metadata_dialog(existing)
        if edited is not None:
            rows = [dict(row) for row in self._editable_accounts]
            rows[index] = edited
            self._propose(rows, "Save changes to the selected account?")

    def _toggle(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        index, existing = selected
        rows = [dict(row) for row in self._editable_accounts]
        rows[index]["enabled"] = not bool(existing.get("enabled"))
        self._propose(rows, "Change the selected account's enabled state?")

    def _remove(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        index, _ = selected
        rows = [dict(row) for i, row in enumerate(self._editable_accounts) if i != index]
        self._propose(rows, "Remove the selected account metadata record?")


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

    _COLUMNS = ("City", "Island", "World", *RESOURCES, "Capacity", "Captured", "Incomplete")

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
        self.demo_note = CaptionLabel("")
        layout.addWidget(self.demo_note)
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
        self.group_island = CheckBox("Group by island")
        self.group_island.setToolTip("Order rows by existing city island coordinates")
        self.group_island.stateChanged.connect(self._render)
        controls.addWidget(self.group_island)
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
        self.txt_button = PushButton("Save TXT")
        self.txt_button.clicked.connect(lambda: self._save("txt"))
        for button in (self.copy_button, self.csv_button, self.json_button, self.txt_button):
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

    def set_demo(self, enabled: bool) -> None:
        self.demo_note.setText(
            "SYNTHETIC DEMO — sample amounts only; no real account resources"
            if enabled else ""
        )

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
        if self.group_island.isChecked():
            self._rows.sort(key=lambda row: (
                row.get("island") is None,
                str(row.get("island") or ""),
                str(row.get("city") or ""),
            ))
        _populate(
            self.table,
            [
                [
                    row.get("city"),
                    row.get("island"),
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
        for button in (self.copy_button, self.csv_button, self.json_button, self.txt_button):
            button.setEnabled(bool(self._rows))

    def _copy_csv(self) -> None:
        QGuiApplication.clipboard().setText(report_csv(self._rows))

    def _save(self, format_name: str) -> None:
        if format_name not in {"csv", "json", "txt"}:
            raise ValueError("Unsupported warehouse export format")
        suffix = {"csv": ".csv", "json": ".json", "txt": ".txt"}[format_name]
        filename, _selected = QFileDialog.getSaveFileName(
            self, "Save warehouse report", f"daedalus-warehouses{suffix}"
        )
        if not filename:
            return
        output = (
            report_csv(self._rows) if format_name == "csv"
            else report_json(self._rows) if format_name == "json"
            else report_txt(self._rows, group_by_island=self.group_island.isChecked())
        )
        with open(filename, "w", encoding="utf-8", newline="") as handle:
            handle.write(output)
