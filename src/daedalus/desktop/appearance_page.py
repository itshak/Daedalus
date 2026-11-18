"""Offline, nonsecret presentation controls for the native Fluent client."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, CheckBox, ComboBox, SubtitleLabel

from daedalus.gui_preferences import GuiPreferences

_THEME_LABELS = ("System", "Light", "Dark")
_THEME_VALUES = ("auto", "light", "dark")


class AppearancePage(QWidget):
    """Safe UI-only settings: no browser, password or game-session controls."""

    preferences_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appearance_page")
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel("Appearance and reports"))
        layout.addWidget(CaptionLabel(
            "Settings apply only to this Mac client, not the connected game worker. "
            "Account report selection is stored privately for each backend."
        ))
        layout.addWidget(BodyLabel("Theme"))
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(_THEME_LABELS)
        layout.addWidget(self.theme_combo)
        self.only_220k = CheckBox("Filter to 220K+ unsecured resources by default")
        layout.addWidget(self.only_220k)
        self.group_island = CheckBox("Group warehouse results by island by default")
        layout.addWidget(self.group_island)
        layout.addWidget(CaptionLabel(
            "Browser login, credentials and recovery settings stay on the authoritative "
            "backend, never in local GUI preferences."
        ))
        layout.addStretch(1)
        self.theme_combo.currentIndexChanged.connect(self._changed)
        self.only_220k.stateChanged.connect(self._changed)
        self.group_island.stateChanged.connect(self._changed)

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
