"""Offline, nonsecret presentation controls for the native Fluent client."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, CheckBox, ComboBox, PushButton, SubtitleLabel

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
        layout.addStretch(1)
        self.theme_combo.currentIndexChanged.connect(self._changed)
        self.only_220k.stateChanged.connect(self._changed)
        self.group_island.stateChanged.connect(self._changed)

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
