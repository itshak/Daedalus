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
        root.addWidget(SubtitleLabel("Log"))
        root.addWidget(CaptionLabel("Local desktop connection and diagnostic messages."))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        font = self.log_view.font()
        font.setFamily("Menlo")
        font.setPointSize(11)
        self.log_view.setFont(font)
        root.addWidget(self.log_view, 1)
