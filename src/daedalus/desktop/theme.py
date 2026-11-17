"""Adapted from the legacy Mac GUI's Fluent/Qt palette synchronization."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from qfluentwidgets import isDarkTheme, qconfig


def apply_app_palette() -> None:
    app = QApplication.instance()
    if app is None:
        return
    if app.style().objectName() != "fusion":
        app.setStyle("Fusion")

    dark = isDarkTheme()
    window = QColor(32, 32, 32) if dark else QColor(240, 244, 249)
    base = QColor(24, 24, 24) if dark else QColor(255, 255, 255)
    text = QColor(255, 255, 255) if dark else QColor(0, 0, 0)
    accent = QColor(76, 194, 255) if dark else QColor(0, 120, 212)

    palette = QPalette()
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, base)
    palette.setColor(QPalette.ToolTipBase, window)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, accent)
    palette.setColor(QPalette.Highlight, accent)
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)


def init_app_theme() -> None:
    apply_app_palette()
    qconfig.themeChanged.connect(apply_app_palette)
