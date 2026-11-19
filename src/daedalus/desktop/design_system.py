"""Reviewed presentation primitives for Daedalus's native Fluent UI.

This module is intentionally UI-only: no credentials, game operations or API calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    SubtitleLabel,
)
from qfluentwidgets import (
    FluentIcon as FIF,
)


@dataclass(frozen=True)
class Metrics:
    """Device-independent spacing values; let Qt scale font metrics for macOS."""

    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    page_max_width: int = 1120


METRICS = Metrics()

# Explicit, unique Fluent icons prevent duplicated Settings/Connection and
# Wine/Automations pictograms. Qt renders the correct theme-specific vector.
NAV_ICONS = {
    "overview": FIF.HOME,
    "accounts": FIF.PEOPLE,
    "warehouses": FIF.SAVE,
    "automations": FIF.ROBOT,
    "activity": FIF.HISTORY,
    "connection": FIF.LINK,
    "settings": FIF.SETTING,
}
FEATURE_ICONS = {
    "wine": FIF.CAFE,
    "construction": FIF.EDIT,
    "alerts": FIF.INFO,
    "resources": FIF.MARKET,
    "catalog": FIF.APPLICATION,
}
assert len({icon.value for icon in NAV_ICONS.values()}) == len(NAV_ICONS)


def _wrap(label: CaptionLabel | BodyLabel) -> None:
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)


class PageHeading(QWidget):
    """Consistent app-title and page-description hierarchy."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, METRICS.xs)
        layout.setSpacing(0)
        self.title = SubtitleLabel(title)
        self.title.setAccessibleName(title)
        if subtitle:
            self.title.setToolTip(subtitle)
            self.title.setAccessibleDescription(subtitle)
        layout.addWidget(self.title)
        # Description is available on hover/assistive tech instead of
        # occupying every page header. Retain this member for existing callers.
        self.subtitle = CaptionLabel(subtitle)
        _wrap(self.subtitle)
        self.subtitle.hide()


class SectionCard(CardWidget):
    """A readable native-looking Fluent card with a short header."""

    def __init__(self, title: str, description: str = "", parent=None) -> None:
        super().__init__(parent)
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(METRICS.lg, METRICS.lg, METRICS.lg, METRICS.lg)
        self.content_layout.setSpacing(METRICS.md)
        self.heading = SubtitleLabel(title)
        self.content_layout.addWidget(self.heading)
        if description:
            info = CaptionLabel(description)
            _wrap(info)
            self.content_layout.addWidget(info)


class StatusPanel(CardWidget):
    """State carries words and accessible meaning, never color alone."""

    def __init__(self, title: str = "", detail: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(METRICS.lg, METRICS.md, METRICS.lg, METRICS.md)
        stack = QVBoxLayout()
        stack.setSpacing(METRICS.xs)
        self.heading = SubtitleLabel(title)
        self.detail = CaptionLabel(detail)
        _wrap(self.detail)
        stack.addWidget(self.heading)
        stack.addWidget(self.detail)
        layout.addLayout(stack, 1)
        self.setAccessibleName(title)

    def set_status(self, title: str, detail: str) -> None:
        self.heading.setText(title)
        self.detail.setText(detail)
        self.setAccessibleName(f"{title}. {detail}")


def style_form_input(widget: QWidget, name: str, help_text: str = "") -> QWidget:
    widget.setAccessibleName(name)
    if help_text:
        widget.setToolTip(help_text)
        widget.setAccessibleDescription(help_text)
    return widget
