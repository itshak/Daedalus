"""Supervised Selenium child process; Qt only reads its bounded local protocol.

Unlike an in-thread WebDriver, the browser process group can be force-killed
without waiting for a blocked ChromeDriver network call or macOS Keychain.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading

from PySide6.QtCore import QThread, Signal

from daedalus.desktop.selenium_auth import GameforgeCredentials

logger = logging.getLogger("daedalus.desktop.selenium_worker")


def child_command() -> list[str]:
    """PyInstaller's executable is the .app launcher, not a Python interpreter."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--selenium-child"]
    return [sys.executable, "-m", "daedalus.desktop.selenium_child"]


class SeleniumLoginWorker(QThread):
    stage_changed = Signal(str)
    credentials_resolved = Signal(str, bool)
    credentials_required = Signal()
    vault_ready = Signal(object)
    cookie_ready = Signal(str)
    login_failed = Signal(str)

    def __init__(
        self, world: str, credentials: GameforgeCredentials | None, parent=None, *,
        origin: str = "", account_id: str = "", record: dict[str, object] | None = None,
        sealed_vault: dict[str, object] | None = None, remember: bool = False,
        visible_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self._world = world
        self._credentials = credentials
        self._origin = origin
        self._account_id = account_id
        self._record = dict(record or {})
        self._sealed_vault = sealed_vault
        self._remember = remember
        self._visible_only = visible_only
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self.setObjectName("isolated_gameforge_selenium")

    @staticmethod
    def _kill_group(process: subprocess.Popen[bytes]) -> None:
        try:
            if os.name == "posix":
                # The helper might have exited while Chrome descendants are
                # still alive. Kill the group before reaping its PID.
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except ProcessLookupError:
            pass
        except OSError:
            try:
                process.kill()
            except OSError:
                pass

    def cancel(self) -> None:
        """Immediately kill the helper AND its ChromeDriver/Chrome descendants."""
        self._cancel.set()
        with self._lock:
            # Serialize with final wait()/reap() to prevent PID reuse racing
            # os.killpg on an unrelated process.
            if self._process is not None:
                self._kill_group(self._process)

    def run(self) -> None:
        process = None
        terminal_received = False
        try:
            if self._cancel.is_set():
                return
            payload = {
                "world": self._world, "account_id": self._account_id,
                "origin": self._origin, "record": self._record,
                "sealed_vault": self._sealed_vault, "remember": self._remember,
                "visible_only": self._visible_only,
                "credentials": ({
                    "email": self._credentials.email,
                    "password": self._credentials.password,
                } if self._credentials is not None else None),
            }
            # A new process group ensures cancellation cannot kill the GUI.
            logger.info("Starting isolated Gameforge login helper")
            self.stage_changed.emit("helper_starting")
            process = subprocess.Popen(
                child_command(),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=(os.name == "posix"),
            )
            with self._lock:
                self._process = process
            self.stage_changed.emit("helper_running")
            if self._cancel.is_set():
                self._kill_group(process)
                return
            assert process.stdin is not None
            process.stdin.write(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
            process.stdin.close()
            assert process.stdout is not None
            for raw in process.stdout:
                if self._cancel.is_set():
                    return
                if len(raw) > 16384:
                    self.stage_changed.emit("helper_protocol_error")
                    break
                try:
                    message = json.loads(raw)
                except (ValueError, UnicodeError):
                    self.stage_changed.emit("helper_protocol_error")
                    break
                if not isinstance(message, dict):
                    self.stage_changed.emit("helper_protocol_error")
                    break
                kind, value = message.get("kind"), message.get("value")
                if kind == "stage" and isinstance(value, str):
                    self.stage_changed.emit(value)
                elif kind == "credentials" and isinstance(value, dict):
                    email = value.get("email")
                    if not isinstance(email, str) or "@" not in email or len(email) > 320:
                        break
                    self.credentials_resolved.emit(email, value.get("remember") is True)
                elif kind == "credentials_required":
                    terminal_received = True
                    self.credentials_required.emit()
                    break
                elif kind == "vault" and isinstance(value, dict):
                    self.vault_ready.emit(value)
                elif kind == "cookie" and isinstance(value, str):
                    terminal_received = True
                    self.cookie_ready.emit(value)
                    break
                elif kind == "error" and isinstance(value, str):
                    terminal_received = True
                    # Only child-authored sanitized failures are shown.
                    self.login_failed.emit(value[:180])
                    break
                else:
                    self.stage_changed.emit("helper_protocol_error")
                    break
            if not terminal_received and not self._cancel.is_set():
                logger.warning("Selenium helper ended before reporting a result (exit code %s)", process.poll())
                self.stage_changed.emit("helper_exited_early")
                self.login_failed.emit(
                    "The isolated Selenium browser exited unexpectedly; no session was imported"
                )
        except (OSError, ValueError, TypeError) as exc:
            if not self._cancel.is_set():
                logger.warning("Unable to start or read isolated Selenium process: %s", type(exc).__name__)
                self.stage_changed.emit("helper_start_failed")
                self.login_failed.emit("The isolated Selenium login process could not start")
        finally:
            if process is not None:
                self._kill_group(process)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._kill_group(process)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
            with self._lock:
                self._process = None
            self._credentials = None
            logger.info("Isolated Gameforge login helper stopped")
