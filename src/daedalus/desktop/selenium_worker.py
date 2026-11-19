"""Isolated Selenium worker; never blocks the Mac Fluent event loop."""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QThread, Signal

from daedalus.desktop.selenium_auth import (
    GameforgeCredentials,
    SeleniumLoginUnavailable,
    login_world,
)


class SeleniumLoginWorker(QThread):
    stage_changed = Signal(str)
    cookie_ready = Signal(str)
    login_failed = Signal(str)

    def __init__(self, world: str, credentials: GameforgeCredentials, parent=None) -> None:
        super().__init__(parent)
        self._world = world
        self._credentials = credentials
        self._cancel = threading.Event()
        self.setObjectName("headless_selenium_gameforge")

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            cookie = login_world(
                self._credentials, self._world,
                notify=lambda value: self.stage_changed.emit(value),
                cancelled=self._cancel.is_set,
            )
            self.cookie_ready.emit(cookie)
        except SeleniumLoginUnavailable as exc:
            self.login_failed.emit(str(exc))
        except Exception:  # noqa: BLE001 - crossing QThread boundary always sanitizes errors
            logging.getLogger("daedalus.desktop.selenium_worker").warning(
                "Automatic Gameforge Selenium login interrupted"
            )
            self.login_failed.emit(
                "Automatic sign-in could not complete; no game session was imported"
            )
        finally:
            # Credentials must never be retained after the Selenium worker exits.
            self._credentials = None
