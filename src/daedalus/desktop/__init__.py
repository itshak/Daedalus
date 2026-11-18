"""Native desktop UI, adapted from the user's original PySide6/Fluent GUI.

Importing the package does not import Qt or initiate backend connections.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
        from qfluentwidgets import Theme, setTheme
    except ImportError:
        print('Install desktop dependencies with: pip install "daedalus[desktop]"', file=sys.stderr)
        return 2

    from daedalus.desktop.app import MainWindow
    from daedalus.desktop.branding import application_icon
    from daedalus.desktop.theme import init_app_theme

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Daedalus")
    app.setWindowIcon(application_icon())
    from daedalus.gui_preferences import (
        GuiPreferenceError,
        GuiPreferences,
        load_gui_preferences,
    )

    try:
        saved = load_gui_preferences()
    except GuiPreferenceError:
        saved = GuiPreferences()
    setTheme({"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}[saved.theme])
    init_app_theme()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
