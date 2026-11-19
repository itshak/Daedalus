"""Headless-first Daedalus adapter around the user's ORIGINAL IkaBot Selenium login.

The actual browser creation, undetected-Chromedriver fallback, LoginFlow,
restore, popup handling, humanized mouse and typing are imported from the
copied modules. Only CAPTCHA escalates from headless to visible Chrome.
No game engine operation or REST request is performed here.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from daedalus.desktop.legacy_selenium.browser import create_driver, quit_driver
from daedalus.desktop.legacy_selenium.login import CAPTCHA_XPATH, LoginFlow
from daedalus.desktop.legacy_selenium.settings import Settings
from daedalus.desktop.selenium_credentials import GameforgeCredentials

logger = logging.getLogger("daedalus.selenium_login")
_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z", re.IGNORECASE)
Progress = Callable[[str], None]
Cancelled = Callable[[], bool]
DriverFactory = Callable[[str, bool], object]


class SeleniumLoginError(RuntimeError):
    """A secret-free, actionable error for a failed local login."""


class LoginCancelled(SeleniumLoginError):
    pass


class CaptchaRequired(SeleniumLoginError):
    """A real Gameforge challenge was detected in the headless browser."""


@dataclass(frozen=True, repr=False)
class SeleniumWorldSession:
    cookie: str = field(repr=False)
    email: str
    world_url: str
    cookies: list[dict[str, object]] = field(repr=False)
    manual_captcha: bool


class DaedalusLoginFlow(LoginFlow):
    """Original LoginFlow with cancellation, CAPTCHA escalation and origin guard."""

    def __init__(
        self, driver: object, settings: Settings, *,
        headless: bool, cancelled: Cancelled,
        progress: Progress,
    ) -> None:
        super().__init__(
            driver, settings, humanize=not headless,
            # Retain upstream Selenium deadlines and retries; session restore
            # and CAPTCHA waits use the same original flow.
            captcha_check=2.0,
        )
        self.headless = headless
        self._cancelled = cancelled
        self._progress = progress

    def _check_cancelled(self) -> None:
        if self._cancelled():
            raise LoginCancelled("Gameforge login was cancelled")

    def _captcha_present(self) -> bool:
        """Only a *visible* challenge justifies opening Chrome.

        The original Russian IkaBot XPath remains the first selector. A hidden
        placeholder in the DOM is not an actual challenge to solve.
        """
        try:
            from selenium.webdriver.common.by import By

            selectors = (
                (By.XPATH, CAPTCHA_XPATH),
                (By.CSS_SELECTOR,
                 "iframe[src*='captcha'], iframe[src*='hcaptcha'], "
                 "iframe[src*='recaptcha'], iframe[src*='turnstile'], "
                 "[id*='captcha' i], [class*='captcha' i]"),
            )
            return any(
                widget.is_displayed()
                for by, selector in selectors
                for widget in self.driver.find_elements(by, selector)
            )
        except (AttributeError, RuntimeError):
            return False
        except Exception:  # noqa: BLE001 - browser failures may contain secrets
            # Unknown browser errors never falsely trigger visible CAPTCHA mode.
            return False

    def _wait_captcha(self) -> None:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait

        self._check_cancelled()
        if self.headless:
            try:
                WebDriverWait(self.driver, self.captcha_check).until(
                    lambda _driver: self._captcha_present()
                )
            except TimeoutException:
                return
            self._progress("CAPTCHA detected; opening visible Chrome for manual verification")
            raise CaptchaRequired("Gameforge requested a CAPTCHA")
        if self._captcha_present():
            self._progress("Complete the CAPTCHA in Chrome. Login will resume automatically.")
            # Manual response is required ONLY while an actual challenge remains.
            while self._captcha_present():
                self._check_cancelled()
                self._sleep(1)
            self._progress("CAPTCHA solved; finishing automatic sign-in")
        else:
            # Preserve the original login flow's pre-submit CAPTCHA probe.
            super()._wait_captcha()

    def _sleep(self, seconds: float) -> None:
        self._check_cancelled()
        super()._sleep(seconds)  # original human_idle in visible mode
        self._check_cancelled()

    def _type(self, field, text: str, from_element=None) -> None:
        self._check_cancelled()
        url = urlsplit(str(self.driver.current_url))
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not (
            host == "gameforge.com" or host.endswith(".gameforge.com")
        ):
            raise SeleniumLoginError(
                "The Gameforge login page changed origin. Credentials were not entered."
            )
        super()._type(field, text, from_element=from_element)

    def _await_game_window(self, username: str) -> bool:
        result = super()._await_game_window(username)
        if not result and self.headless and self._captcha_present():
            self._progress("CAPTCHA detected; opening visible Chrome for manual verification")
            raise CaptchaRequired("Gameforge requested a CAPTCHA")
        return result


def _world_session(driver: object, *, world: str, email: str, manual: bool) -> SeleniumWorldSession:
    expected = f"{world.casefold()}.ikariam.gameforge.com"
    url = str(driver.current_url)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected
        or parsed.username or parsed.password or parsed.port
    ):
        raise SeleniumLoginError("The browser did not reach the configured game world")
    # Original IkaBot reads driver.get_cookies() after the login/game-window
    # switch. Reuse the same result, but hand off ONLY the exact secure world
    # cookie. The server will independently attest the configured player.
    try:
        cookies = driver.get_cookies()
        matching = [
            c for c in cookies if isinstance(c, dict)
            and c.get("name") == "ikariam"
            and str(c.get("domain", "")).lstrip(".").lower() == expected
            and c.get("secure") is True
            and isinstance(c.get("value"), str)
        ]
    except Exception as exc:
        raise SeleniumLoginError("Could not read the authenticated Gameforge world session") from exc
    if len(matching) != 1:
        raise SeleniumLoginError(
            "The selected world has no unique secure game session; no handoff occurred"
        )
    cookie = str(matching[0]["value"])
    if not 16 <= len(cookie) <= 4096 or not cookie.isprintable() or any(
        c in cookie for c in ' ;"'
    ):
        raise SeleniumLoginError("The selected world session was invalid")
    return SeleniumWorldSession(
        cookie=cookie, email=email, world_url=url,
        cookies=cookies, manual_captcha=manual,
    )


def login_headless_first(
    *,
    credentials: GameforgeCredentials,
    world: str,
    player: str,
    cached_session: dict[str, object] | None = None,
    progress: Progress = lambda _message: None,
    cancelled: Cancelled = lambda: False,
    driver_factory: DriverFactory = create_driver,
    driver_cleanup: Callable[[object], None] = quit_driver,
    attempts: int = 3,
) -> SeleniumWorldSession:
    """Restore first; otherwise use original headless login, visible only for CAPTCHA.

    Never opens a visible browser for wrong credentials, a failed scrape or a
    missing city. A fresh visible Chrome session is used for human CAPTCHA
    completion just like the old IkaBot runner's final fallback.
    """
    if not isinstance(world, str) or not _WORLD.fullmatch(world):
        raise SeleniumLoginError("A configured exact game world is required")
    if not isinstance(player, str) or not 1 <= len(player) <= 80:
        raise SeleniumLoginError("A configured exact player is required")
    if not 1 <= attempts <= 3:
        raise ValueError("At most three local browser attempts are permitted")
    if not isinstance(credentials, GameforgeCredentials):
        raise SeleniumLoginError("Local Gameforge login credentials are missing")
    require_visible_captcha = False
    for index in range(attempts):
        if cancelled():
            raise LoginCancelled("Gameforge login was cancelled")
        driver = None
        try:
            progress("Restoring saved session" if index == 0 and cached_session
                     else "Signing in automatically in headless Chrome")
            driver = driver_factory("chrome", True)
            flow = DaedalusLoginFlow(
                driver, Settings(password=credentials.password),
                headless=True, cancelled=cancelled, progress=progress,
            )
            logged_in = False
            if index == 0 and cached_session is not None:
                # Keychain validates exact world host and secure cookie domains.
                logged_in = flow.try_restore(
                    str(cached_session["url"]),
                    list(cached_session["cookies"]),
                    player,
                )
                if not logged_in:
                    progress("Saved session expired; signing in headlessly")
            if not logged_in:
                logged_in = flow.log_in(
                    credentials.email, player, password=credentials.password,
                )
            if logged_in:
                progress("Verifying the configured world")
                result = _world_session(
                    driver, world=world, email=credentials.email, manual=False,
                )
                progress("Secure world session captured; verifying on the backend")
                return result
        except CaptchaRequired:
            require_visible_captcha = True
            break
        except LoginCancelled:
            raise
        except SeleniumLoginError:
            raise
        except Exception:  # noqa: BLE001 - browser failures may contain secrets
            logger.warning("Headless browser attempt failed (secrets omitted)")
            # Follow legacy per-account retry behavior without surfacing driver internals.
        finally:
            if driver is not None:
                try:
                    driver_cleanup(driver)
                except Exception:  # noqa: BLE001 - browser failures may contain secrets
                    logger.warning("Could not fully close the headless Chrome instance")
    if not require_visible_captcha:
        raise SeleniumLoginError(
            "Automatic Gameforge sign-in did not succeed. Check saved credentials "
            "or retry; no CAPTCHA was detected, so no browser was opened."
        )

    if cancelled():
        raise LoginCancelled("Gameforge login was cancelled")
    progress("CAPTCHA detected; use the visible Chrome window to solve it manually")
    driver = None
    try:
        driver = driver_factory("chrome", False)
        flow = DaedalusLoginFlow(
            driver, Settings(password=credentials.password),
            headless=False, cancelled=cancelled, progress=progress,
        )
        # The original LoginFlow uses human_click, human_type and human_idle
        # in visible mode, then waits until CAPTCHA disappears.
        if not flow.log_in(credentials.email, player, password=credentials.password):
            raise SeleniumLoginError(
                "Visible Gameforge login did not complete; check the challenge "
                "and account credentials"
            )
        progress("CAPTCHA solved; verifying the configured game world")
        result = _world_session(
            driver, world=world, email=credentials.email, manual=True,
        )
        progress("Secure world session captured; verifying on the backend")
        return result
    finally:
        if driver is not None:
            try:
                driver_cleanup(driver)
            except Exception:  # noqa: BLE001 - browser failures may contain secrets
                logger.warning("Could not fully close the visible Chrome instance")
