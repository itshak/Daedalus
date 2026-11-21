"""Bounded, private diagnostic logs for freezes that cannot be inspected in UI."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_desktop_diagnostics() -> Path | None:
    """Log only sanitized Daedalus diagnostics; never log cookies or passwords."""
    if sys.platform == "darwin":
        folder = Path.home() / "Library" / "Logs" / "Daedalus"
    else:
        folder = Path.home() / ".local" / "state" / "daedalus" / "desktop"
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        if folder.is_symlink():
            return None
        destination = folder / "desktop.log"
        if destination.is_symlink():
            return None
        logger = logging.getLogger("daedalus.desktop")
        if any(isinstance(handler, RotatingFileHandler)
               and Path(handler.baseFilename) == destination
               for handler in logger.handlers):
            return destination
        handler = RotatingFileHandler(
            destination, mode="a", maxBytes=1_000_000,
            backupCount=2, encoding="utf-8",
        )
        if os.name == "posix":
            os.chmod(destination, 0o600)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return destination
    except OSError:
        # A read-only home folder must not prevent the GUI from opening.
        return None
