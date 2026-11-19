"""Bounded, nonsecret desktop activity and opt-in technical diagnostics.

This is local client activity, never a substitute for authoritative server
request history. A compact timeline is the primary view; raw logs stay behind
Advanced diagnostics.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    PushButton,
)

from daedalus.desktop.design_system import PageHeading

_EVENTS = {
    "connected to daedalus api": ("Connection established", "Your backend is available."),
    "accounts refreshed": ("Accounts refreshed", "Account status was updated."),
    "warehouse snapshot report updated": (
        "Warehouse report refreshed", "A new read-only warehouse snapshot is available."
    ),
    "multi-account warehouse report updated": (
        "Combined warehouses refreshed", "Account warehouse results were combined."
    ),
    "managed tasks refreshed": ("Automations refreshed", "Running tasks and request history were checked."),
    "multi-account read-only managed task statuses refreshed": (
        "All-account status refreshed", "Read-only task status was checked across accounts."
    ),
    "task operation acknowledged": (
        "Automation response received", "Review the task status for authoritative confirmation."
    ),
}


class LogPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("log_page")
        self._events: list[tuple[str, str, str, str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeading(
            "Activity", "Recent events on this Mac, across all configured accounts.", self
        ))
        note = CaptionLabel(
            "This is a local, bounded activity timeline, not a complete server audit. "
            "For task request IDs and uncertain launches, use Automations → History."
        )
        note.setWordWrap(True)
        root.addWidget(note)
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
        self.diagnostics_button = PushButton("Show advanced diagnostics")
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

    def _toggle_diagnostics(self) -> None:
        show = not self.log_view.isVisible()
        self.log_view.setVisible(show)
        self.diagnostics_button.setText(
            "Hide advanced diagnostics" if show else "Show advanced diagnostics"
        )

    def add_event(self, level: str, message: str) -> None:
        """Accept only reviewed generic client events, never arbitrary payloads."""
        safe_message = message.casefold()
        known = next((key for key in _EVENTS if key in safe_message), None)
        if known:
            title, detail = _EVENTS[known]
        elif level in {"WARNING", "ERROR", "CRITICAL"}:
            title, detail = (
                ("Action needs attention", "Open the relevant screen to review the current state.")
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
