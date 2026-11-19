"""Native Mac progress/credential UI for the original headless Selenium login.

The Chrome driver runs on a background QThread. With saved Keychain
credentials no typing or confirmation is needed: it attempts a headless
session restore/login and closes automatically after a valid world cookie.
Only when Selenium DETECTS CAPTCHA does it open a visible Chrome window;
the original humanized LoginFlow waits for the operator to solve it.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.selenium_automation import (
    LoginCancelled,
    SeleniumLoginError,
    login_headless_first,
)
from daedalus.desktop.selenium_credentials import (
    GameforgeCredentialError,
    GameforgeCredentials,
    GameforgeKeychain,
)

logger = logging.getLogger("daedalus.selenium_dialog")


class SeleniumLoginWorker(QThread):
    progress = Signal(str)
    authenticated = Signal(object)
    failed = Signal(str)

    def __init__(
        self, *, store: GameforgeKeychain, credentials: GameforgeCredentials,
        world: str, player: str, remember: bool, parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.credentials = credentials
        self.world = world
        self.player = player
        self.remember = remember

    def run(self) -> None:
        try:
            cached = self.store.get_session() if self.remember else None
            session = login_headless_first(
                credentials=self.credentials, world=self.world, player=self.player,
                cached_session=cached, progress=self.progress.emit,
                cancelled=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                raise LoginCancelled("Gameforge login was cancelled")
            if self.remember:
                try:
                    self.store.save_credentials(self.credentials)
                    self.store.save_session(session.world_url, session.cookies)
                except GameforgeCredentialError:
                    self.progress.emit(
                        "Signed in, but Keychain could not save the login. "
                        "You may need to enter credentials next time."
                    )
            # Only the exact verified world cookie + email escape the Selenium
            # thread in memory; never log or persist the cookie in Qt preferences.
            self.authenticated.emit({
                "cookie": session.cookie,
                "email": session.email,
                "manual_captcha": session.manual_captcha,
            })
        except LoginCancelled:
            self.failed.emit("Login cancelled. No session was transferred.")
        except (SeleniumLoginError, GameforgeCredentialError) as exc:
            self.failed.emit(str(exc))
        except ImportError:
            self.failed.emit(
                "Selenium/Chrome support is missing from this Mac installation. "
                "Reinstall the native Daedalus app or its desktop dependencies."
            )
        except Exception:  # noqa: BLE001 - redact browser internals
            logger.warning("Selenium login failed; internal browser details redacted")
            self.failed.emit(
                "Unable to complete automatic Gameforge login. Check that Chrome "
                "and a compatible ChromeDriver are installed."
            )


class SeleniumLoginDialog(QDialog):
    """Account-scoped headless login with a guided manual CAPTCHA fallback."""

    def __init__(
        self, *, backend_url: str, account_id: str, world: str,
        player: str, ttl_seconds: int, parent=None, auto_start: bool = True,
    ) -> None:
        super().__init__(parent)
        if not 60 <= ttl_seconds <= 900:
            raise ValueError("A valid short-lived login authorization is required")
        self.store = GameforgeKeychain(backend_url, account_id, world, player)
        self.world = world
        self.player = player
        self._session: dict[str, object] | None = None
        self._credentials: GameforgeCredentials | None = None
        self._worker: SeleniumLoginWorker | None = None
        self._cancel_requested = False
        self._error_message = ""
        self.setWindowTitle(f"Automatic Gameforge sign-in — {world}")
        self.setMinimumSize(520, 325)
        self.resize(640, 390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(13)
        layout.addWidget(SubtitleLabel(f"Sign in automatically — {player} ({world})"))
        description = CaptionLabel(
            "Daedalus reuses the original IkaBot headless Selenium login and "
            "saved session first. No browser opens unless Gameforge displays a "
            "CAPTCHA. If challenged, complete it in Chrome; Daedalus continues "
            "automatically and the server independently verifies your player."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.email_label = BodyLabel("Gameforge email (first use only)")
        layout.addWidget(self.email_label)
        self.email_input = LineEdit()
        self.email_input.setAccessibleName("Gameforge email for selected account")
        self.email_input.setPlaceholderText("name@example.com")
        layout.addWidget(self.email_input)
        self.password_label = BodyLabel("Gameforge password (first use only)")
        layout.addWidget(self.password_label)
        self.password_input = LineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setAccessibleName("Gameforge password for selected account")
        layout.addWidget(self.password_input)

        self.remember = CheckBox("Save login and game session in macOS Keychain")
        self.remember.setChecked(True)
        self.remember.setToolTip(
            "Only your Mac Keychain stores this account's Gameforge credentials. "
            "Daedalus sends the world cookie encrypted and never sends your password."
        )
        layout.addWidget(self.remember)
        self.change_button = PushButton("Use different Gameforge credentials")
        self.change_button.clicked.connect(self._change_credentials)
        layout.addWidget(self.change_button)

        self.status = BodyLabel("Preparing secure automatic sign-in…")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Automatic login and CAPTCHA status")
        layout.addWidget(self.status)
        layout.addStretch(1)
        actions = QHBoxLayout()
        self.cancel_button = PushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_button)
        self.start_button = PrimaryPushButton("Sign in automatically")
        self.start_button.clicked.connect(self._start)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)

        try:
            self._credentials = self.store.get_credentials()
        except GameforgeCredentialError:
            self._credentials = None
            self.status.setText(
                "Saved credentials are unavailable. Enter them once for automatic login."
            )
        self._show_credentials(self._credentials is None)
        if self._credentials is not None and auto_start:
            QTimer.singleShot(0, self._start)

    def _show_credentials(self, show: bool) -> None:
        for widget in (
            self.email_label, self.email_input, self.password_label, self.password_input,
        ):
            widget.setVisible(show)
        self.change_button.setVisible(not show)
        self.start_button.setText(
            "Sign in automatically" if show else "Continue headless sign-in"
        )

    def _change_credentials(self) -> None:
        if self._worker is not None:
            return
        self._credentials = None
        self.email_input.clear()
        self.password_input.clear()
        self._show_credentials(True)
        self.status.setText("Enter credentials for this account. They stay on this Mac.")

    def _start(self) -> None:
        if self._worker is not None or self._cancel_requested:
            return
        if self._credentials is None:
            try:
                self._credentials = GameforgeCredentials(
                    self.email_input.text().strip(), self.password_input.text()
                )
            except GameforgeCredentialError:
                QMessageBox.warning(
                    self, "Credentials required",
                    "Enter a valid Gameforge email and password for the selected account.",
                )
                return
        self.password_input.clear()  # do not leave plaintext in a Qt text field
        self.email_input.clear()
        self._show_credentials(False)
        self.start_button.setEnabled(False)
        self.change_button.setEnabled(False)
        self.status.setText("Opening headless Chrome (no manual action needed)…")
        self._worker = SeleniumLoginWorker(
            store=self.store, credentials=self._credentials,
            world=self.world, player=self.player,
            remember=self.remember.isChecked(), parent=self,
        )
        self._worker.progress.connect(self.status.setText)
        self._worker.authenticated.connect(self._authenticated)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _authenticated(self, payload: dict[str, object]) -> None:
        if not self._cancel_requested:
            self._session = payload
            self.status.setText("Headless login finished. Verifying securely on the server…")

    def _failed(self, message: str) -> None:
        self._error_message = message
        self.status.setText(message)

    def _worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            # An unused Qt child must not retain a Gameforge password.
            worker.credentials = None
            worker.deleteLater()
        self._credentials = None
        if self._cancel_requested:
            super().reject()
        elif self._session is not None:
            self.accept()
        else:
            self.start_button.setEnabled(True)
            self.change_button.setEnabled(True)
            self.start_button.setText("Retry automatic login")
            try:
                self._credentials = self.store.get_credentials()
            except GameforgeCredentialError:
                self._credentials = None
            self._show_credentials(self._credentials is None)

    def store_available(self) -> bool:
        try:
            return self.store.get_credentials() is not None
        except GameforgeCredentialError:
            return False

    def _cancel(self) -> None:
        self._cancel_requested = True
        if self._worker is not None and self._worker.isRunning():
            self.status.setText("Cancelling browser login and closing Chrome…")
            self.cancel_button.setEnabled(False)
            self._worker.requestInterruption()
        else:
            super().reject()

    def reject(self) -> None:
        self._cancel()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._cancel()
            event.ignore()
            return
        super().closeEvent(event)

    def world_session(self) -> str:
        if self.result() != QDialog.Accepted or self._session is None:
            raise ValueError("No automatic world session has been verified")
        return str(self._session["cookie"])

    def optional_email(self) -> str:
        if self._session is None:
            return ""
        return str(self._session["email"])

    def discard_session(self) -> None:
        self._session = None
        self._credentials = None
        self.password_input.clear()
        self.email_input.clear()

    def dispose_browser(self) -> None:
        """Selenium worker has already closed Chrome in finally before accept()."""
        self.discard_session()
