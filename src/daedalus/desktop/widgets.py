"""Reviewed styling helpers ported from the existing Mac GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from qfluentwidgets import CardWidget, TableWidget
from qfluentwidgets.common.style_sheet import isDarkTheme


class ScrollTableWidget(TableWidget):
    """Retain the legacy GUI's mouse-wheel scrolling correction."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        delegate = getattr(self, "scrollDelagate", None)
        if delegate is None:
            return
        self._fix_wheel(delegate.verticalSmoothScroll, self.verticalScrollBar)
        self._fix_wheel(delegate.horizonSmoothScroll, self.horizontalScrollBar)

    @staticmethod
    def _fix_wheel(scroll: object, bar_getter: object) -> None:
        for engine in (scroll.fixedStepScrollEngine, scroll.adaptiveScrollEngine):
            def send(total_delta: float) -> None:
                bar = bar_getter()
                bar.setValue(int(bar.value() - total_delta))

            engine.sendScrollEventToScrollBar = send


class OpaqueCardWidget(CardWidget):
    """Preserve the native light-theme opaque white cards."""

    def _normalBackgroundColor(self) -> QColor:
        if isDarkTheme():
            return super()._normalBackgroundColor()
        return QColor(255, 255, 255)

    def _hoverBackgroundColor(self) -> QColor:
        if isDarkTheme():
            return super()._hoverBackgroundColor()
        return QColor(248, 248, 248)

    def _pressedBackgroundColor(self) -> QColor:
        if isDarkTheme():
            return super()._pressedBackgroundColor()
        return QColor(240, 240, 240)
