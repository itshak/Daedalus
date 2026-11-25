"""Offline, nonsecret presentation controls for the native Fluent client."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMessageBox, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.design_system import PageHeading
from daedalus.gui_preferences import GuiPreferences

_THEME_LABELS = ("System", "Light", "Dark")
_THEME_VALUES = ("auto", "light", "dark")


class AppearancePage(QWidget):
    """Safe UI-only settings: no browser, password or game-session controls."""

    preferences_changed = Signal(object)
    connection_settings_requested = Signal()
    report_accounts_requested = Signal()
    report_all_requested = Signal()
    administrative_status_requested = Signal(str)
    notification_settings_requested = Signal(str, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appearance_page")
        self._updating = False
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        scroll.setWidget(content)
        shell.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(PageHeading(
            "Settings", "Personalize Daedalus without changing your backend's game sessions.",
            self,
        ))
        layout.addWidget(SubtitleLabel("Appearance"))
        layout.addWidget(BodyLabel("Theme"))
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(_THEME_LABELS)
        self.theme_combo.setMaximumWidth(220)
        layout.addWidget(self.theme_combo)
        layout.addWidget(SubtitleLabel("Warehouse reporting"))
        self.only_220k = CheckBox("Filter to 220K+ unsecured resources by default")
        layout.addWidget(self.only_220k)
        self.group_island = CheckBox("Group warehouse results by island by default")
        layout.addWidget(self.group_island)
        self.report_scope_status = CaptionLabel(
            "Connect to manage the accounts included in combined warehouse reports."
        )
        self.report_scope_status.setWordWrap(True)
        layout.addWidget(self.report_scope_status)
        report_actions = QHBoxLayout()
        self.report_all_button = PushButton("Include all accounts")
        self.report_all_button.setEnabled(False)
        self.report_all_button.clicked.connect(self.report_all_requested.emit)
        report_actions.addWidget(self.report_all_button)
        self.report_choose_button = PushButton("Choose report accounts…")
        self.report_choose_button.setEnabled(False)
        self.report_choose_button.clicked.connect(self.report_accounts_requested.emit)
        report_actions.addWidget(self.report_choose_button)
        report_actions.addStretch(1)
        layout.addLayout(report_actions)
        layout.addWidget(SubtitleLabel("Connection"))
        self.connection_button = PushButton("Manage secure connection…")
        self.connection_button.clicked.connect(self.connection_settings_requested.emit)
        layout.addWidget(self.connection_button)
        layout.addWidget(SubtitleLabel("Protected administration"))
        self.admin_account = ComboBox()
        self.admin_account.setAccessibleName("Administrative status account")
        self.admin_refresh = PushButton("Read protected settings status")
        self.admin_refresh.setEnabled(False)
        self.admin_refresh.clicked.connect(self._request_admin_status)
        self.admin_account.currentIndexChanged.connect(self._admin_selection_changed)
        layout.addWidget(self.admin_account)
        layout.addWidget(self.admin_refresh)
        self.admin_note = CaptionLabel("Select an enabled account. No credentials will be displayed.")
        self.admin_note.setWordWrap(True)
        layout.addWidget(self.admin_note)
        self.admin_rows = BodyLabel()
        self.admin_rows.setWordWrap(True)
        layout.addWidget(self.admin_rows)
        layout.addWidget(SubtitleLabel("Notification configuration"))
        notice = CaptionLabel("These are worker-global defaults, shared by game accounts on that worker host. "
                              "Existing legacy per-user overrides require local reconciliation. "
                              "Replacement sends one fixed test message before saving. Credentials are never returned.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.notification_provider = ComboBox()
        self.notification_provider.addItems(["Telegram", "Discord"])
        self.notification_provider.currentIndexChanged.connect(self._notification_changed)
        layout.addWidget(self.notification_provider)
        self.notification_secret = LineEdit()
        self.notification_secret.setEchoMode(QLineEdit.Password)
        self.notification_secret.setAccessibleName("Write-only notification credential")
        layout.addWidget(self.notification_secret)
        self.notification_chat = LineEdit()
        self.notification_chat.setEchoMode(QLineEdit.Password)
        self.notification_chat.setAccessibleName("Write-only Telegram chat identifier")
        self.notification_chat.setPlaceholderText("Telegram chat ID")
        layout.addWidget(self.notification_chat)
        self.notification_confirm = CheckBox("I approve changing the worker-global notification default")
        layout.addWidget(self.notification_confirm)
        actions = QHBoxLayout()
        self.notification_save = PushButton("Test and save")
        self.notification_clear = PushButton("Clear configured default")
        self.notification_save.clicked.connect(lambda: self._configure_notification(False))
        self.notification_clear.clicked.connect(lambda: self._configure_notification(True))
        actions.addWidget(self.notification_save)
        actions.addWidget(self.notification_clear)
        layout.addLayout(actions)
        self.notification_note = CaptionLabel()
        self.notification_note.setWordWrap(True)
        layout.addWidget(self.notification_note)
        self.notification_confirm.stateChanged.connect(self._notification_controls)
        self.notification_secret.textChanged.connect(self._notification_controls)
        self.notification_chat.textChanged.connect(self._notification_controls)
        self._notification_changed()
        boundary = CaptionLabel(
             "Proxy configuration, challenge handling and custom extensions "
            "are managed on the authenticated worker host. The raw engine web service, developer "
            "cookie dump and unverified update commands are not exposed. Use Daedalus for remote control "
            "and the reviewed release workflow for updates.")
        boundary.setWordWrap(True)
        layout.addWidget(boundary)
        layout.addStretch(1)
        self.theme_combo.currentIndexChanged.connect(self._changed)
        self.only_220k.stateChanged.connect(self._changed)
        self.group_island.stateChanged.connect(self._changed)

    def set_admin_accounts(self, accounts: list[dict[str, object]]) -> None:
        from daedalus.account_display import account_player_name

        current = self.admin_account.currentData()
        self.admin_account.blockSignals(True)
        try:
            self.admin_account.clear()
            self.admin_account.addItem("Choose an account", userData=None)
            for row in accounts:
                if row.get("enabled") is True and isinstance(row.get("id"), str):
                    self.admin_account.addItem(
                        f"{account_player_name(row)} · {row.get('world') or ''}", userData=row["id"])
            for index in range(self.admin_account.count()):
                if self.admin_account.itemData(index) == current:
                    self.admin_account.setCurrentIndex(index)
                    break
        finally:
            self.admin_account.blockSignals(False)
        self._admin_selection_changed()

    def _admin_selection_changed(self, *_args) -> None:
        self.admin_rows.clear()
        self.admin_note.setText("Select an enabled account and refresh. No credentials will be displayed.")
        self.admin_refresh.setEnabled(isinstance(self.admin_account.currentData(), str))
        if hasattr(self, "notification_secret"):
            self._notification_changed()

    def _notification_changed(self, *_args):
        self.notification_secret.clear()
        self.notification_chat.clear()
        self.notification_confirm.setChecked(False)
        self.notification_note.clear()
        telegram = self.notification_provider.currentIndex() == 0
        self.notification_secret.setPlaceholderText("New Telegram bot token" if telegram else "New Discord webhook URL")
        self.notification_chat.setVisible(telegram)
        self._notification_controls()

    def _notification_controls(self, *_args):
        ready = isinstance(self.admin_account.currentData(), str) and self.notification_confirm.isChecked()
        self.notification_save.setEnabled(ready and bool(self.notification_secret.text().strip()) and
            (self.notification_provider.currentIndex() != 0 or bool(self.notification_chat.text().strip())))
        self.notification_clear.setEnabled(ready)

    def _configure_notification(self, clear):
        account = self.admin_account.currentData()
        if not isinstance(account, str) or not self.notification_confirm.isChecked():
            return
        provider = "telegram" if self.notification_provider.currentIndex() == 0 else "discord"
        if clear:
            if QMessageBox.question(self, "Clear notification default",
                    f"Clear the worker-global {provider} default for all accounts using it?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            settings = {"mode": "clear"}
        elif provider == "telegram":
            settings = {"mode": "replace", "bot_token": self.notification_secret.text().strip(),
                        "chat_id": self.notification_chat.text().strip()}
        else:
            settings = {"mode": "replace", "webhook_url": self.notification_secret.text().strip()}
        self.notification_secret.clear()
        self.notification_chat.clear()
        self.notification_confirm.setChecked(False)
        self.notification_note.setText("Submitting encrypted provider configuration…")
        self.notification_settings_requested.emit(account, provider, settings)

    def set_notification_result(self, result):
        if result.get("account_id") == self.admin_account.currentData():
            self.admin_rows.clear()
            self.notification_note.setText(
                "Worker-global notification default saved after successful provider test."
                if result.get("result") == "configured" else "Worker-global notification default cleared.")

    def set_notification_unavailable(self, account):
        if account == self.admin_account.currentData():
            self.admin_rows.clear()
            self.notification_note.setText("Configuration unavailable or outcome uncertain. Refresh status before retrying.")

    def _request_admin_status(self) -> None:
        account = self.admin_account.currentData()
        if isinstance(account, str):
            self.admin_rows.clear()
            self.admin_note.setText("Reading protected settings…")
            self.administrative_status_requested.emit(account)

    def set_admin_unavailable(self, account_id: str) -> None:
        if self.admin_account.currentData() == account_id:
            self.admin_rows.clear()
            self.admin_note.setText("Protected settings unavailable for this account.")

    def set_admin_status(self, data: dict[str, object]) -> None:
        from daedalus.admin_status import validate_admin_status

        if data.get("account_id") != self.admin_account.currentData():
            return
        try:
            value = validate_admin_status(data.get("settings"))
        except ValueError:
            self.set_admin_unavailable(str(data.get("account_id")))
            return
        proxy = "Disabled"
        if value["proxy_enabled"]:
            proxy = (f"Enabled · {value['proxy_protocol'] or 'Unknown protocol'} · "
                     f"port {value['proxy_port'] or 'unknown'} · authentication "
                     + ("unknown" if value["proxy_auth"] is None else
                        "configured" if value["proxy_auth"] else "not configured"))
        count = value["registered_extensions"]
        self.admin_note.setText("Observed saved configuration; connectivity has not been tested.")
        self.admin_rows.setText(
            f"Telegram: {value['telegram'].replace('_', ' ')}\n"
            f"Discord: {value['discord'].replace('_', ' ')}\n"
            f"Proxy: {proxy}\nChallenge provider: {value['challenge_provider']}\n"
            f"Registered custom extensions: {count if count is not None else 'Unknown'}")

    def set_report_scope(self, total: int, selected: int) -> None:
        """Display the local per-backend scope; no account/session mutations."""
        self.report_scope_status.setText(
            f"{selected} of {total} accounts included in combined warehouse reports."
            if total else "No accounts available. Connect to manage report selection."
        )
        self.report_all_button.setEnabled(total > 0 and selected < total)
        self.report_choose_button.setEnabled(total > 0)

    def set_preferences(self, prefs: GuiPreferences) -> None:
        self._updating = True
        try:
            self.theme_combo.setCurrentIndex(_THEME_VALUES.index(prefs.theme))
            self.only_220k.setChecked(prefs.only_220k)
            self.group_island.setChecked(prefs.group_by_island)
        finally:
            self._updating = False

    def _changed(self, *_args: object) -> None:
        if self._updating:
            return
        self.preferences_changed.emit({
            "theme": _THEME_VALUES[self.theme_combo.currentIndex()],
            "only_220k": self.only_220k.isChecked(),
            "group_by_island": self.group_island.isChecked(),
        })
