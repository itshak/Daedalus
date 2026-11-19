"""Native Fluent pages built from the existing Mac GUI's design vocabulary.

These pages never contact Ikariam or store authentication secrets. The main
window feeds them typed data from the Daedalus backend API.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
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

from daedalus.desktop.design_system import StatusPanel
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
    overview_requested = Signal()
    ssh_connect_requested = Signal(str, str)
    demo_requested = Signal()
    reconnect_requested = Signal()
    forget_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("connection_page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(13)
        layout.addWidget(SubtitleLabel("Connect to Daedalus"))
        intro = CaptionLabel(
            "Connect securely over HTTPS. No SSH tunnel, Terminal or manual "
            "port forwarding is needed. Your server stays in control of game sessions."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(BodyLabel("Server address"))
        self.url_input = LineEdit()
        self.url_input.setPlaceholderText("https://your-daedalus-server.example")
        # First run must not imply a backend runs on the Mac. A saved, exact
        # HTTPS origin is restored below when the user previously approved it.
        self.url_input.setText("")
        from daedalus.connection_prefs import PreferenceError, load_connection_url

        try:
            saved_url = load_connection_url()
        except PreferenceError:
            saved_url = None
        if saved_url is not None:
            self.url_input.setText(saved_url)
        layout.addWidget(self.url_input)

        layout.addWidget(BodyLabel("API access token"))
        self.token_input = LineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("Paste your API token once")
        layout.addWidget(self.token_input)
        tip = CaptionLabel(
            "Daedalus API token, not a Gameforge lobby token. After the first "
            "successful connection the token is kept securely in your Mac Keychain."
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.remember_checkbox = CheckBox("Save token securely in Keychain and reconnect on startup")
        self.remember_checkbox.setToolTip(
            "On by default. The token is stored in the OS keyring only, never in a text file. "
            "Uncheck for a one-time connection."
        )
        self.remember_checkbox.setChecked(True)
        layout.addWidget(self.remember_checkbox)

        self.connect_button = PrimaryPushButton("Connect")
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)
        self.status_label = CaptionLabel("Not connected")
        layout.addWidget(self.status_label)
        self.overview_button = PushButton("Open Overview")
        self.overview_button.setEnabled(False)
        self.overview_button.clicked.connect(self.overview_requested.emit)
        layout.addWidget(self.overview_button)
        self.keychain_status = CaptionLabel("")
        layout.addWidget(self.keychain_status)

        connection_actions = QHBoxLayout()
        self.reconnect_button = PushButton("Reconnect saved server")
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)
        self.forget_button = PushButton("Forget saved access")
        self.forget_button.clicked.connect(self.forget_requested.emit)
        connection_actions.addWidget(self.reconnect_button)
        connection_actions.addWidget(self.forget_button)
        layout.addLayout(connection_actions)

        self.advanced_button = PushButton("Show advanced connection options")
        self.advanced_button.clicked.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_button)
        self.advanced_panel = QWidget(self)
        advanced = QVBoxLayout(self.advanced_panel)
        advanced.setContentsMargins(6, 3, 6, 4)
        advanced.setSpacing(9)
        advanced.addWidget(SubtitleLabel("Advanced / optional"))
        ssh_info = CaptionLabel(
            "SSH forwarding is only an optional fallback for private networks "
            "without HTTPS. It is not required for normal Daedalus access."
        )
        ssh_info.setWordWrap(True)
        advanced.addWidget(ssh_info)
        self.ssh_host_input = LineEdit()
        self.ssh_host_input.setPlaceholderText("SSH host or user@host")
        from daedalus.desktop.ssh_tunnel import SSHConnectionUnavailable, load_ssh_destination
        try:
            stored_ssh_host = load_ssh_destination()
        except SSHConnectionUnavailable:
            stored_ssh_host = None
        if stored_ssh_host:
            self.ssh_host_input.setText(stored_ssh_host)
        advanced.addWidget(self.ssh_host_input)
        self.ssh_button = PushButton("Use SSH fallback")
        self.ssh_button.clicked.connect(self._connect_ssh)
        advanced.addWidget(self.ssh_button)
        self.demo_button = PushButton("Try offline demo — no game login")
        self.demo_button.clicked.connect(self.demo_requested.emit)
        self.demo_button.setToolTip(
            "Run an isolated synthetic preview on loopback; never access saved accounts"
        )
        advanced.addWidget(self.demo_button)
        layout.addWidget(self.advanced_panel)
        self.advanced_panel.hide()
        layout.addStretch(1)

    def _toggle_advanced(self) -> None:
        opened = not self.advanced_panel.isVisible()
        self.advanced_panel.setVisible(opened)
        self.advanced_button.setText(
            "Hide advanced connection options" if opened
            else "Show advanced connection options"
        )

    def set_token_saved(self, saved: bool) -> None:
        self.keychain_status.setText(
            "API token saved in the OS Keychain; future launches can reconnect automatically."
            if saved else ""
        )

    def _connect(self) -> None:
        self.connect_requested.emit(self.url_input.text().strip(), self.token_input.text())

    def _connect_ssh(self) -> None:
        self.ssh_connect_requested.emit(
            self.ssh_host_input.text().strip(), self.token_input.text()
        )

    def set_connected(self, connected: bool, *, demo: bool = False) -> None:
        self.overview_button.setEnabled(connected)
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
    recovery_guide_requested = Signal(str)
    recovery_prepare_requested = Signal(str)
    rebind_requested = Signal(str, str)
    native_browser_login_requested = Signal(str)
    monitor_requested = Signal(str)
    report_selection_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("accounts_page")
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        scroll.setWidget(container)
        container_layout.addWidget(scroll)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)
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
        self._excluded_report_ids: set[str] = set()
        self._updating_report_checks = False
        self.select_all_reports = CheckBox("Include all accounts in warehouse reports")
        self.select_all_reports.setToolTip(
            "Local report selection only; does not start game tasks or change account enablement"
        )
        self.select_all_reports.setChecked(True)
        self.select_all_reports.stateChanged.connect(self._set_all_reports)
        layout.addWidget(self.select_all_reports)
        self.table = _table(["Account", "World", "Player", "Enabled", "Session", "IkaBot", "Report"])
        self.table.itemChanged.connect(self._report_item_changed)
        self.table.setMinimumHeight(205)
        self.table.setMaximumHeight(290)
        layout.addWidget(self.table)
        self.selected_account_summary = StatusPanel(
            "Choose an account",
            "Select a row to see session status and available next steps.",
            self,
        )
        layout.addWidget(self.selected_account_summary)
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
        advanced_wrap = QVBoxLayout()
        advanced_wrap.setSpacing(12)
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
        advanced_wrap.addLayout(assistance_actions)
        native_login_actions = QHBoxLayout()
        self.native_browser_login_button = PrimaryPushButton("Sign in on this Mac")
        self.native_browser_login_button.setToolTip(
            "Human Gameforge browser login on this Mac; encrypted one-time handoff "
            "to your verified backend worker"
        )
        self.native_browser_login_button.setEnabled(False)
        self.native_browser_login_button.clicked.connect(self._native_browser_login)
        native_login_actions.addWidget(self.native_browser_login_button)
        self.native_login_status = CaptionLabel(
            "Native Mac browser login is available when your backend enables secure recovery."
        )
        native_login_actions.addWidget(self.native_login_status, 1)
        layout.addLayout(native_login_actions)
        self._native_browser_login_enabled = False

        recovery_actions = QHBoxLayout()
        self.recovery_guide_button = PushButton("Advanced: host recovery instructions")
        self.recovery_prepare_button = PushButton("Advanced: prepare host-side recovery")
        self.rebind_button = PushButton("Advanced: verify host-staged session")
        self.recovery_guide_button.setEnabled(False)
        self.recovery_prepare_button.setEnabled(False)
        self.rebind_button.setEnabled(False)
        self.recovery_guide_button.clicked.connect(self._request_recovery_guide)
        self.recovery_prepare_button.clicked.connect(self._prepare_worker_recovery)
        self.rebind_button.clicked.connect(self._request_worker_rebind)
        self._recovery_guide: dict[str, object] | None = None
        recovery_actions.addWidget(self.recovery_guide_button)
        recovery_actions.addWidget(self.recovery_prepare_button)
        recovery_actions.addWidget(self.rebind_button)
        recovery_actions.addStretch(1)
        advanced_wrap.addLayout(recovery_actions)
        self.assistance_status = CaptionLabel("Select an account to check for manual help")
        advanced_wrap.addWidget(self.assistance_status)
        self._monitor_enabled = False
        self.monitor_button = PushButton("Monitor verified session")
        self.monitor_button.clicked.connect(self._monitor_selected)
        self.monitor_button.setEnabled(False)
        advanced_wrap.addWidget(self.monitor_button)
        self.monitor_status = CaptionLabel("Existing-session monitoring is disabled")
        advanced_wrap.addWidget(self.monitor_status)
        self.advanced_recovery_panel = QWidget(self)
        self.advanced_recovery_panel.setLayout(advanced_wrap)
        self.advanced_recovery_button = PushButton("Advanced recovery and monitoring ▾")
        self.advanced_recovery_button.clicked.connect(self._toggle_advanced_recovery)
        self.advanced_recovery_button.setAccessibleName(
            "Show or hide advanced account recovery actions"
        )
        layout.addWidget(self.advanced_recovery_button)
        layout.addWidget(self.advanced_recovery_panel)
        self.advanced_recovery_panel.hide()

    def _toggle_advanced_recovery(self) -> None:
        showing = not self.advanced_recovery_panel.isVisible()
        self.advanced_recovery_panel.setVisible(showing)
        self.advanced_recovery_button.setText(
            "Hide advanced recovery and monitoring" if showing
            else "Advanced recovery and monitoring ▾"
        )

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        self._accounts = accounts
        self._assistance_ticket = None
        self._assistance_account_id = None
        self._recovery_guide = None
        # Removed accounts no longer need a persisted exclusion.
        self._excluded_report_ids.intersection_update(
            str(account["id"]) for account in accounts if isinstance(account.get("id"), str)
        )
        self._render()
        self._update_assistance_buttons()
        self._emit_report_selection()

    def set_report_exclusions(self, excluded_ids: set[str]) -> None:
        """Apply backend-scoped, private UI report preferences only."""
        self._excluded_report_ids = set(excluded_ids)
        self._render()
        self._emit_report_selection()

    def selected_report_account_ids(self) -> list[str]:
        return [
            str(account["id"]) for account in self._accounts
            if isinstance(account.get("id"), str)
            and account["id"] not in self._excluded_report_ids
        ]

    def report_exclusions(self) -> set[str]:
        return set(self._excluded_report_ids)

    def _emit_report_selection(self) -> None:
        self.report_selection_changed.emit(self.selected_report_account_ids())

    def _update_select_all_reports(self) -> None:
        with QSignalBlocker(self.select_all_reports):
            selected = self.selected_report_account_ids()
            if not self._accounts or len(selected) == len(self._accounts):
                state = Qt.Checked
            elif not selected:
                state = Qt.Unchecked
            else:
                state = Qt.PartiallyChecked
            self.select_all_reports.setCheckState(state)

    def _set_all_reports(self, state: int) -> None:
        if self._updating_report_checks:
            return
        self._excluded_report_ids = (
            set() if state == Qt.Checked.value
            else {str(account["id"]) for account in self._accounts if isinstance(account.get("id"), str)}
        )
        self._render()
        self._emit_report_selection()

    def _report_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_report_checks or item.column() != 6:
            return
        row = item.row()
        if not 0 <= row < len(self._accounts):
            return
        account_id = self._accounts[row].get("id")
        if not isinstance(account_id, str):
            return
        if item.checkState() == Qt.Checked:
            self._excluded_report_ids.discard(account_id)
        else:
            self._excluded_report_ids.add(account_id)
        self._update_select_all_reports()
        self._emit_report_selection()

    def set_connected_ids(self, account_ids: list[str] | None) -> None:
        self._connected_ids = set(account_ids) if account_ids is not None else None
        self._render()

    def _render(self) -> None:
        self._updating_report_checks = True
        try:
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
                        "",
                    ]
                    for acc in self._accounts
                ],
            )
            for index, account in enumerate(self._accounts):
                item = self.table.item(index, 6)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Unchecked if account.get("id") in self._excluded_report_ids else Qt.Checked
                )
                item.setToolTip("Include in read-only warehouse reporting")
        finally:
            self._updating_report_checks = False
        self._update_select_all_reports()

    def account_record(self, account_id: str) -> dict[str, object] | None:
        return next((dict(record) for record in self._accounts
                     if record.get("id") == account_id), None)

    def set_native_browser_login_enabled(self, enabled: bool) -> None:
        self._native_browser_login_enabled = enabled
        self.native_login_status.setText(
            "Secure browser sign-in is available. Select the correct account above."
            if enabled else
            "This backend has not enabled native browser login."
        )
        self._update_assistance_buttons()

    def _native_browser_login(self) -> None:
        account_id = self._selected_visible_id()
        account = self.account_record(account_id) if account_id else None
        if (account_id is not None and account is not None and
                account.get("enabled") is True and self._native_browser_login_enabled):
            self.native_browser_login_requested.emit(account_id)

    def _selected_visible_id(self) -> str | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._accounts):
            selected = self._accounts[index].get("id")
            if isinstance(selected, str):
                return selected
        return None

    def _update_assistance_buttons(self) -> None:
        account_id = self._selected_visible_id()
        selected = self.account_record(account_id) if account_id else None
        if selected:
            session = str(selected.get("session_status") or "not_connected")
            message = {
                "authenticated": "Session verified. Warehouse reports and eligible automations are available.",
                "needs_assistance": "Sign in is needed. Use Sign in on this Mac when enabled.",
                "paused": "Worker is paused. Inspect session status before resuming any operation.",
                "not_connected": "No verified session is attached to this account.",
                "disabled": "Account is disabled on the authoritative backend.",
            }.get(session, "Session: " + session.replace("_", " "))
            self.selected_account_summary.set_status(
                str(selected.get("label") or selected.get("player") or selected["id"]),
                message,
            )
        else:
            self.selected_account_summary.set_status(
                "Choose an account", "Select a row for status and sign-in options."
            )
        self.native_browser_login_button.setEnabled(
            self._native_browser_login_enabled and account_id is not None
            and selected is not None and selected.get("enabled") is True
        )
        self.assistance_check_button.setEnabled(account_id is not None)
        self.recovery_guide_button.setEnabled(account_id is not None)
        self.monitor_button.setEnabled(self._monitor_enabled and account_id is not None)
        guide = self._recovery_guide
        self.recovery_prepare_button.setEnabled(
            account_id is not None
            and isinstance(guide, dict)
            and guide.get("account_id") == account_id
            and guide.get("enabled") is True
            and guide.get("dedicated_rebind_supported") is True
            and guide.get("session_status") in {
                "authenticated", "needs_assistance",
            }
            and not (
                isinstance(guide.get("ticket"), dict)
                and guide["ticket"].get("state") in {
                    "waiting_operator", "operator_ready", "validating_session",
                }
            )
        )
        self.rebind_button.setEnabled(
            account_id is not None
            and isinstance(guide, dict)
            and guide.get("account_id") == account_id
            and guide.get("enabled") is True
            and guide.get("dedicated_rebind_supported") is True
            and isinstance(guide.get("ticket"), dict)
            and guide["ticket"].get("state") == "operator_ready"
        )
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

    def set_recovery_guide(self, guide: dict[str, object]) -> None:
        """Display fixed local instructions only; never render remote text as a command."""
        account_id = guide.get("account_id")
        if not isinstance(account_id, str) or account_id != self._selected_visible_id():
            return
        self._recovery_guide = guide
        self._update_assistance_buttons()
        # These are locally authored commands, with only the API-validated ID.
        # Running this GUI on a different Mac must NEVER operate its own keyring.
        steps = (
            "Use a trusted graphical remote desktop to the AUTHORITATIVE WORKER HOST, "
            "under the SAME OS user that runs Daedalus. Do not run these on this "
            "client Mac if the worker is elsewhere.\n\n"
            "For first-time provisioning with no active worker:\n"
            f"daedalus sessions bind-email {account_id} --config /private/accounts.toml\n"
            f"daedalus sessions assist-playwright-login {account_id} "
            "--config /private/accounts.toml --confirm-read-only-network\n\n"
            "If an existing dedicated worker owns the account lease:\n"
            f"daedalus sessions stage-playwright-login {account_id} "
            "--config /private/accounts.toml --confirm-read-only-network\n"
            "Alternatively, stage only a manually copied world cookie with "
            "'stage-world-cookie' using the same flags and a hidden terminal prompt.\n"
            "If the existing worker is healthy, first press 'Prepare idle worker recovery' "
            "to pause it safely and create a short-lived assistance ticket. "
            "After staging, return here: confirm the manual assistance ticket, "
            "then press 'Verify staged cookie and rebind worker'.\n\n"
            "Only the worker can independently verify the game-world player. "
            "Never paste a cookie or password into the desktop, backend URL, "
            "GitHub, an API request, or a public browser session."
        )
        if guide.get("enabled") is not True:
            steps += "\n\nThis backend has NOT enabled monitored recovery."
        elif guide.get("dedicated_rebind_supported") is not True:
            steps += (
                "\n\nThis backend cannot hot-rebind an attached dedicated worker. "
                "Use an isolated test deployment and do not replace a production owner."
            )
        QMessageBox.information(self, "Trusted-host human recovery", steps)

    def _request_recovery_guide(self) -> None:
        account_id = self._selected_visible_id()
        if account_id is not None:
            self.recovery_guide_requested.emit(account_id)

    def _prepare_worker_recovery(self) -> None:
        account_id = self._selected_visible_id()
        guide = self._recovery_guide
        if (
            account_id is None or not isinstance(guide, dict)
            or guide.get("account_id") != account_id
            or guide.get("enabled") is not True
            or guide.get("dedicated_rebind_supported") is not True
            or guide.get("session_status") not in {
                "authenticated", "needs_assistance",
            }
            or not self.recovery_prepare_button.isEnabled()
        ):
            return
        if QMessageBox.question(
            self, "Pause idle dedicated worker for human recovery",
            "This explicitly pauses new tasks for the selected dedicated "
            "worker and creates a short-lived manual assistance ticket. "
            "The backend refuses when any task is running or uncertain. "
            "No game login, cookie transfer or automatic task restart occurs. "
            "Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            self.recovery_prepare_requested.emit(account_id)

    def _request_worker_rebind(self) -> None:
        account_id = self._selected_visible_id()
        guide = self._recovery_guide
        if (
            account_id is None or not isinstance(guide, dict)
            or guide.get("account_id") != account_id
            or guide.get("dedicated_rebind_supported") is not True
            or not isinstance(guide.get("ticket"), dict)
            or guide["ticket"].get("state") != "operator_ready"
        ):
            return
        ticket_id = guide["ticket"].get("ticket_id")
        if not isinstance(ticket_id, str):
            return
        if QMessageBox.question(
            self, "Confirm authoritative-host worker rebind",
            "Have you ALREADY staged a new world cookie in the protected keyring "
            "of the SAME authoritative worker host, using its trusted graphical "
            "terminal? This may stop and replace the dedicated IPC worker. All "
            "existing running/uncertain tasks must first be reconciled. "
            "The backend will validate the exact world and player; no task is "
            "automatically restarted. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            self.rebind_requested.emit(account_id, ticket_id)

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
    configure_requested = Signal(str)

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
            "Read-only catalog. Select a background task and open its guided setup in Automations."
        )
        layout.addWidget(self.status_label)
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("Filter operations by name or module")
        self.search_input.textChanged.connect(self._render)
        layout.addWidget(self.search_input)
        self.table = _table(["Operation", "Kind", "Module", "Parameters"])
        self.table.itemSelectionChanged.connect(self._update_configure)
        self.table.cellDoubleClicked.connect(lambda *_args: self._configure_selected())
        layout.addWidget(self.table, 1)
        self.configure_button = PrimaryPushButton("Configure selected automation")
        self.configure_button.clicked.connect(self._configure_selected)
        self.configure_button.setEnabled(False)
        layout.addWidget(self.configure_button)

    def _update_configure(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 1) if row >= 0 else None
        self.configure_button.setEnabled(
            bool(item is not None and item.text() == "background_task")
        )

    def _configure_selected(self) -> None:
        row = self.table.currentRow()
        kind = self.table.item(row, 1) if row >= 0 else None
        name = self.table.item(row, 0) if row >= 0 else None
        if kind is not None and kind.text() == "background_task" and name is not None:
            self.configure_requested.emit(name.text())

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
        self._update_configure()


class WarehousesPage(QWidget):
    load_requested = Signal(str)
    load_selected_requested = Signal(object)
    load_all_requested = Signal(object)
    report_scope_changed = Signal(object)

    _COLUMNS = ("City", "Island", "World", *RESOURCES, "Capacity", "Captured", "Incomplete", "Account")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("warehouses_page")
        self._account_ids: list[str] = []
        self._accounts: dict[str, dict[str, object]] = {}
        self._selected_account: dict[str, object] = {}
        self._snapshots: list[dict[str, object]] = []
        self._rows: list[dict[str, object]] = []
        self._included_ids: list[str] = []
        self._reports: list[tuple[str, list[dict[str, object]]]] = []
        self._failed_accounts: list[str] = []

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
        self.load_button = PushButton("This account")
        self.load_button.setToolTip("Refresh this account's warehouse report")
        self.load_button.clicked.connect(self._load)
        controls.addWidget(self.load_button)

        self.load_all_button = PrimaryPushButton("All accounts")
        self.load_all_button.setAccessibleName("Load warehouses for all accounts")
        self.load_all_button.setToolTip(
            "Fetch read-only warehouse reports for every configured account; "
            "unavailable accounts will be shown separately"
        )
        self.load_all_button.clicked.connect(self._load_all)
        self.load_all_button.setEnabled(False)
        controls.addWidget(self.load_all_button)

        self.load_selected_button = PushButton("Selected accounts")
        self.load_selected_button.setToolTip(
            "Read-only snapshots for accounts selected here; no tasks started"
        )
        self.load_selected_button.clicked.connect(self._load_selected)
        self.load_selected_button.setEnabled(False)
        controls.addWidget(self.load_selected_button)

        self.choose_accounts_button = PushButton("Choose accounts…")
        self.choose_accounts_button.setToolTip(
            "Choose any combination of accounts for warehouse reports"
        )
        self.choose_accounts_button.clicked.connect(self._choose_accounts)
        self.choose_accounts_button.setEnabled(False)
        controls.addWidget(self.choose_accounts_button)
        layout.addLayout(controls)
        filters = QHBoxLayout()

        self.only_220k = CheckBox("Only 220K+")
        self.only_220k.setToolTip(
            "Show cities with at least 220,000 known unsecured resources in total"
        )
        self.only_220k.stateChanged.connect(self._render)
        filters.addWidget(self.only_220k)
        self.group_island = CheckBox("Group by island")
        self.group_island.setToolTip("Order rows by existing city island coordinates")
        self.group_island.stateChanged.connect(self._render)
        filters.addWidget(self.group_island)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.status_label = CaptionLabel("No warehouse snapshots loaded")
        layout.addWidget(self.status_label)
        self.table = _table(list(self._COLUMNS))
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.copy_button = PushButton("Copy CSV")
        self.copy_button.clicked.connect(self._copy_csv)
        self.copy_islands_button = PushButton("Copy by island")
        self.copy_islands_button.clicked.connect(self._copy_islands)
        self.csv_button = PushButton("Save CSV")
        self.csv_button.clicked.connect(lambda: self._save("csv"))
        self.json_button = PushButton("Save JSON")
        self.json_button.clicked.connect(lambda: self._save("json"))
        self.txt_button = PushButton("Save TXT")
        self.txt_button.clicked.connect(lambda: self._save("txt"))
        self.print_button = PushButton("Print report…")
        self.print_button.setAccessibleName("Preview and print the combined warehouse report")
        self.print_button.clicked.connect(self._print_report)
        self.print_button.setEnabled(False)
        actions.addWidget(self.print_button)
        self.export_button = PushButton("Export report ▾")
        self.export_button.setAccessibleName("Copy or save the current warehouse report")
        menu = QMenu(self)
        menu.addAction("Copy CSV to clipboard", self._copy_csv)
        menu.addAction("Copy grouped island report", self._copy_islands)
        menu.addAction("Print grouped report…", self._print_report)
        menu.addSeparator()
        menu.addAction("Save CSV…", lambda: self._save("csv"))
        menu.addAction("Save JSON…", lambda: self._save("json"))
        menu.addAction("Save island text…", lambda: self._save("txt"))
        self.export_button.setMenu(menu)
        self.export_button.setEnabled(False)
        actions.addWidget(self.export_button)
        for button in (
            self.copy_button, self.copy_islands_button,
            self.csv_button, self.json_button, self.txt_button,
        ):
            button.setEnabled(False)
            button.setVisible(False)
            actions.addWidget(button)  # Compatibility for existing test/API callers.
        actions.addStretch(1)
        # Keep Print/Export visible above the potentially tall warehouse table.
        layout.insertLayout(layout.indexOf(self.status_label), actions)

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
        self.load_all_button.setEnabled(bool(self._account_ids))
        self.choose_accounts_button.setEnabled(bool(self._account_ids))
        self.load_button.setEnabled(bool(self._account_ids))
        self.set_selected_accounts(self._included_ids or self._account_ids)

    def selected_account_id(self) -> str | None:
        index = self.account_combo.currentIndex()
        return self._account_ids[index] if 0 <= index < len(self._account_ids) else None

    def select_account(self, account_id: str) -> None:
        if account_id in self._account_ids:
            self.account_combo.setCurrentIndex(self._account_ids.index(account_id))

    def set_selected_accounts(self, account_ids: list[str]) -> None:
        """Local report inclusion only; never changes engine account enablement."""
        included = set(account_ids)
        self._included_ids = [aid for aid in self._account_ids if aid in included]
        self.load_selected_button.setEnabled(bool(self._included_ids))
        self.load_selected_button.setText(
            f"Selected ({len(self._included_ids)})"
        )

    def _load_all(self) -> None:
        """Always include every configured account; individual failures remain visible."""
        if self._account_ids:
            self.status_label.setText(
                f"Loading warehouses for all {len(self._account_ids)} accounts…"
            )
            self.load_all_requested.emit(list(self._account_ids))

    def _choose_accounts(self) -> None:
        from daedalus.desktop.account_scope import AccountSelectionDialog

        dialog = AccountSelectionDialog(
            list(self._accounts.values()), list(self._included_ids), self,
            title="Warehouse report accounts",
        )
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.selected_ids()
            self.set_selected_accounts(selected)
            self.report_scope_changed.emit(selected)

    def set_display_preferences(self, *, only_220k: bool, group_by_island: bool) -> None:
        self.only_220k.setChecked(only_220k)
        self.group_island.setChecked(group_by_island)

    def clear_reports(self) -> None:
        """Avoid displaying another backend's resource data after a reconnect."""
        self._reports = []
        self._failed_accounts = []
        self._rows = []
        self._snapshots = []
        self._selected_account = {}
        self.table.setRowCount(0)
        self.status_label.setText("No warehouse snapshots loaded")
        for button in (
            self.copy_button, self.copy_islands_button,
            self.csv_button, self.json_button, self.txt_button,
            self.export_button, self.print_button,
        ):
            button.setEnabled(False)

    def _load_selected(self) -> None:
        if self._included_ids:
            self.status_label.setText(
                f"Loading warehouses for {len(self._included_ids)} selected accounts…"
            )
            if len(self._included_ids) > 32:
                self.load_all_requested.emit(list(self._included_ids))
            else:
                self.load_selected_requested.emit(list(self._included_ids))

    def _load(self) -> None:
        account_id = self.selected_account_id()
        if account_id is not None:
            self.status_label.setText("Loading this account's warehouses…")
            self.load_requested.emit(account_id)

    def set_snapshots(self, account_id: str, snapshots: list[dict[str, object]]) -> None:
        self._selected_account = self._accounts.get(account_id, {"id": account_id})
        self._snapshots = snapshots
        self._reports = [(account_id, snapshots)]
        self._failed_accounts = []
        self._render()

    def set_batch_snapshots(self, results: list[dict[str, object]]) -> None:
        """Partial results are explicitly labeled; no failed account data is invented."""
        self._reports = []
        self._failed_accounts = []
        for result in results:
            account_id = result.get("account_id")
            if not isinstance(account_id, str) or account_id not in self._accounts:
                continue
            if result.get("error"):
                self._failed_accounts.append(account_id)
                continue
            cities = result.get("cities")
            if isinstance(cities, list) and all(isinstance(city, dict) for city in cities):
                self._reports.append((account_id, cities))
            else:
                self._failed_accounts.append(account_id)
        self._render()

    def _render(self, *_args: object) -> None:
        self._rows = [
            row for account_id, snapshots in self._reports
            for row in rows_for_warehouse(
                self._accounts.get(account_id, {"id": account_id}), snapshots,
                only_220k=self.only_220k.isChecked(),
            )
        ]
        if self.group_island.isChecked():
            self._rows.sort(key=lambda row: (
                str(row.get("world") or ""),
                row.get("island") is None,
                str(row.get("island") or ""),
                str(row.get("account") or ""),
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
                    row.get("account"),
                ]
                for row in self._rows
            ],
        )
        status = (
            f"{len(self._rows)} cities across {len(self._reports)} account reports"
            if self._reports else
            "No warehouse snapshots available — connect an authenticated account"
        )
        if self._reports and not self._rows and self.only_220k.isChecked():
            status = "No warehouses match the 220K+ filter; disable it to see all cities"
        if self._failed_accounts:
            labels = [
                str(self._accounts.get(aid, {}).get("label") or aid)
                for aid in self._failed_accounts
            ]
            status += "; unavailable account snapshots: " + ", ".join(labels[:5])
            if len(labels) > 5:
                status += f" (+{len(labels) - 5} more)"
        self.status_label.setText(status)
        for button in (
            self.copy_button, self.copy_islands_button,
            self.csv_button, self.json_button, self.txt_button,
            self.export_button, self.print_button,
        ):
            button.setEnabled(bool(self._rows))

    def _print_report(self) -> None:
        """Preview a text report for any number of included account warehouses."""
        if not self._rows:
            return
        try:
            from PySide6.QtGui import QFont, QTextDocument
            from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog

            document = QTextDocument(self)
            document.setDefaultFont(QFont("Menlo", 10))
            document.setPlainText(
                report_txt(self._rows, group_by_island=self.group_island.isChecked())
            )
            printer = QPrinter(QPrinter.HighResolution)
            preview = QPrintPreviewDialog(printer, self)
            preview.setWindowTitle("Print Daedalus warehouse report")
            preview.paintRequested.connect(document.print_)
            preview.exec()
        except (ImportError, RuntimeError):
            QMessageBox.warning(
                self, "Printing unavailable",
                "This system does not offer Qt printer support. "
                "Use Save TXT or Copy by island and print with another application.",
            )

    def _copy_csv(self) -> None:
        QGuiApplication.clipboard().setText(report_csv(self._rows))

    def _copy_islands(self) -> None:
        QGuiApplication.clipboard().setText(report_txt(self._rows, group_by_island=True))

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
