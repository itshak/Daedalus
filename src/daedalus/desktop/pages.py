"""Native Fluent pages built from the existing Mac GUI's design vocabulary.

These pages never contact Ikariam or store authentication secrets. The main
window feeds them typed data from the Daedalus backend API.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
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
    QSizePolicy,
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

from daedalus.account_display import account_display_name
from daedalus.desktop.design_system import PageHeading, StatusPanel
from daedalus.desktop.widgets import OpaqueCardWidget, ScrollTableWidget
from daedalus.reporting import (
    RESOURCES,
    report_csv,
    report_json,
    report_txt,
    report_txt_islands,
    rows_for_warehouse,
)


def _table(headers: list[str]) -> ScrollTableWidget:
    table = ScrollTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setBorderVisible(True)
    table.setBorderRadius(8)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setFixedHeight(32)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    table.horizontalHeader().setStretchLastSection(True)
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)
    table.setEditTriggers(ScrollTableWidget.NoEditTriggers)
    table.setSelectionBehavior(ScrollTableWidget.SelectRows)
    table.setSelectionMode(ScrollTableWidget.SingleSelection)
    return table


def _populate(table: ScrollTableWidget, rows: list[list[object]]) -> None:
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            label = "—" if value is None else str(value)
            table.setItem(row_index, column_index, QTableWidgetItem(label))



_WORLD_CODE = re.compile(r"^s([0-9]+)-([a-z]{2,4})$", re.IGNORECASE)
_IMPORTED_LABEL = re.compile(r"Imported IkaBot (?:account|identity)(?: [0-9]+)?", re.IGNORECASE)
# Verified in official Gameforge 2026 server-merger announcement:
# https://forum.ikariam.gameforge.com/forum/thread/114624/
# Unknown server numbers keep their exact identifiers, never guessed names.
_OFFICIAL_WORLD_NAMES = {"s52-ru": "Adonis", "s53-ru": "Eurydike"}


def _account_title(account: dict[str, object]) -> str:
    """Prefer server-bound email, meaningful label or player fallback."""
    return account_display_name(account)


def _world_title(account: dict[str, object]) -> str:
    """Show a world name only if the backend actually provides one."""
    world = str(account.get("world") or "")
    match = _WORLD_CODE.fullmatch(world)
    if match is None:
        return world or "—"
    flag = "🇷🇺" if match.group(2).casefold() == "ru" else "🌐"
    server = f"S{int(match.group(1))}"
    name = account.get("world_name")
    if not (isinstance(name, str) and 0 < len(name.strip()) <= 80 and name.isprintable()):
        name = _OFFICIAL_WORLD_NAMES.get(world.casefold())
    if isinstance(name, str) and name:
        return f"{flag} {name.strip()} · {server}"
    return f"{flag} {server}"


def _status_item(symbol: str, explanation: str, color: str) -> QTableWidgetItem:
    """A styled status glyph with a readable tooltip and accessibility value."""
    item = QTableWidgetItem(symbol)
    item.setTextAlignment(Qt.AlignCenter)
    item.setToolTip(explanation)
    item.setData(Qt.AccessibleTextRole, explanation)
    item.setForeground(QBrush(QColor(color)))
    font = item.font()
    font.setBold(True)
    font.setPointSize(13)
    item.setFont(font)
    return item


def _session_status_item(value: object) -> QTableWidgetItem:
    status = str(value or "not_connected")
    if status == "authenticated":
        return _status_item("✓", "Game session authenticated", "#2BAF65")
    if status in {"validating_session", "validating_handoff", "assisted_login"}:
        return _status_item("…", "Game session: " + status.replace("_", " "), "#D69E27")
    if status == "paused":
        return _status_item("‖", "Game session paused", "#D69E27")
    if status in {"not_connected", "failed", "needs_assistance", "disabled"}:
        meanings = {
            "not_connected": "No authenticated game session",
            "failed": "Game session failed",
            "needs_assistance": "Game session needs sign-in assistance",
            "disabled": "Game account disabled",
        }
        return _status_item("✕", meanings[status], "#D95455")
    return _status_item("?", "Game session status is unknown", "#8D96A3")


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
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setFrameShape(QScrollArea.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        host = QWidget(self.content_scroll)
        center = QHBoxLayout(host)
        center.setContentsMargins(24, 28, 24, 28)
        center.setSpacing(0)
        center.addStretch(1)
        self.connection_card = OpaqueCardWidget(host)
        self.connection_card.setMaximumWidth(540)
        self.connection_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        center.addWidget(self.connection_card, 0, Qt.AlignTop)
        center.addStretch(1)
        self.content_scroll.setWidget(host)
        shell.addWidget(self.content_scroll)
        layout = QVBoxLayout(self.connection_card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(9)
        layout.addWidget(PageHeading("Connect to Daedalus"))
        intro = CaptionLabel(
            "Connect securely over HTTPS. No SSH tunnel, Terminal or manual "
            "port forwarding is needed. Your server stays in control of game sessions."
        )
        intro.setWordWrap(True)
        self.intro_label = intro
        self.url_input_explanation = intro
        intro.hide()

        layout.addWidget(BodyLabel("Server address"))
        self.url_input = LineEdit()
        self.url_input.setPlaceholderText("https://your-daedalus-server.example")
        self.url_input.setAccessibleName("Secure Daedalus backend HTTPS address")
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
        self._token_saved = False
        self._connected = False
        self.token_input.setPlaceholderText("Paste your API token once")
        self.token_input.setAccessibleName("Daedalus API access token")
        layout.addWidget(self.token_input)
        tip = CaptionLabel(
            "Daedalus API token, not a Gameforge lobby token. After the first "
            "successful connection the token is kept securely in your Mac Keychain."
        )
        tip.setWordWrap(True)
        self.token_input.setToolTip(tip.text())
        self.remember_checkbox = CheckBox("Save token securely in Keychain and reconnect on startup")
        self.remember_checkbox.setToolTip(
            "On by default. The token is stored in the OS keyring only, never in a text file. "
            "Uncheck for a one-time connection."
        )
        self.remember_checkbox.setChecked(True)
        layout.addWidget(self.remember_checkbox)

        self.connect_button = PrimaryPushButton("Connect")
        self.connect_button.setAccessibleDescription(
            "Connect to the Daedalus backend API; does not log in to Gameforge."
        )
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)
        self.status_label = CaptionLabel("Not connected. Enter a secure backend address to begin.")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Connection progress and status")
        layout.addWidget(self.status_label)
        self.overview_button = PushButton("Open Overview")
        self.overview_button.setEnabled(False)
        self.overview_button.clicked.connect(self.overview_requested.emit)
        layout.addWidget(self.overview_button)
        self.keychain_status = CaptionLabel("")
        layout.addWidget(self.keychain_status)
        self.keychain_status.hide()

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
        layout.addWidget(self.demo_button)
        layout.addWidget(self.advanced_panel)
        self.advanced_panel.hide()

    def _toggle_advanced(self) -> None:
        opened = not self.advanced_panel.isVisible()
        self.advanced_panel.setVisible(opened)
        self.advanced_button.setText(
            "Hide advanced connection options" if opened
            else "Show advanced connection options"
        )

    def set_token_saved(self, saved: bool) -> None:
        self._token_saved = saved
        self.keychain_status.setText(
            "API access saved in Keychain" if saved else ""
        )
        self.keychain_status.setVisible(saved)
        self._update_token_hint()

    def _update_token_hint(self) -> None:
        """Show a masked *hint*, never retain the bearer in a Qt input field."""
        if self._connected and self._token_saved:
            hint = "••••••••••••••••  (saved in Keychain)"
        elif self._connected:
            hint = "••••••••••••••••  (active for this session)"
        elif self._token_saved:
            hint = "••••••••••••••••  (saved; reconnect to use)"
        else:
            hint = "Paste your API token once"
        self.token_input.setPlaceholderText(hint)
        self.token_input.setAccessibleDescription(
            "Token is configured; leave blank to reuse saved secure access"
            if self._token_saved else
            "Enter a token to connect or replace the current token"
        )

    def _connect(self) -> None:
        self.connect_requested.emit(self.url_input.text().strip(), self.token_input.text())

    def _connect_ssh(self) -> None:
        self.ssh_connect_requested.emit(
            self.ssh_host_input.text().strip(), self.token_input.text()
        )

    def set_connecting(self, active: bool) -> None:
        """Progress is explicit, without exposing the URL, token or transport errors."""
        self.connect_button.setEnabled(not active)
        self.ssh_button.setEnabled(not active)
        self.reconnect_button.setEnabled(not active)
        self.connect_button.setText("Connecting…" if active else "Connect")
        if active:
            self.status_label.setText(
                "Checking secure connection, authorization and backend capabilities…"
            )

    def set_connection_error(self, reason: str) -> None:
        """Classify safe failures; never display arbitrary backend response bodies."""
        self._connected = False
        self._update_token_hint()
        failure = reason.casefold()
        if any(word in failure for word in ("certificate", "tls", "ssl", "trust")):
            message = "Certificate not trusted. Check your server certificate; do not bypass TLS."
        elif any(word in failure for word in ("401", "403", "unauthorized", "forbidden", "token")):
            message = "Access denied. Check the API token for this exact server."
        elif any(word in failure for word in ("keychain", "keyring", "credential")):
            message = "Keychain unavailable. Unlock it or paste an API token for this session."
        elif any(word in failure for word in ("url", "https", "address", "scheme")):
            message = "Invalid server address. Use a trusted HTTPS URL."
        elif any(word in failure for word in ("timeout", "unreachable", "connection", "network")):
            message = "Server unreachable. Check the address, network and server status."
        else:
            message = "Unable to connect. Review the secure server address and API access."
        self.status_label.setText(message)
        self.overview_button.setEnabled(False)

    def set_connected(self, connected: bool, *, demo: bool = False) -> None:
        self._connected = connected
        self.overview_button.setEnabled(connected)
        self.status_label.setText(
            "SYNTHETIC DEMO connected — no real game accounts or sessions"
            if connected and demo else
            "Connected securely to the Daedalus backend. Open Overview to continue."
            if connected else "Not connected. Enter a secure backend address to begin."
        )
        if connected:
            # QLineEdit itself must not retain a copy of the bearer. The
            # masked placeholder tells the operator access is configured.
            self.token_input.clear()
        self._update_token_hint()


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
    automatic_login_requested = Signal(object)
    automatic_login_cancel_requested = Signal()
    sync_saved_logins_requested = Signal(object)
    monitor_requested = Signal(str)
    recovery_refresh_requested = Signal()
    recovery_import_requested = Signal(str)
    recovery_policy_requested = Signal(str, bool, int)
    recovery_pause_requested = Signal(str, object)
    recovery_resume_requested = Signal(str)
    recovery_bulk_requested = Signal(object, bool)
    recovery_jobs_requested = Signal(str)
    report_selection_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("accounts_page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        self._accounts: list[dict[str, object]] = []
        self._connected_ids: set[str] | None = None
        self._edit_revision: str | None = None
        self._editable_accounts: list[dict[str, object]] = []
        self._excluded_report_ids: set[str] = set()
        self._updating_report_checks = False
        self._assistance_account_id: str | None = None
        self._assistance_ticket: dict[str, object] | None = None
        self._recovery_guide: dict[str, object] | None = None
        self._native_browser_login_enabled = False
        self._auto_login_busy = False
        self._monitor_enabled = False
        self._advanced_open = False
        self._recovery_by_account: dict[str, dict[str, object]] = {}
        self._recovery_supervisor_enabled = False

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(SubtitleLabel("Accounts"))
        header.addStretch(1)
        self.refresh_button = PushButton("Refresh")
        self.refresh_button.setToolTip("Refresh account status from the backend")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.create_button = PrimaryPushButton("Add account")
        self.create_button.clicked.connect(self._create)
        self.create_button.setEnabled(False)
        header.addWidget(self.refresh_button)
        header.addWidget(self.create_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.select_all_reports = CheckBox("All in reports")
        self.select_all_reports.setChecked(True)
        self.select_all_reports.setToolTip(
            "Include all configured accounts in combined warehouse reports; "
            "this changes no game sessions or task permissions"
        )
        self.select_all_reports.stateChanged.connect(self._set_all_reports)
        toolbar.addWidget(self.select_all_reports)
        toolbar.addStretch(1)
        self.auto_login_all_button = PushButton("Sign in all")
        self.auto_login_all_button.clicked.connect(self._auto_all)
        self.auto_login_button = PushButton("Sign in")
        self.auto_login_button.setToolTip(
            "Sign in the highlighted account using headless Selenium; "
            "only an actual CAPTCHA needs your input"
        )
        self.auto_login_button.clicked.connect(self._auto_this)
        toolbar.addWidget(self.auto_login_all_button)
        toolbar.addWidget(self.auto_login_button)
        self.auto_cancel_button = PushButton("Cancel sign-in")
        self.auto_cancel_button.clicked.connect(self.automatic_login_cancel_requested.emit)
        self.auto_cancel_button.setEnabled(False)
        self.auto_cancel_button.hide()
        toolbar.addWidget(self.auto_cancel_button)
        self.more_button = PushButton("More ▾")
        self.more_button.setAccessibleName("More account actions")
        toolbar.addWidget(self.more_button)
        layout.addLayout(toolbar)

        self.table = _table(["Account", "World", "Player", "Enabled", "Session", "Worker", "Report"])
        self.table.setAccessibleName("Configured accounts and warehouse report inclusion")
        self.table.horizontalHeaderItem(5).setToolTip(
            "Whether an existing IkaBot worker is attached; not a Gameforge login status"
        )
        self.table.setToolTip("Select an account; tick Report to include it in warehouse printing")
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setMinimumHeight(290)
        for col, width in enumerate((240, 145, 140, 70, 90, 80, 72)):
            self.table.setColumnWidth(col, width)
        self.table.itemChanged.connect(self._report_item_changed)
        self.table.itemSelectionChanged.connect(self._update_assistance_buttons)
        self.table.cellDoubleClicked.connect(lambda row, col: self._edit() if col != 6 else None)
        layout.addWidget(self.table, 1)
        self.selection_status = CaptionLabel("No accounts loaded")
        self.selection_status.setAccessibleName("Selected account and session status")
        layout.addWidget(self.selection_status)

        # Opt-in browser-friendly auto recovery, separate from Mac Selenium.
        # This panel exposes only redacted backend metadata and deliberate
        # operator actions; no login token or password input.
        recovery_header = QHBoxLayout()
        recovery_header.addWidget(SubtitleLabel("Automatic recovery"))
        recovery_header.addStretch(1)
        self.recovery_refresh_button = PushButton("Refresh recovery")
        self.recovery_refresh_button.clicked.connect(self.recovery_refresh_requested.emit)
        recovery_header.addWidget(self.recovery_refresh_button)
        layout.addLayout(recovery_header)
        self.recovery_status_label = CaptionLabel(
            "Automatic reconnection is off until explicitly approved for each account."
        )
        self.recovery_status_label.setWordWrap(True)
        layout.addWidget(self.recovery_status_label)
        recovery_actions = QHBoxLayout()
        recovery_actions.setSpacing(7)
        self.recovery_import_button = PushButton("Import saved lobby token")
        self.recovery_import_button.clicked.connect(self._recovery_import)
        self.recovery_policy_button = PushButton("Enable auto recovery")
        self.recovery_policy_button.clicked.connect(self._recovery_policy)
        self.recovery_pause_button = PushButton("Pause browser use ▾")
        self.recovery_pause_menu = QMenu(self)
        for caption, seconds in (
            ("15 minutes", 900), ("30 minutes", 1800),
            ("60 minutes", 3600), ("Until resumed", None),
        ):
            item = self.recovery_pause_menu.addAction(caption)
            item.triggered.connect(lambda checked=False, s=seconds: self._recovery_pause(s))
        self.recovery_pause_button.setMenu(self.recovery_pause_menu)
        self.recovery_resume_button = PushButton("Resume now")
        self.recovery_resume_button.clicked.connect(self._recovery_resume)
        self.recovery_jobs_button = PushButton("Review saved jobs")
        self.recovery_jobs_button.clicked.connect(self._recovery_jobs)
        for button in (self.recovery_import_button, self.recovery_policy_button,
                       self.recovery_pause_button, self.recovery_resume_button,
                       self.recovery_jobs_button):
            recovery_actions.addWidget(button)
        recovery_actions.addStretch(1)
        layout.addLayout(recovery_actions)
        self.recovery_bulk_button = PushButton("Recovery for selected / all…")
        self.recovery_bulk_button.clicked.connect(self._recovery_bulk)
        layout.addWidget(self.recovery_bulk_button)
        self._update_recovery_controls()

        # Keep existing named actions and backend signals for compatibility,
        # but display them only in the contextual More menu.
        self.edit_button = PushButton("Edit")
        self.toggle_button = PushButton("Enable / Disable")
        self.remove_button = PushButton("Remove")
        self.check_engine_button = PushButton("Check IkaBot sessions")
        self.sync_logins_button = PushButton("Back up saved logins")
        self.sync_logins_button.setToolTip(
            "Copy already remembered Mac logins to encrypted server storage. "
            "Passwords never travel as plaintext."
        )
        self.assistance_check_button = PushButton("Check login assistance")
        self.assistance_approve_button = PushButton("Confirm manual step complete")
        self.native_browser_login_button = PushButton("Manual browser fallback")
        self.monitor_button = PushButton("Monitor verified session")
        self.recovery_guide_button = PushButton("Host recovery instructions")
        self.recovery_prepare_button = PushButton("Prepare host-side recovery")
        self.rebind_button = PushButton("Verify host-staged session")
        self.auto_login_selected_button = PushButton("Sign in selected…")
        for button, callback in (
            (self.edit_button, self._edit),
            (self.toggle_button, self._toggle),
            (self.remove_button, self._remove),
            (self.check_engine_button, self.check_engine_requested.emit),
            (self.sync_logins_button, self._sync_saved_logins),
            (self.assistance_check_button, self._check_assistance),
            (self.assistance_approve_button, self._approve_assistance),
            (self.native_browser_login_button, self._native_browser_login),
            (self.monitor_button, self._monitor_selected),
            (self.recovery_guide_button, self._request_recovery_guide),
            (self.recovery_prepare_button, self._prepare_worker_recovery),
            (self.rebind_button, self._request_worker_rebind),
            (self.auto_login_selected_button, self._auto_selected),
        ):
            button.clicked.connect(callback)
            button.setEnabled(False)

        self.more_menu = QMenu(self)
        self._menu_actions = []
        for label, button in (
            ("Edit account…", self.edit_button),
            ("Enable / disable", self.toggle_button),
            ("Remove account…", self.remove_button),
            (None, None),
            ("Sign in selected accounts…", self.auto_login_selected_button),
            ("Check IkaBot sessions", self.check_engine_button),
            ("Back up saved logins to server…", self.sync_logins_button),
            ("Check login assistance", self.assistance_check_button),
            ("Confirm manual step complete", self.assistance_approve_button),
            ("Manual browser fallback…", self.native_browser_login_button),
            ("Monitor verified session…", self.monitor_button),
        ):
            if button is None:
                self.more_menu.addSeparator()
                continue
            action = self.more_menu.addAction(label)
            action.triggered.connect(button.click)
            self._menu_actions.append((action, button))
        self.more_menu.addSeparator()
        self.advanced_recovery_button = PushButton("Advanced recovery")
        self.advanced_recovery_button.clicked.connect(self._toggle_advanced_recovery)
        recovery_action = self.more_menu.addAction("Advanced recovery…")
        recovery_action.triggered.connect(self.advanced_recovery_button.click)
        self._menu_actions.append((recovery_action, self.advanced_recovery_button))
        self.more_menu.aboutToShow.connect(self._sync_account_menu)
        self.more_button.setMenu(self.more_menu)

        # Recovery is deliberately not part of the normal account workspace.
        # Show it only after an explicit More > Advanced recovery action.
        self.advanced_recovery_panel = QWidget(self)
        expert = QVBoxLayout(self.advanced_recovery_panel)
        expert.setContentsMargins(6, 8, 6, 8)
        expert.setSpacing(6)
        expert.addWidget(CaptionLabel("Advanced account recovery"))
        for button in (
            self.recovery_guide_button, self.recovery_prepare_button,
            self.rebind_button, self.assistance_check_button,
            self.assistance_approve_button, self.native_browser_login_button,
            self.monitor_button,
        ):
            # A named button is still the single source of enabled state for
            # the overflow-menu counterpart.
            button.setParent(self.advanced_recovery_panel)
            expert.addWidget(button)
        layout.addWidget(self.advanced_recovery_panel)
        self.advanced_recovery_panel.hide()

        # Dynamic/diagnostic labels exist for callers, but do not consume
        # permanent space with explanations already conveyed by tooltips.
        self.selected_account_summary = StatusPanel("", "", self)
        self.editor_status = CaptionLabel("")
        self.assistance_status = CaptionLabel("")
        self.monitor_status = CaptionLabel("")
        self.native_login_status = CaptionLabel("")
        self.auto_login_status = CaptionLabel("")
        self.auto_login_status.setWordWrap(True)
        layout.addWidget(self.auto_login_status)
        self.auto_login_status.hide()

    def set_recovery_status(self, response: dict[str, object]) -> None:
        """Refresh nonsecret data after a backend request, not a local timer."""
        entries = response.get("accounts")
        self._recovery_by_account = (
            {str(row["account_id"]): row for row in entries
             if isinstance(row, dict) and isinstance(row.get("account_id"), str)}
            if response.get("enabled") is True and isinstance(entries, list) else {}
        )
        self._recovery_supervisor_enabled = response.get("supervisor_enabled") is True
        self._update_recovery_controls()

    def _recovery_selection(self) -> tuple[str | None, dict[str, object] | None]:
        account_id = self._selected_visible_id()
        return account_id, self._recovery_by_account.get(account_id) if account_id else None

    def _update_recovery_controls(self) -> None:
        aid, status = self._recovery_selection()
        policy = status.get("policy") if isinstance(status, dict) else None
        policy = policy if isinstance(policy, dict) else {}
        enabled = policy.get("enabled") is True
        available = status.get("server_token_available") is True if status else False
        self.recovery_policy_button.setText(
            "Disable auto recovery" if enabled else "Enable auto recovery"
        )
        selected = aid is not None
        self.recovery_import_button.setEnabled(selected and bool(status) and not available)
        self.recovery_policy_button.setEnabled(selected and bool(status) and (enabled or available))
        self.recovery_pause_button.setEnabled(selected and enabled)
        self.recovery_resume_button.setEnabled(
            selected and enabled and self._recovery_supervisor_enabled
        )
        self.recovery_jobs_button.setEnabled(selected and bool(status))
        self.recovery_bulk_button.setEnabled(bool(self._recovery_by_account))
        if not selected:
            self.recovery_status_label.setText(
                "Choose an account to review its five-minute recovery policy and saved jobs."
            )
            return
        if not status:
            self.recovery_status_label.setText(
                "Recovery status not yet loaded. Select Refresh recovery."
            )
            return
        event = status.get("event")
        event = event if isinstance(event, dict) else {}
        phase = str(event.get("phase") or "idle").replace("_", " ")
        deadline = event.get("due_at")
        import datetime
        deadline_text = ""
        if isinstance(deadline, (int, float)) and phase in ("grace", "retry"):
            deadline_text = " · Not before " + datetime.datetime.fromtimestamp(
                deadline, datetime.UTC
            ).strftime("%H:%M UTC")
        paused = policy.get("pause_indefinite") is True or (
            isinstance(policy.get("pause_until"), (int, float))
            and policy["pause_until"] > datetime.datetime.now(
                datetime.UTC
            ).timestamp()
        )
        self.recovery_status_label.setText(
            f"{'Enabled' if enabled else 'Off'} · "
            f"{'Paused for browser use' if paused else phase} · "
            f"{'Protected token ready' if available else 'No server lobby token'} · "
            f"{status.get('desired_jobs', 0)} desired / "
            f"{status.get('auto_resume_eligible', 0)} auto-eligible"
            + deadline_text
            + (" · Host supervisor OFF" if not self._recovery_supervisor_enabled else "")
        )

    def _recovery_import(self) -> None:
        aid, _ = self._recovery_selection()
        if aid is None:
            return
        if QMessageBox.question(
            self, "Import saved Gameforge lobby token",
            "Import the selected account's existing server-side IkaBot lobby "
            "credential into the encrypted Daedalus store? No game login or task starts.",
        ) == QMessageBox.Yes:
            self.recovery_import_requested.emit(aid)

    def _recovery_policy(self) -> None:
        aid, status = self._recovery_selection()
        if aid is None or not status:
            return
        policy = status.get("policy") or {}
        if not isinstance(policy, dict):
            return
        enabled = policy.get("enabled") is not True
        question = (
            "Enable automatic game login five minutes after confirmed loss, "
            "plus restoration of approved restart-safe tasks? The new login "
            "can end an active browser session. Pause for browser use to delay it."
            if enabled else "Disable automatic game recovery for this account?"
        )
        if QMessageBox.question(self, "Confirm recovery policy", question) == QMessageBox.Yes:
            self.recovery_policy_requested.emit(aid, enabled, int(policy.get("revision", 0)))

    def _recovery_pause(self, seconds: int | None) -> None:
        aid, _ = self._recovery_selection()
        if aid is not None and QMessageBox.question(
            self, "Pause for browser use",
            "Delay automatic Gameforge sign-in while you use the browser?",
        ) == QMessageBox.Yes:
            self.recovery_pause_requested.emit(aid, seconds)

    def _recovery_resume(self) -> None:
        aid, _ = self._recovery_selection()
        if aid is not None and QMessageBox.question(
            self, "Reconnect this account now",
            "A new Gameforge login can invalidate the game session open in another "
            "browser. Continue with a verified worker and safe job reconciliation?",
        ) == QMessageBox.Yes:
            self.recovery_resume_requested.emit(aid)

    def _recovery_jobs(self) -> None:
        aid, _ = self._recovery_selection()
        if aid is not None:
            self.recovery_jobs_requested.emit(aid)

    def _recovery_bulk(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        values = ["Enable for selected report accounts",
                  "Enable for all configured accounts",
                  "Disable for selected report accounts",
                  "Disable for all configured accounts"]
        choice, ok = QInputDialog.getItem(
            self, "Bulk recovery policy", "Choose exact account scope:", values,
            0, False,
        )
        if not ok:
            return
        all_accounts = "all configured" in choice.lower()
        enabled = choice.startswith("Enable")
        aids = ([a["id"] for a in self._accounts if a.get("enabled") is True]
                if all_accounts else self.selected_report_account_ids())
        if not aids:
            return
        if QMessageBox.question(
            self, "Confirm bulk recovery",
            f"{'Enable' if enabled else 'Disable'} automatic game reconnection for "
            f"{len(aids)} accounts? Enabling can sign your game browser out after "
            "the grace period. Unsupported credentials are skipped.",
        ) == QMessageBox.Yes:
            self.recovery_bulk_requested.emit(aids, enabled)

    def _sync_account_menu(self) -> None:
        self.check_engine_button.setEnabled(bool(self._accounts))
        self.sync_logins_button.setEnabled(
            bool(self._accounts) and self._native_browser_login_enabled
        )
        for action, button in self._menu_actions:
            needs_selection = button in (
                self.edit_button, self.toggle_button, self.remove_button,
            )
            action.setEnabled(
                button.isEnabled() and (not needs_selection or self._selected_account() is not None)
            )

    def _sync_saved_logins(self) -> None:
        self.sync_saved_logins_requested.emit([
            dict(account) for account in self._accounts if account.get("enabled") is True
        ])

    def _toggle_advanced_recovery(self) -> None:
        self._advanced_open = not self._advanced_open
        self.advanced_recovery_panel.setVisible(self._advanced_open)
        self.advanced_recovery_button.setText(
            "Hide advanced recovery" if self._advanced_open else "Advanced recovery"
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
        previous_id = self._selected_visible_id()
        self._updating_report_checks = True
        try:
            _populate(
                self.table,
                [
                    [
                        _account_title(acc),
                        _world_title(acc),
                        acc.get("player"),
                        "", "", "",
                        "",
                    ]
                    for acc in self._accounts
                ],
            )
            for index, account in enumerate(self._accounts):
                self.table.setItem(
                    index, 3,
                    _status_item("✓", "Account enabled", "#2BAF65") if account.get("enabled")
                    else _status_item("✕", "Account disabled", "#D95455"),
                )
                self.table.setItem(index, 4, _session_status_item(account.get("session_status")))
                if self._connected_ids is None:
                    worker_status = _status_item(
                        "?", "IkaBot worker attachment has not been checked", "#8D96A3",
                    )
                elif account.get("id") in self._connected_ids:
                    worker_status = _status_item(
                        "✓", "An IkaBot worker is attached", "#2BAF65",
                    )
                else:
                    worker_status = _status_item(
                        "✕", "No IkaBot worker is attached", "#D95455",
                    )
                self.table.setItem(index, 5, worker_status)
                item = self.table.item(index, 6)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Unchecked if account.get("id") in self._excluded_report_ids else Qt.Checked
                )
                item.setToolTip("Include in read-only warehouse reporting")
        finally:
            self._updating_report_checks = False
        if previous_id is not None:
            new_index = next(
                (i for i, row in enumerate(self._accounts) if row.get("id") == previous_id),
                -1,
            )
            if new_index >= 0:
                self.table.selectRow(new_index)
        self._update_select_all_reports()
        self._update_assistance_buttons()

    def account_record(self, account_id: str) -> dict[str, object] | None:
        return next((dict(record) for record in self._accounts
                     if record.get("id") == account_id), None)

    def set_native_browser_login_enabled(self, enabled: bool) -> None:
        self._native_browser_login_enabled = enabled
        self.native_login_status.setText(
            "Manual browser recovery available as a fallback."
            if enabled else
            "This backend has not enabled secure Gameforge session handoff."
        )
        if not enabled:
            self.auto_login_status.setText("Automatic login requires an enabled secure backend.")
        else:
            self.auto_login_status.setText(
                "Headless Chrome signs in automatically. If a CAPTCHA appears, "
                "complete it in the temporary visible Chrome window."
            )
        self._update_assistance_buttons()

    def _auto_this(self) -> None:
        account_id = self._selected_visible_id()
        account = self.account_record(account_id) if account_id else None
        if self._native_browser_login_enabled and not self._auto_login_busy and account and account.get("enabled"):
            self.automatic_login_requested.emit([account_id])

    def _auto_all(self) -> None:
        if not self._native_browser_login_enabled or self._auto_login_busy:
            return
        account_ids = [
            account["id"] for account in self._accounts
            if isinstance(account.get("id"), str) and account.get("enabled") is True
        ]
        if account_ids:
            self.automatic_login_requested.emit(account_ids)

    def _auto_selected(self) -> None:
        from daedalus.desktop.account_scope import AccountSelectionDialog

        if not self._native_browser_login_enabled or self._auto_login_busy:
            return
        enabled = [
            row for row in self._accounts
            if isinstance(row.get("id"), str) and row.get("enabled") is True
        ]
        dialog = AccountSelectionDialog(enabled, [row["id"] for row in enabled],
                                        self, title="Choose Gameforge sign-ins")
        if dialog.exec() == QDialog.Accepted:
            self.automatic_login_requested.emit(dialog.selected_ids())

    def set_automatic_login_busy(self, busy: bool, status: str = "") -> None:
        self._auto_login_busy = bool(busy)
        self.auto_cancel_button.setEnabled(busy)
        self.auto_cancel_button.setVisible(bool(busy))
        if status:
            self.auto_login_status.setText(status)
        # Keep the final receipt readable after the child/HTTP workers finish.
        # Previously success/failure disappeared as soon as busy became false.
        self.auto_login_status.setVisible(bool(status))
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
        self._update_recovery_controls()
        selected = self.account_record(account_id) if account_id else None
        if selected:
            session = str(selected.get("session_status") or "not_connected")
            message = {
                "authenticated": "Session verified. Warehouse reports and eligible automations are available.",
                "needs_assistance": "Session needs sign-in. Use automatic headless login; only CAPTCHA requires input.",
                "paused": "Worker is paused. Inspect session status before resuming any operation.",
                "not_connected": "No game worker is connected. A verified world cookie may be saved for later attachment; check the Worker column.",
                "disabled": "Account is disabled on the authoritative backend.",
            }.get(session, "Session: " + session.replace("_", " "))
            self.selected_account_summary.set_status(
                _account_title(selected),
                message,
            )
        else:
            self.selected_account_summary.set_status(
                "Choose an account", "Select a row for status and sign-in options."
            )
        if selected:
            label = _account_title(selected)
            session = str(selected.get("session_status") or "not_connected")
            friendly = {
                "authenticated": "Session ready",
                "not_connected": "Not connected",
                "needs_assistance": "Sign-in needed",
                "failed": "Login failed",
                "paused": "Paused",
                "validating_session": "Verifying session",
                "validating_handoff": "Verifying login",
                "assisted_login": "Assisted login",
            }.get(session, "Status unknown")
            self.selection_status.setText(f"{label}  ·  {friendly}")
        else:
            self.selection_status.setText(
                f"{len(self._accounts)} accounts" if self._accounts
                else "No accounts yet — use Add account"
            )
        editing = self._edit_revision is not None
        self.edit_button.setEnabled(editing)
        self.toggle_button.setEnabled(editing)
        self.remove_button.setEnabled(editing)
        allowed = self._native_browser_login_enabled and not self._auto_login_busy
        self.native_browser_login_button.setEnabled(
            allowed and account_id is not None
            and selected is not None and selected.get("enabled") is True
        )
        self.auto_login_button.setEnabled(
            allowed and account_id is not None and selected is not None
            and selected.get("enabled") is True
        )
        self.auto_login_all_button.setEnabled(allowed and any(
            a.get("enabled") is True for a in self._accounts
        ))
        self.auto_login_selected_button.setEnabled(self.auto_login_all_button.isEnabled())
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
        self.create_button.setEnabled(enabled)
        self._update_assistance_buttons()
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(SubtitleLabel("Operations"))
        header.addStretch(1)
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("Search operations")
        self.search_input.setMaximumWidth(230)
        self.search_input.textChanged.connect(self._render)
        header.addWidget(self.search_input)
        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_button)
        self.configure_button = PrimaryPushButton("Configure…")
        self.configure_button.clicked.connect(self._configure_selected)
        self.configure_button.setEnabled(False)
        header.addWidget(self.configure_button)
        layout.addLayout(header)
        self.table = _table(["Operation", "Kind", "Module", "Parameters"])
        self.table.setAccessibleName("IkaBot operation catalog")
        self.table.setToolTip("Read-only catalog. Double-click a background task to configure it.")
        self.table.itemSelectionChanged.connect(self._update_configure)
        self.table.cellDoubleClicked.connect(lambda *_args: self._configure_selected())
        layout.addWidget(self.table, 1)
        # Leave read-only mode explicit for accessibility and callers without
        # showing a permanent disclaimer above the table.
        self.status_label = CaptionLabel(
            "Read-only catalog. Background tasks can be configured in Automations."
        )
        self.status_label.hide()

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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(SubtitleLabel("Warehouses"))
        header.addStretch(1)
        self.load_all_button = PrimaryPushButton("All accounts")
        self.load_all_button.setAccessibleName("Load warehouses for all accounts")
        self.load_all_button.setToolTip(
            "Read-only snapshots for every account; unavailable accounts remain identified"
        )
        self.load_all_button.clicked.connect(self._load_all)
        self.load_all_button.setEnabled(False)
        header.addWidget(self.load_all_button)
        self.load_selected_button = PushButton("Selected")
        self.load_selected_button.setToolTip("Load the saved warehouse report selection")
        self.load_selected_button.clicked.connect(self._load_selected)
        self.load_selected_button.setEnabled(False)
        header.addWidget(self.load_selected_button)
        self.choose_accounts_button = PushButton("Choose…")
        self.choose_accounts_button.setAccessibleName("Choose accounts for combined warehouse reports")
        self.choose_accounts_button.clicked.connect(self._choose_accounts)
        self.choose_accounts_button.setEnabled(False)
        header.addWidget(self.choose_accounts_button)
        layout.addLayout(header)

        options = QHBoxLayout()
        options.setSpacing(8)
        self.account_combo = ComboBox()
        self.account_combo.setAccessibleName("Inspect single warehouse account")
        self.account_combo.setMinimumWidth(130)
        self.account_combo.setMaximumWidth(200)
        options.addWidget(self.account_combo)
        self.load_button = PushButton("Load one")
        self.load_button.clicked.connect(self._load)
        self.load_button.setToolTip("Read-only warehouse report for this account only")
        options.addWidget(self.load_button)
        self.only_220k = CheckBox("220K+")
        self.only_220k.setToolTip("Only cities with at least 220,000 known unsecured resources")
        self.only_220k.stateChanged.connect(self._render)
        options.addWidget(self.only_220k)
        self.group_island = CheckBox("By island")
        self.group_island.setToolTip("Group city rows by world and island coordinates")
        self.group_island.stateChanged.connect(self._render)
        options.addWidget(self.group_island)
        options.addStretch(1)

        self.print_button = PushButton("Print…")
        self.print_button.setAccessibleName("Preview and print the combined warehouse report")
        self.print_button.clicked.connect(self._print_report)
        self.print_button.setEnabled(False)
        options.addWidget(self.print_button)

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
        self.export_button = PushButton("Export ▾")
        self.export_button.setAccessibleName("Copy or save the current warehouse report")
        menu = QMenu(self)
        for label, button in (
            ("Copy CSV", self.copy_button),
            ("Copy by island", self.copy_islands_button),
            ("Print grouped report…", self.print_button),
            ("Save CSV…", self.csv_button),
            ("Save JSON…", self.json_button),
            ("Save TXT…", self.txt_button),
        ):
            action = menu.addAction(label)
            action.triggered.connect(button.click)
        self.export_button.setMenu(menu)
        self.export_button.setEnabled(False)
        options.addWidget(self.export_button)
        layout.addLayout(options)

        self.table = _table(list(self._COLUMNS))
        self.table.setAccessibleName("Warehouse resources grouped across selected accounts")
        self.table.setToolTip("— means unknown, not zero. Export retains this distinction.")
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        for index, width in enumerate((155, 94, 94, 90, 90, 90, 90, 90, 100, 135, 87, 140)):
            self.table.setColumnWidth(index, width)
        self.status_label = CaptionLabel("No warehouse snapshots loaded")
        layout.addWidget(self.status_label)
        layout.addWidget(self.table, 1)
        self.demo_note = CaptionLabel("")
        self.demo_note.hide()
        layout.addWidget(self.demo_note)

    def set_demo(self, enabled: bool) -> None:
        self.demo_note.setText(
            "SYNTHETIC DEMO · sample amounts only" if enabled else ""
        )
        self.demo_note.setVisible(enabled)

    def set_accounts(self, accounts: list[dict[str, object]]) -> None:
        previous = self.selected_account_id()
        self._accounts = {str(account["id"]): account for account in accounts if account.get("id")}
        self._account_ids = list(self._accounts)
        self.account_combo.clear()
        for account in self._accounts.values():
            self.account_combo.addItem(account_display_name(account))
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
            explanation=(
                "Select accounts for combined read-only warehouse reports. "
                "No game tasks are started; unavailable snapshots appear separately."
            ),
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
                account_display_name(self._accounts.get(aid, {"id": aid}))
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
                report_txt_islands(self._rows) if self.group_island.isChecked()
                else report_txt(self._rows, group_by_island=False)
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
        QGuiApplication.clipboard().setText(report_txt_islands(self._rows))

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
            else (report_txt_islands(self._rows) if self.group_island.isChecked()
                  else report_txt(self._rows, group_by_island=False))
        )
        with open(filename, "w", encoding="utf-8", newline="") as handle:
            handle.write(output)
