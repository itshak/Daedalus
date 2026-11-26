"""Isolated runtime theme and palette regression (synthetic desktop only)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from daedalus.desktop.app import MainWindow


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def _dispose(window, app):
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()

def test_native_scroll_surfaces_follow_runtime_theme(qt_app, monkeypatch):
    from PySide6.QtGui import QPalette
    from qfluentwidgets import Theme, setTheme

    import daedalus.desktop.app as module
    from daedalus.desktop.theme import apply_app_palette
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(MainWindow, "_auto_reconnect_securely", lambda _: None)
    setTheme(Theme.LIGHT)
    apply_app_palette()
    window = MainWindow()
    try:
        for theme, expected in ((Theme.DARK, "#1c1c1e"), (Theme.LIGHT, "#f5f5f7")):
            setTheme(theme)
            apply_app_palette()
            qt_app.processEvents()
            for scroll in (window.home_page.content_scroll, window.tasks_page.discovery_scroll, window.tasks_page.parameter_scroll):
                for surface in (scroll, scroll.viewport(), scroll.widget()):
                    assert surface.palette().color(QPalette.Window).name() == expected
    finally:
        setTheme(Theme.LIGHT)
        apply_app_palette()
        _dispose(window, qt_app)
