"""Offline, nonsecret presentation controls for the native Fluent client."""

from __future__ import annotations

from datetime import UTC

from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    Pivot,
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
    challenge_policy_requested = Signal(str, object)
    proxy_profiles_requested = Signal(str, object)
    world_reports_requested = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appearance_page")
        self._updating = False
        shell = QVBoxLayout(self)
        shell.setContentsMargins(20, 16, 20, 12)
        shell.setSpacing(8)
        shell.addWidget(PageHeading("Settings", "Appearance, reports and protected server settings."))
        self.sections = Pivot(self)
        self.sections.setAccessibleName("Settings sections")
        shell.addWidget(self.sections)
        self.admin_bar = QWidget(self)
        account_row = QHBoxLayout(self.admin_bar)
        account_row.setContentsMargins(0, 0, 0, 0)
        account_row.addWidget(BodyLabel("Account"))
        self.admin_account = ComboBox()
        self.admin_account.setAccessibleName("Administrative status account")
        self.admin_account.currentIndexChanged.connect(self._admin_selection_changed)
        account_row.addWidget(self.admin_account, 1)
        shell.addWidget(self.admin_bar)
        self.section_stack = QStackedWidget(self)
        shell.addWidget(self.section_stack, 1)
        self.section_keys = ("general", "status", "notifications", "security", "reports", "network")

        def section(key, title):
            scroll = QScrollArea(self.section_stack)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            content = QWidget(scroll)
            scroll.setWidget(content)
            panel = QVBoxLayout(content)
            panel.setContentsMargins(0, 6, 8, 6)
            panel.setSpacing(9)
            index = self.section_stack.addWidget(scroll)
            self.sections.addItem(routeKey=key, text=title, onClick=lambda: self.select_section(index))
            return panel

        layout = section("general", "General")
        layout.addWidget(SubtitleLabel("Appearance"))
        theme_row = QHBoxLayout()
        theme_row.addWidget(BodyLabel("Theme"))
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(_THEME_LABELS)
        self.theme_combo.setMaximumWidth(220)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)
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
        layout.addWidget(self.connection_button, 0, Qt.AlignLeft)
        layout.addWidget(SubtitleLabel("Releases and diagnostics"))
        from daedalus import __version__
        from daedalus.release_catalog import build_revision

        self.release_note = CaptionLabel(
            f"Desktop version {__version__} · build {build_revision() or 'unknown'}")
        self.release_note.setWordWrap(True)
        layout.addWidget(self.release_note)
        self.release_check = PushButton("Check published Mac preview")
        self.release_check.clicked.connect(self.release_status_requested.emit)
        release_actions = QHBoxLayout()
        release_actions.addWidget(self.release_check)
        self.release_result = BodyLabel()
        self.release_result.setWordWrap(True)

        self.release_download = PushButton("Open reviewed release and checksum")
        self.release_download.setEnabled(False)
        self.release_download.clicked.connect(self._open_release)
        release_actions.addWidget(self.release_download)
        release_actions.addStretch(1)
        layout.addLayout(release_actions)
        layout.addWidget(self.release_result)
        self._release_url = None
        release_warning = CaptionLabel(
            "Mac previews are not notarized. Verify the checksum before installing.")
        release_warning.setWordWrap(True)
        layout.addWidget(release_warning)
        layout.addStretch(1)
        layout = section("status", "Status")
        layout.addWidget(SubtitleLabel("Protected settings"))
        self.admin_refresh = PushButton("Read protected settings status")
        self.admin_refresh.setEnabled(False)
        self.admin_refresh.clicked.connect(self._request_admin_status)
        layout.addWidget(self.admin_refresh, 0, Qt.AlignLeft)
        self.admin_note = CaptionLabel("Select an enabled account. No credentials will be displayed.")
        self.admin_note.setWordWrap(True)
        layout.addWidget(self.admin_note)
        self.admin_rows = BodyLabel()
        self.admin_rows.setWordWrap(True)
        layout.addWidget(self.admin_rows)
        layout.addStretch(1)
        layout = section("notifications", "Notifications")
        layout.addWidget(SubtitleLabel("Notification defaults"))
        notice = CaptionLabel("Shared worker defaults. Saving sends one test message; legacy overrides require local reconciliation.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.notification_provider = ComboBox()
        self.notification_provider.addItems(["Telegram", "Discord"])
        self.notification_provider.currentIndexChanged.connect(self._notification_changed)
        provider_row = QHBoxLayout()
        provider_row.addWidget(BodyLabel("Provider"))
        provider_row.addWidget(self.notification_provider, 1)
        layout.addLayout(provider_row)
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
        layout.addStretch(1)
        layout = section("security", "Security")
        layout.addWidget(SubtitleLabel("Game challenges"))
        challenge_note = CaptionLabel(
            "Automation stops for a human challenge. Optionally send a notification; review a new launch after completion.")
        challenge_note.setWordWrap(True)
        layout.addWidget(challenge_note)
        self.challenge_read = PushButton("Read challenge policy")
        self.challenge_read.setEnabled(False)
        self.challenge_read.clicked.connect(self._request_challenge_policy)
        challenge_row = QHBoxLayout()
        challenge_row.addWidget(self.challenge_read)
        self.challenge_mode = ComboBox()
        self.challenge_mode.addItems(["Stop for human attention", "Notify and stop"])
        self.challenge_mode.setEnabled(False)
        self.challenge_mode.currentIndexChanged.connect(self._challenge_controls)
        challenge_row.addWidget(self.challenge_mode, 1)
        self.challenge_save = PushButton("Save human challenge policy…")
        self.challenge_save.setEnabled(False)
        self.challenge_save.clicked.connect(self._save_challenge_policy)
        challenge_row.addWidget(self.challenge_save)
        layout.addLayout(challenge_row)
        self.challenge_status = CaptionLabel()
        self.challenge_status.setWordWrap(True)
        layout.addWidget(self.challenge_status)
        self._challenge_policy = None
        layout.addWidget(SubtitleLabel("Host-approved extensions"))
        self.extension_note = CaptionLabel(
            "Host-approved extensions only. Registration changes the shared menu; no code runs or is deleted.")
        self.extension_note.setWordWrap(True)
        layout.addWidget(self.extension_note)
        self.extension_refresh = PushButton("Read approved extensions")
        self.extension_refresh.clicked.connect(self._request_extensions)
        self.extension_refresh.setEnabled(False)
        extension_row = QHBoxLayout()
        extension_row.addWidget(self.extension_refresh)
        self.extension_picker = ComboBox()
        self.extension_picker.setAccessibleName("Host-approved extension")
        self.extension_picker.currentIndexChanged.connect(self._extension_controls)
        extension_row.addWidget(self.extension_picker, 1)
        self.extension_toggle = PushButton("Change registration…")
        self.extension_toggle.setEnabled(False)
        self.extension_toggle.clicked.connect(self._change_extension)
        extension_row.addWidget(self.extension_toggle)
        layout.addLayout(extension_row)
        self.extension_status = CaptionLabel()
        self.extension_status.setWordWrap(True)
        layout.addWidget(self.extension_status)
        self._extension_rows = []
        self._extension_override = True
        layout.addStretch(1)
        layout = section("reports", "Map reports")
        layout.addWidget(SubtitleLabel("World map reports"))
        report_note = CaptionLabel("Completed scans, with island-only CSV exports.")
        report_note.setWordWrap(True)
        layout.addWidget(report_note)
        self.world_refresh = PushButton("Read completed map reports")
        self.world_refresh.setEnabled(False)
        self.world_refresh.clicked.connect(self._request_world_reports)
        world_row = QHBoxLayout()
        world_row.addWidget(self.world_refresh)
        self.world_picker = ComboBox()
        self.world_picker.setAccessibleName("Completed aggregate world map report")
        self.world_picker.currentIndexChanged.connect(self._world_controls)
        world_row.addWidget(self.world_picker, 1)
        self.world_export = PushButton("Export selected report to CSV…")
        self.world_export.setEnabled(False)
        self.world_export.clicked.connect(self._request_world_export)
        layout.addLayout(world_row)
        layout.addWidget(self.world_export, 0, Qt.AlignLeft)
        self.world_note = CaptionLabel()
        self.world_note.setWordWrap(True)
        layout.addWidget(self.world_note)
        self._world_metadata = []
        layout.addStretch(1)
        layout = section("network", "Network")
        layout.addWidget(SubtitleLabel("Approved proxy profiles"))
        proxy_note = CaptionLabel("Idle accounts only. Test uses a fixed HTTPS endpoint; no automatic switching or reconnect.")
        proxy_note.setWordWrap(True)
        layout.addWidget(proxy_note)
        self.proxy_read = PushButton("Read approved profiles")
        self.proxy_read.setEnabled(False)
        self.proxy_read.clicked.connect(self._read_proxy_profiles)
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.proxy_read)
        self.proxy_picker = ComboBox()
        self.proxy_picker.setAccessibleName("Approved network profile")
        self.proxy_picker.currentIndexChanged.connect(self._proxy_controls)
        profile_row.addWidget(self.proxy_picker, 1)
        layout.addLayout(profile_row)
        self.proxy_test = PushButton("Test selected profile…")
        self.proxy_test.setEnabled(False)
        self.proxy_test.clicked.connect(lambda: self._submit_proxy_profile("test"))
        profile_actions = QHBoxLayout()
        profile_actions.addWidget(self.proxy_test)
        self.proxy_save = PushButton("Test and save profile…")
        self.proxy_save.setEnabled(False)
        self.proxy_save.clicked.connect(lambda: self._submit_proxy_profile("save"))
        profile_actions.addWidget(self.proxy_save)
        profile_actions.addStretch(1)
        layout.addLayout(profile_actions)
        self.proxy_note = CaptionLabel()
        self.proxy_note.setWordWrap(True)
        layout.addWidget(self.proxy_note)
        self._proxy_status = None
        boundary = CaptionLabel(
             "Unapproved proxy endpoints are not exposed. Legacy automated challenge providers and unreviewed extensions "
            "are not exposed. The raw engine web service, developer "
            "cookie dump and unverified update commands are not exposed. Use Daedalus for remote control "
            "and the reviewed release workflow for updates.")
        boundary.setWordWrap(True)
        self.setToolTip(boundary.text())
        layout.addStretch(1)
        self.theme_combo.currentIndexChanged.connect(self._changed)
        self.only_220k.stateChanged.connect(self._changed)
        self.group_island.stateChanged.connect(self._changed)
        self.select_section(0)

    def select_section(self, index: int) -> None:
        self.section_stack.setCurrentIndex(index)
        self.sections.setCurrentItem(self.section_keys[index])
        self.admin_bar.setVisible(index != 0)

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
        if hasattr(self, "challenge_status"):
            self._reset_challenge_policy()
        if hasattr(self, "world_picker"):
            self._reset_world_reports()
        if hasattr(self, "proxy_picker"):
            self._reset_proxy_profiles()

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

    def _reset_proxy_profiles(self):
        self._proxy_status = None
        self.proxy_picker.clear()
        self.proxy_read.setEnabled(isinstance(self.admin_account.currentData(), str))
        self.proxy_test.setEnabled(False)
        self.proxy_save.setEnabled(False)
        self.proxy_note.clear()

    def _proxy_controls(self, *_args):
        status = getattr(self, "_proxy_status", None)
        selected = self.proxy_picker.currentData()
        allowed = bool(status and not status["busy"] and self.proxy_picker.currentIndex() >= 0
                       and selected != "unselected")
        self.proxy_test.setEnabled(allowed)
        self.proxy_save.setEnabled(allowed and (selected != status["current"] or
                                                (selected is None and status["enabled"])))

    def _read_proxy_profiles(self):
        account = self.admin_account.currentData()
        if isinstance(account, str):
            self._reset_proxy_profiles()
            self.proxy_note.setText("Reading approved profiles…")
            self.proxy_profiles_requested.emit(account, None)

    def _submit_proxy_profile(self, action):
        account = self.admin_account.currentData()
        if not isinstance(account, str) or not self._proxy_status or not (
                self.proxy_test.isEnabled() if action == "test" else self.proxy_save.isEnabled()):
            return
        choice = self.proxy_picker.currentData()
        label = self.proxy_picker.currentText()
        if QMessageBox.question(self, "Approved network profile",
                f"{'Test' if action == 'test' else 'Test and save'} {label} for the selected account? "
                "The check contacts a fixed public HTTPS endpoint without game credentials. "
                "Saving changes future network requests, without forcing a reconnect.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        draft = {"action": action, "profile": choice, "revision": self._proxy_status["revision"], "confirmed": True}
        self._reset_proxy_profiles()
        self.proxy_note.setText("Checking network profile…")
        self.proxy_profiles_requested.emit(account, draft)

    def set_proxy_profiles(self, value):
        from daedalus.proxy_profiles import validate_proxy_status

        account = self.admin_account.currentData()
        if not isinstance(value, dict) or value.get("account_id") != account:
            return
        self._reset_proxy_profiles()
        try:
            status = validate_proxy_status(value, account)
        except ValueError:
            self.set_proxy_unavailable(account)
            return
        self._proxy_status = status
        with QSignalBlocker(self.proxy_picker):
            self.proxy_picker.addItem("Choose approved profile", userData="unselected")
            if status["allow_direct"]:
                self.proxy_picker.addItem("Direct connection (host approved)", userData=None)
            for row in status["profiles"]:
                self.proxy_picker.addItem(f"{row['label']} · {row['protocol']}", userData=row["id"])
            for i in range(1, self.proxy_picker.count()):
                if self.proxy_picker.itemData(i) == status["current"]:
                    self.proxy_picker.setCurrentIndex(i)
                    break
        current = next((r["label"] for r in status["profiles"] if r["id"] == status["current"]), None)
        description = current or ("Legacy proxy (manage locally)" if status["enabled"] else "Direct connection")
        outcome = {"observed": "", "tested": "HTTPS test passed; settings unchanged. ",
                   "saved": "Profile saved after HTTPS test. "}[status["result"]]
        self.proxy_note.setText(outcome + "Current: " + description +
                               (". Stop active tasks before changing profiles." if status["busy"] else
                                ". Game-side connectivity is not tested."))
        self._proxy_controls()

    def set_proxy_unavailable(self, account):
        if self.admin_account.currentData() == account:
            self._reset_proxy_profiles()
            self.proxy_note.setText("Network profile unavailable or outcome uncertain. Refresh before retrying.")

    def _reset_world_reports(self):
        self._world_metadata = []
        self.world_picker.clear()
        self.world_export.setEnabled(False)
        self.world_refresh.setEnabled(isinstance(self.admin_account.currentData(), str))
        self.world_note.clear()

    def _world_controls(self, *_args):
        self.world_export.setEnabled(isinstance(self.world_picker.currentData(), str))

    def _request_world_reports(self):
        account = self.admin_account.currentData()
        if isinstance(account, str):
            self._reset_world_reports()
            self.world_note.setText("Reading completed aggregate reports…")
            self.world_reports_requested.emit(account, None)

    def _request_world_export(self):
        account, report_id = self.admin_account.currentData(), self.world_picker.currentData()
        if isinstance(account, str) and isinstance(report_id, str):
            self.world_export.setEnabled(False)
            self.world_note.setText("Validating every report page…")
            self.world_reports_requested.emit(account, report_id)

    def set_world_reports(self, value):
        from datetime import datetime

        from daedalus.world_reports import validate_world_reports

        account = self.admin_account.currentData()
        if not isinstance(value, dict) or value.get("account_id") != account:
            return
        self._reset_world_reports()
        try:
            result = validate_world_reports(value, account)
        except ValueError:
            self.set_world_report_unavailable(account)
            return
        self._world_metadata = result["reports"]
        with QSignalBlocker(self.world_picker):
            for row in self._world_metadata:
                date = datetime.fromtimestamp(row["completed_at"], UTC).strftime("%Y-%m-%d %H:%M UTC")
                kind = "Shallow" if row["shallow"] else "Detailed aggregate"
                extent = "partial" if row["partial"] else "whole map"
                self.world_picker.addItem(f"{date} · {kind} · {extent} · {row['island_count']} islands",
                                          userData=row["report_id"])
        self._world_controls()
        self.world_note.setText(f"{len(self._world_metadata)} completed reports. Only complete validated reports can be exported.")

    def set_world_export(self, value):
        from pathlib import Path

        from daedalus.world_reports import report_csv

        account = self.admin_account.currentData()
        if (not isinstance(value, dict) or value.get("account_id") != account
                or value.get("report_id") != self.world_picker.currentData()):
            return
        self._world_controls()
        filename, _ = QFileDialog.getSaveFileName(self, "Export aggregate map report",
                                                   "Daedalus-world-map.csv", "CSV files (*.csv)")
        if not filename:
            self.world_note.setText("Export cancelled.")
            return
        try:
            with Path(filename).open("w", encoding="utf-8", newline="") as handle:
                handle.write(report_csv(value))
        except OSError:
            self.world_note.setText("Could not save the selected report.")
            return
        self.world_note.setText(f"Exported {len(value['rows'])} island rows.")

    def set_world_report_unavailable(self, account):
        if self.admin_account.currentData() == account:
            self._reset_world_reports()
            self.world_note.setText("Aggregate map reports unavailable. Refresh before retrying.")

    def _reset_challenge_policy(self):
        self._challenge_policy = None
        self.challenge_read.setEnabled(isinstance(self.admin_account.currentData(), str))
        self.challenge_mode.setEnabled(False)
        self.challenge_save.setEnabled(False)
        self.challenge_status.clear()

    def _request_challenge_policy(self):
        account = self.admin_account.currentData()
        if isinstance(account, str):
            self._reset_challenge_policy()
            self.challenge_status.setText("Reading account challenge policy…")
            self.challenge_policy_requested.emit(account, None)

    def _challenge_controls(self, *_args):
        mode = "stop" if self.challenge_mode.currentIndex() == 0 else "notify_and_stop"
        current = getattr(self, "_challenge_policy", None)
        self.challenge_save.setEnabled(bool(current and mode != current["mode"] and
                                            (mode == "stop" or current["notification_ready"])))

    def _save_challenge_policy(self):
        account = self.admin_account.currentData()
        if not isinstance(account, str) or not self.challenge_save.isEnabled() or not self._challenge_policy:
            return
        mode = "stop" if self.challenge_mode.currentIndex() == 0 else "notify_and_stop"
        if QMessageBox.question(self, "Human challenge policy",
                "Save the selected account's human-attention stop policy?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        draft = {"mode": mode, "expected_mode": self._challenge_policy["mode"], "confirmed": True}
        self._reset_challenge_policy()
        self.challenge_status.setText("Updating account challenge policy…")
        self.challenge_policy_requested.emit(account, draft)

    def set_challenge_policy(self, value):
        from daedalus.challenge_policy import validate_challenge_policy

        account = self.admin_account.currentData()
        if not isinstance(value, dict) or value.get("account_id") != account:
            return
        try:
            self._challenge_policy = validate_challenge_policy(value, account)
        except ValueError:
            self.set_challenge_unavailable(account)
            return
        self.challenge_mode.setCurrentIndex(0 if value["mode"] == "stop" else 1)
        self.challenge_mode.setEnabled(True)
        self.challenge_status.setText("Notification destination configured." if value["notification_ready"]
                                      else "Configure a supported notification destination before choosing notify and stop.")
        self._challenge_controls()

    def set_challenge_unavailable(self, account):
        if self.admin_account.currentData() == account:
            self._reset_challenge_policy()
            self.challenge_status.setText("Challenge policy unavailable or changed. Refresh before retrying.")

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
