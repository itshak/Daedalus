"""Offline, nonsecret presentation controls for the native Fluent client."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
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
    release_status_requested = Signal()
    extension_settings_requested = Signal(str, object)

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
        layout.addWidget(SubtitleLabel("Releases and diagnostics"))
        from daedalus import __version__
        from daedalus.release_catalog import build_revision

        self.release_note = CaptionLabel(
            f"Desktop version {__version__} · build {build_revision() or 'unknown'}")
        self.release_note.setWordWrap(True)
        layout.addWidget(self.release_note)
        self.release_check = PushButton("Check published Mac preview")
        self.release_check.clicked.connect(self.release_status_requested.emit)
        layout.addWidget(self.release_check)
        self.release_result = BodyLabel()
        self.release_result.setWordWrap(True)
        layout.addWidget(self.release_result)
        self.release_download = PushButton("Open reviewed release and checksum")
        self.release_download.setEnabled(False)
        self.release_download.clicked.connect(self._open_release)
        layout.addWidget(self.release_download)
        self._release_url = None
        release_warning = CaptionLabel(
            "Published previews are not notarized. Verify the checksum before installation. "
            "Controller updates and rollback use the reviewed host release workflow, not a remote shell.")
        release_warning.setWordWrap(True)
        layout.addWidget(release_warning)
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
        layout.addWidget(SubtitleLabel("Host-approved extensions"))
        self.extension_note = CaptionLabel(
            "Only extensions installed and hash-approved by the host administrator are listed. "
            "Registration changes the shared default menu; it does not run or delete code.")
        self.extension_note.setWordWrap(True)
        layout.addWidget(self.extension_note)
        self.extension_refresh = PushButton("Read approved extensions")
        self.extension_refresh.clicked.connect(self._request_extensions)
        self.extension_refresh.setEnabled(False)
        layout.addWidget(self.extension_refresh)
        self.extension_picker = ComboBox()
        self.extension_picker.setAccessibleName("Host-approved extension")
        self.extension_picker.currentIndexChanged.connect(self._extension_controls)
        layout.addWidget(self.extension_picker)
        self.extension_toggle = PushButton("Change registration…")
        self.extension_toggle.setEnabled(False)
        self.extension_toggle.clicked.connect(self._change_extension)
        layout.addWidget(self.extension_toggle)
        self.extension_status = CaptionLabel()
        self.extension_status.setWordWrap(True)
        layout.addWidget(self.extension_status)
        self._extension_rows = []
        self._extension_override = True
        boundary = CaptionLabel(
             "Proxy configuration, challenge handling and legacy unreviewed extensions "
            "are managed on the authenticated worker host. The raw engine web service, developer "
            "cookie dump and unverified update commands are not exposed. Use Daedalus for remote control "
            "and the reviewed release workflow for updates.")
        boundary.setWordWrap(True)
        layout.addWidget(boundary)
        layout.addStretch(1)
        self.theme_combo.currentIndexChanged.connect(self._changed)
        self.only_220k.stateChanged.connect(self._changed)
        self.group_island.stateChanged.connect(self._changed)

    def _open_release(self):
        if self._release_url:
            QDesktopServices.openUrl(QUrl(self._release_url))

    def set_release_status(self, data):
        from daedalus.release_catalog import build_revision, validate_release_status

        self._release_url = None
        self.release_download.setEnabled(False)
        try:
            result = validate_release_status(data)
        except ValueError:
            self.release_result.setText("Release metadata unavailable")
            return
        current = result["controller_revision"] or "unknown"
        lines = [f"Controller {result['controller_version']} · build {current}"]
        preview = result["preview"]
        if preview:
            local = build_revision()
            comparison = ("Matches installed desktop build" if local and local.startswith(preview["revision_prefix"])
                          else "Different build available; review before installation" if local
                          else "Installed desktop build revision unknown")
            lines.extend([f"Published preview: {preview['tag']} · {preview['published_at']}", comparison])
            self._release_url = preview["release_url"]
            self.release_download.setEnabled(True)
        else:
            lines.append("Public preview unavailable or no verified catalog entry")
        self.release_result.setText("\n".join(lines))

    def set_release_unavailable(self):
        self._release_url = None
        self.release_download.setEnabled(False)
        self.release_result.setText("Release metadata unavailable. Reconnect and check again.")

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
        if hasattr(self, "extension_picker"):
            self._reset_extensions()

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

    def _reset_extensions(self):
        self._extension_rows = []
        self._extension_override = True
        self.extension_picker.clear()
        self.extension_status.clear()
        self.extension_refresh.setEnabled(isinstance(self.admin_account.currentData(), str))
        self.extension_toggle.setEnabled(False)

    def _extension_controls(self, *_args):
        index = self.extension_picker.currentIndex()
        row = self._extension_rows[index] if 0 <= index < len(self._extension_rows) else None
        self.extension_toggle.setEnabled(bool(row and not self._extension_override
                                               and (row["verified"] or row["registered"])))
        self.extension_toggle.setText("Unregister…" if row and row["registered"] else "Register…")

    def _request_extensions(self):
        account = self.admin_account.currentData()
        if isinstance(account, str):
            self._reset_extensions()
            self.extension_status.setText("Reading locally approved extensions…")
            self.extension_settings_requested.emit(account, None)

    def _change_extension(self):
        account = self.admin_account.currentData()
        index = self.extension_picker.currentIndex()
        if not isinstance(account, str) or not self.extension_toggle.isEnabled() or not 0 <= index < len(self._extension_rows):
            return
        row = self._extension_rows[index]
        register = not row["registered"]
        if QMessageBox.question(self, "Review worker-global registration",
                f"{'Register' if register else 'Unregister'} {row['name']}?\nSHA-256: {row['sha256']}\n"
                "This changes the shared default for the worker host. No extension will be executed.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._reset_extensions()
        self.extension_status.setText("Updating reviewed registration…")
        self.extension_settings_requested.emit(account, {"id": row["id"], "sha256": row["sha256"],
            "registered": register, "expected_registered": row["registered"], "confirmed_global": True})

    def set_extension_status(self, result):
        from daedalus.extension_settings import validate_extension_status

        account = self.admin_account.currentData()
        if not isinstance(result, dict) or result.get("account_id") != account:
            return
        self._reset_extensions()
        try:
            result = validate_extension_status(result, account)
        except ValueError:
            self.extension_status.setText("Approved extension inventory unavailable")
            return
        self._extension_override = result["legacy_override"]
        self._extension_rows = result["extensions"]
        for row in self._extension_rows:
            label = "registered" if row["registered"] else "not registered"
            self.extension_picker.addItem(f"{row['name']} · {label} · {'verified' if row['verified'] else 'hash mismatch'}")
        self.extension_status.setText(
            f"{len(self._extension_rows)} locally approved; {result['unreviewed_count']} legacy registrations. "
            + ("Local per-user override blocks changes." if self._extension_override else
               "Unreviewed modules require host-local reconciliation."))
        self._extension_controls()

    def set_extension_unavailable(self, account):
        if self.admin_account.currentData() == account:
            self._reset_extensions()
            self.extension_status.setText("Extension settings unavailable or changed. Refresh before retrying.")

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
