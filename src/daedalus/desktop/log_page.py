"""Bounded, nonsecret desktop activity and opt-in technical diagnostics.

This is local client activity, never a substitute for authoritative server
request history. A compact timeline is the primary view; raw logs stay behind
Advanced diagnostics.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    PushButton,
)

from daedalus.account_display import account_player_names
from daedalus.desktop.design_system import PageHeading

_EVENTS = {
    "military inventory refreshed": ("Military inventory refreshed", "Current troops and fleets were received from the authenticated account."),
    "military movements refreshed": ("Military movements refreshed", "Current movements were received from the authenticated account."),
    "backend military_overview request failed": ("Military inventory unavailable", "The backend could not verify current troops and fleets. Check account connection and retry the military refresh."),
    "backend military_movements request failed": ("Military movements unavailable", "The backend could not verify current movements. Check account connection and retry."),
    "connected to daedalus api": ("Connection established", "Your backend is available."),
    "accounts refreshed": ("Accounts refreshed", "Account status was updated."),
    "warehouse snapshot report updated": (
        "Warehouse report refreshed", "A new read-only warehouse snapshot is available."
    ),
    "multi-account warehouse report updated": (
        "Combined warehouses refreshed", "Account warehouse results were combined."
    ),
    "backend native_login_complete request failed": (
        "Server rejected game login",
        "The encrypted session was not accepted. Visible Chrome recovery is attempted once with a new ticket.",
    ),
    "backend native_login_start request failed": (
        "Server could not prepare game login",
        "The selected account or worker is not ready for a new login ticket. Review account ownership.",
    ),
    "backend native_login_cancel request failed": (
        "Game login cancellation was rejected",
        "The one-use handoff may have expired. Review the account before another attempt.",
    ),
    "server declined headless cookie handoff": (
        "Visible browser recovery required",
        "The saved headless session failed server verification. A new visible Chrome attempt is queued.",
    ),
    "isolated gameforge sign-in failed": (
        "Gameforge sign-in unsuccessful",
        "Chrome or Gameforge login could not finish. Review the sign-in stages and retry.",
    ),
    "isolated selenium login exceeded": (
        "Gameforge sign-in timed out",
        "Chrome was terminated after its watchdog deadline; retry or inspect Chrome installation.",
    ),
    "saved gameforge login unavailable": (
        "Saved credentials unavailable",
        "Enter the account's Gameforge credentials in the secure prompt.",
    ),
    "backend task_start request failed": (
        "Action needs attention", "Review Activity before retrying the automation."
    ),
    "managed tasks refreshed": ("Automations refreshed", "Running tasks and request history were checked."),
    "multi-account read-only managed task statuses refreshed": (
        "All-account status refreshed", "Read-only task status was checked across accounts."
    ),
    "task operation acknowledged": (
        "Automation response received", "Review the task status for authoritative confirmation."
    ),
}


# Only reviewed, nonsecret stages emitted by the isolated browser helper are
# eligible for display. Do not display arbitrary subprocess diagnostics.
_LOGIN_STAGES = {
    "sign_in_requested": "Sign-in requested",
    "backend_handoff_requested": "Preparing secure server handoff",
    "backend_handoff_ready": "Secure server handoff prepared",
    "helper_starting": "Starting isolated login helper",
    "helper_running": "Isolated login helper started",
    "resolving_saved_login": "Checking saved Gameforge credentials",
    "keychain_unavailable": "Mac Keychain unavailable",
    "launching_chrome": "Launching Chrome",
    "starting_headless_browser": "Starting background Chrome",
    "checking_saved_session": "Checking saved world session",
    "saved_session_expired": "Saved world session unavailable; checking saved credentials",
    "saved_session_restored": "Saved world session restored",
    "headless_login": "Trying background Gameforge login",
    "opening_lobby": "Opening Gameforge lobby",
    "lobby_loaded": "Gameforge lobby loaded",
    "waiting_for_login_form": "Waiting for the login form",
    "login_submitted": "Gameforge login form submitted",
    "sign_in_tab_selected": "Gameforge sign-in tab selected",
    "sign_in_tab_not_found": "Gameforge sign-in form unavailable; visible help required",
    "lobby_session_active": "Existing lobby session found",
    "waiting_for_world": "Waiting for the selected game world",
    "play_clicked": "Opening selected game world",
    "world_ready": "Selected game world opened",
    "world_cookie_ready": "World session obtained; awaiting server verification",
    "headless_login_failed": "Background login failed",
    "opening_visible_captcha": "CAPTCHA detected; opening visible Chrome",
    "opening_visible_recovery": "Opening visible Chrome after login failure",
    "opening_visible_browser": "Starting visible Chrome",
    "visible_captcha_login": "Continuing in visible Chrome",
    "captcha_required": "CAPTCHA requires manual completion",
    "captcha_resolved": "CAPTCHA completed",
    "manual_login_required": "Manual sign-in needed in visible Chrome",
    "login_form_timeout": "Gameforge login form timed out",
    "browser_navigation_error": "Chrome could not navigate the login page",
    "visible_login_failed": "Visible login recovery failed",
    "helper_protocol_error": "Login helper returned invalid data",
    "helper_exited_early": "Login helper stopped unexpectedly",
    "helper_start_failed": "Isolated login helper could not start",
    "keychain_save_failed": "Secure login backup could not be saved",
    "credentials_required": "Saved login unavailable; credentials required",
    "handoff_verifying": "Waiting for independent server verification",
    "handoff_verified": "Game session verified; worker reconnected",
    "handoff_saved": "Game session verified and saved; worker not connected",
    "server_rejected_headless": "Server rejected headless session; visible retry queued",
    "handoff_failed": "Game session could not be verified",
    "sign_in_cancelled": "Sign-in cancelled",
    "sign_in_finished": "Sign-in attempt finished",
}


def _login_stage_severity(stage: str) -> str:
    if stage in {
        "headless_login_failed", "helper_exited_early", "helper_protocol_error",
        "keychain_unavailable", "keychain_save_failed", "login_form_timeout",
        "browser_navigation_error", "manual_login_required", "credentials_required",
        "server_rejected_headless",
    }:
        return "Warning"
    if stage in {"visible_login_failed", "helper_start_failed", "handoff_failed"}:
        return "Error"
    return "Information"


class LogPage(QWidget):
    server_activity_requested = Signal(str, object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("log_page")
        self._events: list[tuple[str, str, str, str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(9)
        root.addWidget(PageHeading(
            "Activity", "Recent events on this Mac, across all configured accounts.", self
        ))
        note = CaptionLabel(
            "This is a local, bounded activity timeline, not a complete server audit. "
            "For task request IDs and uncertain launches, use Automations → History."
        )
        note.setWordWrap(True)
        self.timeline_explanation = note
        self.setToolTip(note.text())
        filters = QHBoxLayout()
        filters.addWidget(BodyLabel("Show"))
        self.severity_combo = ComboBox()
        self.severity_combo.addItems(["All events", "Information", "Warnings", "Errors"])
        self.severity_combo.currentIndexChanged.connect(self._render_events)
        filters.addWidget(self.severity_combo)
        filters.addWidget(BodyLabel("Type"))
        self.type_combo = ComboBox()
        self.type_combo.addItems([
            "All types", "Connection", "Accounts", "Warehouses", "Automations", "Other"
        ])
        self.type_combo.currentIndexChanged.connect(self._render_events)
        filters.addWidget(self.type_combo)
        filters.addStretch()
        self.diagnostics_button = PushButton("Diagnostics ▾")
        self.diagnostics_button.clicked.connect(self._toggle_diagnostics)
        filters.addWidget(self.diagnostics_button)
        root.addLayout(filters)
        self.timeline = QPlainTextEdit(self)
        self.timeline.setObjectName("activity_timeline")
        self.timeline.setReadOnly(True)
        self.timeline.setAccessibleName("Recent local Daedalus activity")
        self.timeline.setMaximumBlockCount(250)
        self.timeline.setPlainText("No local activity yet. Connect to see status updates.")
        root.addWidget(self.timeline, 1)
        server_controls = QHBoxLayout()
        server_controls.addWidget(BodyLabel("Server receipts"))
        self.server_account = ComboBox()
        self.server_account.setAccessibleName("Server activity account")
        self.server_status = ComboBox()
        self.server_status.addItems(["All statuses", "Started", "Rejected", "Unconfirmed", "Dispatching", "Operator reconciled"])
        self.server_status.setAccessibleName("Server receipt status")
        self.server_refresh = PushButton("Refresh")
        self.server_older = PushButton("Older")
        self.server_copy = PushButton("Copy CSV")
        for widget in (self.server_account, self.server_status, self.server_refresh, self.server_older, self.server_copy):
            server_controls.addWidget(widget)
        root.addLayout(server_controls)
        self.server_note = CaptionLabel("Server request history only; raw engine logs remain host-local.")
        self.server_note.setWordWrap(True)
        root.addWidget(self.server_note)
        self.server_timeline = QPlainTextEdit()
        self.server_timeline.setReadOnly(True)
        self.server_timeline.setMaximumBlockCount(160)
        self.server_timeline.setAccessibleName("Server task receipt history")
        root.addWidget(self.server_timeline, 1)
        self._server_ids = []
        self._server_rows = []
        self._server_before = None
        self._server_requested = None
        self.server_account.currentIndexChanged.connect(self._server_reset)
        self.server_status.currentIndexChanged.connect(self._server_reset)
        self.server_refresh.clicked.connect(self._server_reset)
        self.server_older.clicked.connect(self._server_load_older)
        self.server_copy.clicked.connect(self._server_export)
        self._server_controls()
        self.log_view = QPlainTextEdit(self)
        self.log_view.setObjectName("advanced_diagnostics")
        self.log_view.setReadOnly(True)
        self.log_view.setAccessibleName("Advanced bounded technical diagnostics")
        self.log_view.setMaximumBlockCount(2000)
        font = self.log_view.font()
        font.setFamily("Menlo")
        font.setPointSize(11)
        self.log_view.setFont(font)
        self.log_view.hide()
        root.addWidget(self.log_view, 1)

    def set_accounts(self, accounts):
        previous = self.server_account.currentData()
        rows = [row for row in accounts if isinstance(row, dict) and isinstance(row.get("id"), str)]
        names = account_player_names(rows)
        with QSignalBlocker(self.server_account):
            self.server_account.clear()
            for row in rows:
                self.server_account.addItem(names[row["id"]], userData=row["id"])
            self.server_account.setCurrentIndex(next((i for i,r in enumerate(rows) if r["id"] == previous), 0 if rows else -1))
        self._server_ids = [row["id"] for row in rows]
        self._server_clear()
        self._server_controls()

    def _server_filter(self):
        return ("all", "started", "rejected", "unconfirmed", "dispatching",
                "operator_reconciled")[max(0, self.server_status.currentIndex())]

    def _server_controls(self):
        self.server_refresh.setEnabled(bool(self._server_ids))
        self.server_older.setEnabled(self._server_before is not None and self._server_requested is None)
        self.server_copy.setEnabled(bool(self._server_rows))

    def _server_clear(self):
        self._server_rows = []
        self._server_before = None
        self._server_requested = None
        self.server_timeline.setPlainText("Select an account and refresh its server receipts.")

    def _server_reset(self, *_args):
        self._server_clear()
        self._server_load(None)

    def _server_load_older(self):
        if self._server_before is not None:
            self._server_load(self._server_before)

    def _server_load(self, before):
        account = self.server_account.currentData()
        if not account:
            self._server_controls()
            return
        status = self._server_filter()
        self._server_requested = (account, before, status)
        self.server_note.setText("Loading server receipts…")
        self._server_controls()
        self.server_activity_requested.emit(account, before, status)

    @staticmethod
    def _server_time(value):
        if value is None:
            return "Unknown"
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OverflowError, OSError):
            return "Unknown"

    def set_server_activity(self, result, before, status):
        key = (result.get("account_id"), before, status)
        if key != self._server_requested or key[0] != self.server_account.currentData() or status != self._server_filter():
            return
        self._server_requested = None
        self._server_rows = result["events"]
        self._server_before = result["next_before"]
        self.server_timeline.setPlainText("\n".join(
            f"{self._server_time(row['updated_at'])}  ·  {row['task']}  ·  {row['status'].replace('_', ' ')}\n{row['request_id']}"
            for row in self._server_rows) or "No matching server receipts.")
        self.server_note.setText("Showing a page of server receipts. Started is a dispatch receipt, not proof of completion.")
        self._server_controls()

    def set_server_activity_unavailable(self, account, before, status):
        if (account, before, status) == self._server_requested:
            self._server_requested = None
            self.server_note.setText("Server receipt history unavailable. Refresh to retry.")
            self._server_controls()

    def _server_export(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["request_id", "task", "status", "created_at", "updated_at"])
        for row in self._server_rows:
            writer.writerow([row["request_id"], row["task"], row["status"],
                             row["created_at"], row["updated_at"]])
        QApplication.clipboard().setText(output.getvalue())
        self.server_note.setText("Current page copied as CSV.")

    def _toggle_diagnostics(self) -> None:
        show = not self.log_view.isVisible()
        self.log_view.setVisible(show)
        self.diagnostics_button.setText(
            "Hide advanced diagnostics" if show else "Show advanced diagnostics"
        )

    def add_login_stage(self, stage: str) -> None:
        """Append one account sign-in step without storing secret-bearing input."""
        title = _LOGIN_STAGES.get(stage)
        if title is None:
            return
        severity = _login_stage_severity(stage)
        self._events.append((
            datetime.now().strftime("%H:%M:%S"), severity, "Accounts", title,
            {
                "handoff_saved": "Server verified this cookie and stored it securely. No game worker was attached; the account may still be marked Not connected.",
                "handoff_verified": "The authoritative server verified the session and reconnected its existing worker.",
                "handoff_failed": "Session verification or handoff failed; this is not a connected account.",
                "server_rejected_headless": "The consumed login ticket cannot be reused. A new ticket and visible Chrome recovery are required.",
                "saved_session_restored": "A local world cookie was restored. This is not yet an authenticated server worker.",
                "sign_in_finished": "The current sign-in batch ended. Check the Accounts Worker column and the result message for actual connectivity.",
            }.get(stage, "Local browser step; server verification and worker attachment are separate."),
        ))
        if len(self._events) > 250:
            del self._events[:-250]
        self._render_events()

    def add_event(self, level: str, message: str) -> None:
        """Accept only reviewed generic client events, never arbitrary payloads."""
        safe_message = message.casefold()
        known = next((key for key in _EVENTS if key in safe_message), None)
        if known:
            title, detail = _EVENTS[known]
        elif level in {"WARNING", "ERROR", "CRITICAL"}:
            title, detail = (
                ("Desktop warning", "Open Advanced diagnostics for the reviewed, nonsecret warning category.")
                if level == "WARNING" else
                ("Request failed", "Check the connection or retry a read-only refresh.")
            )
        else:
            return
        severity = "Error" if level in {"ERROR", "CRITICAL"} else (
            "Warning" if level == "WARNING" else "Information"
        )
        category = (
            "Warehouses" if "warehouse" in known.lower() else
            "Automations" if "task" in known.lower() or "automation" in known.lower()
            else "Connection" if "connect" in known.lower()
            else "Accounts" if "account" in known.lower()
            else "Other"
        ) if known else "Other"
        self._events.append((datetime.now().strftime("%H:%M"), severity, category, title, detail))
        if len(self._events) > 250:
            del self._events[:-250]
        self._render_events()

    def _render_events(self, *_args: object) -> None:
        selection = self.severity_combo.currentText()
        category_filter = self.type_combo.currentText()
        entries = [
            f"{when}  ·  {severity}  ·  {title}\n{detail}"
            for when, severity, category, title, detail in reversed(self._events)
            if (selection == "All events" or selection == severity + "s"
                or selection == severity)
            and (category_filter == "All types" or category_filter == category)
        ]
        self.timeline.setPlainText(
            "\n\n".join(entries) if entries
            else "No local activity matches this filter."
        )
