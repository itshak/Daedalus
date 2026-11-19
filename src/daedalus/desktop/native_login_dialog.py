"""Human-operated Gameforge login entirely inside the Mac's ephemeral Qt browser.

Only the exact secure `ikariam` cookie from the chosen world is read. No page
source, browser history, password, CAPTCHA response or lobby token is copied.
The browser has no persistent profile and is destroyed after a one-time login.
"""

from __future__ import annotations

import re
import time

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)
from shiboken6 import delete as delete_qobject

_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z")
_LOBBY = "https://lobby.ikariam.gameforge.com/"


def allowed_gameforge_navigation(url: QUrl, main_frame: bool) -> bool:
    """Top-level login never leaves HTTPS Gameforge-controlled domains.

    Embedded third-party challenge frames remain available for human login;
    their cookies will *never* be read, accepted or included in handoff.
    """
    if not main_frame:
        return True
    host = url.host().lower().rstrip(".")
    return (url.scheme() == "https" and
            (host == "gameforge.com" or host.endswith(".gameforge.com")))


def exact_world_cookie(cookie: QNetworkCookie, world_host: str) -> str | None:
    """Exclude parent-domain, unrelated-world, insecure and lobby credentials."""
    if (cookie.name().data() != b"ikariam"
            or not cookie.isSecure()
            or cookie.domain().lstrip(".").lower() != world_host.lower()):
        return None
    try:
        value = cookie.value().data().decode("ascii")
    except UnicodeDecodeError:
        return None
    if (not 16 <= len(value) <= 4096 or not value.isprintable()
            or any(c in value for c in " ;\\")):
        return None
    return value


class _OfficialLoginPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        return allowed_gameforge_navigation(url, is_main_frame)

    def createWindow(self, web_window_type):
        # A popup must not create an uncontrolled profile or browser window.
        # The user can navigate to the world via the explicit toolbar button.
        return None


class NativeLoginDialog(QDialog):
    """Native login browser with separate explicit operator handoff consent."""

    def __init__(self, *, world: str, player: str, ttl_seconds: int, parent=None,
                 load_initial: bool = True) -> None:
        super().__init__(parent)
        if (not _WORLD.fullmatch(world) or not isinstance(player, str)
                or not 0 < len(player) <= 80 or not 60 <= ttl_seconds <= 900):
            raise ValueError("An exact configured world/player and short deadline are required")
        self.world_host = f"{world}.ikariam.gameforge.com"
        self.world_url = QUrl("https://" + self.world_host + "/")
        self._deadline = time.monotonic() + ttl_seconds
        self._cookie: str | None = None
        self._browser_disposed = False
        self.setWindowTitle(f"Gameforge sign-in — {world}")
        self.resize(980, 780)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(SubtitleLabel(f"Sign in on your Mac — {player} ({world})"))
        instructions = CaptionLabel(
            "Log in on Gameforge's own page and complete any two-factor or CAPTCHA "
            "challenge yourself. Then open your selected world below. "
            "Daedalus will not read or send your password, MFA answer or lobby token."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        buttons = QHBoxLayout()
        self.lobby_button = PushButton("Open Gameforge login")
        self.lobby_button.clicked.connect(lambda: self.view.load(QUrl(_LOBBY)))
        buttons.addWidget(self.lobby_button)
        self.world_button = PushButton(f"Open {world} world")
        self.world_button.clicked.connect(lambda: self.view.load(self.world_url))
        buttons.addWidget(self.world_button)
        self.refresh_button = PushButton("Check signed-in session")
        self.refresh_button.clicked.connect(self._refresh_cookies)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)

        self.profile = QWebEngineProfile(self)
        if not self.profile.isOffTheRecord():
            raise RuntimeError("Gameforge login must use an off-the-record browser")
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        self.profile.cookieStore().cookieAdded.connect(self._cookie_added)
        self.page = _OfficialLoginPage(self.profile, self)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)
        layout.addWidget(self.view, 1)

        layout.addWidget(BodyLabel("First-time account? Enter its Gameforge email (optional)"))
        self.email_input = LineEdit()
        self.email_input.setPlaceholderText("Only needed if this account has no saved email binding")
        layout.addWidget(self.email_input)
        privacy = CaptionLabel(
            "Email, when supplied, travels inside the same one-time encrypted "
            "handoff as the world cookie. The server saves it only to its OS keyring."
        )
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        self.status = CaptionLabel("Waiting for a secure session in the selected world…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.approval = CheckBox(
            "I completed the Gameforge login and authorize one encrypted session handoff"
        )
        self.approval.stateChanged.connect(self._update_finish)
        layout.addWidget(self.approval)
        end = QHBoxLayout()
        self.cancel_button = PushButton("Cancel and discard browser")
        self.cancel_button.clicked.connect(self.reject)
        end.addWidget(self.cancel_button)
        self.finish_button = PrimaryPushButton("Verify session on server")
        self.finish_button.setEnabled(False)
        self.finish_button.clicked.connect(self._finish)
        end.addWidget(self.finish_button)
        layout.addLayout(end)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_finish)
        self.timer.start()
        if load_initial:
            self.view.load(QUrl(_LOBBY))

    def _cookie_added(self, cookie: QNetworkCookie) -> None:
        value = exact_world_cookie(cookie, self.world_host)
        if value is not None:
            self._cookie = value
            self.status.setText(
                "Secure world session detected. Confirm below to let the server "
                "verify your exact account and safely resume its worker."
            )
            self._update_finish()

    def _refresh_cookies(self) -> None:
        # Chromium emits cookieAdded for existing entries when loadAllCookies
        # is called, including when login occurred before a listener attached.
        self.profile.cookieStore().loadAllCookies()

    def _update_finish(self, *_args) -> None:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            self._cookie = None
            self.status.setText("The login window expired. Close it and start a fresh login.")
        self.finish_button.setEnabled(
            self._cookie is not None and remaining > 0 and self.approval.isChecked()
        )

    def _finish(self) -> None:
        if not self.finish_button.isEnabled():
            QMessageBox.warning(self, "Game login incomplete",
                                "Sign into the selected game world and approve the handoff.")
            return
        self.accept()

    def world_session(self) -> str:
        if self.result() != QDialog.Accepted or self._cookie is None:
            raise ValueError("The operator has not approved a verified world session")
        return self._cookie

    def discard_session(self) -> None:
        self._cookie = None
        self.email_input.clear()

    def optional_email(self) -> str:
        value = self.email_input.text().strip()
        if len(value) > 320 or any(c in value for c in "\r\n\x00"):
            raise ValueError("Invalid Gameforge email")
        return value

    def dispose_browser(self) -> None:
        """Destroy Chromium page *before* its off-record profile.

        Without this explicit ordering, releasing the dialog during app exit
        can leave a live renderer attached to an already-freed Qt profile.
        """
        if self._browser_disposed:
            return
        self._browser_disposed = True
        self.timer.stop()
        self.view.stop()
        self.profile.cookieStore().deleteAllCookies()
        self.profile.clearHttpCache()
        delete_qobject(self.view)
        delete_qobject(self.page)
        delete_qobject(self.profile)

    def done(self, result: int) -> None:
        self.timer.stop()
        # The dialog may be queried for the cookie only until it is destroyed;
        # it is never persisted in browser profile/cache or desktop settings.
        if not self._browser_disposed:
            self.profile.cookieStore().deleteAllCookies()
            self.profile.clearHttpCache()
        super().done(result)

    def closeEvent(self, event) -> None:
        self._cookie = None
        if not self._browser_disposed:
            self.profile.cookieStore().deleteAllCookies()
            self.profile.clearHttpCache()
        super().closeEvent(event)
