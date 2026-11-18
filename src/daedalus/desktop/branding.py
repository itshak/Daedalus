"""Brand assets for both source and installed/frozen desktop applications."""
from __future__ import annotations

from importlib.resources import files


def application_icon():
    """Use the package-shipped opaque app icon, not the current working dir."""
    from PySide6.QtGui import QIcon

    icon = files("daedalus.desktop").joinpath("resources/app-icon-256.png")
    return QIcon(str(icon))
