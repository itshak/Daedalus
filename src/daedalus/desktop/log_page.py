"""Adapted from the legacy GUI's bounded, read-only diagnostics log."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, SubtitleLabel


class LogPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("log_page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(SubtitleLabel("Activity"))
        description = CaptionLabel(
            "Local Daedalus desktop events across all accounts. This is not a "
            "complete server audit history. Technical details never contain API "
            "tokens, game cookies or passwords."
        )
        description.setWordWrap(True)
        root.addWidget(description)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        font = self.log_view.font()
        font.setFamily("Menlo")
        font.setPointSize(11)
        self.log_view.setFont(font)
        root.addWidget(self.log_view, 1)
