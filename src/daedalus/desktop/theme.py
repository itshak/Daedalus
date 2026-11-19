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
    window = QColor(28, 28, 30) if dark else QColor(245, 245, 247)
    base = QColor(39, 39, 41) if dark else QColor(255, 255, 255)
    text = QColor(242, 242, 247) if dark else QColor(29, 29, 31)
    accent = QColor(10, 132, 255) if dark else QColor(0, 122, 255)

    palette = QPalette()
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(
        QPalette.AlternateBase, QColor(44, 44, 46) if dark else QColor(248, 248, 250)
    )
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
