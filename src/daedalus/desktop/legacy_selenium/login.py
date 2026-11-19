"""Login flow: Gameforge lobby → server lobby → game window.

Includes CAPTCHA pause (manual solve), human-like mouse/typing emulation,
retries, and ad pop-up closing.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from daedalus.desktop.legacy_selenium import humanize
from daedalus.desktop.legacy_selenium.settings import Settings

logger = logging.getLogger(__name__)

LOBBY_URL = "https://lobby.ikariam.gameforge.com/ru_RU/"
CAPTCHA_XPATH = "//span[contains(text(), 'Подтвердите, что вы человек')]"
LOGIN_ERROR_XPATH = "//div[contains(text(), 'Неизвестный e-mail адрес или неверный пароль.')]"
PLAY_BUTTON_XPATH = "//button[contains(text(), 'Последнее сохранение')]"
COOKIE_ACCEPT_XPATH = "//button[contains(@class,'cookiebanner') and contains(., 'Принять')]"
LOGIN_TAB_XPATH = "//div[@id='loginRegisterTabs']/ul[@class='tabsList']/li"
CITY_BREAD_XPATH = "//span[@id='js_cityBread']"


class LoginError(Exception):
    """Login could not be completed (bad credentials, CAPTCHA, timeouts)."""


class LoginFlow:
    def __init__(
        self,
        driver: WebDriver,
        settings: Settings,
        max_retries: int = 3,
        humanize: bool = True,
        captcha_check: float = 5.0,
        captcha_wait: float = 180,
        play_timeout: float = 25.0,
        game_timeout: float = 25.0,
        window_timeout: float = 10.0,
    ) -> None:
        self.driver = driver
        self.settings = settings
        self.max_retries = max_retries
        self.humanize = humanize
        self.captcha_check = captcha_check
        self.captcha_wait = captcha_wait
        self.play_timeout = play_timeout
        self.game_timeout = game_timeout
        self.window_timeout = window_timeout

    # ---------- helpers ----------

    def _sleep(self, seconds: float) -> None:
        if self.humanize:
            humanize.human_idle(self.driver, seconds)
        else:
            time.sleep(seconds)

    def _wait(self, timeout: float):
        return WebDriverWait(self.driver, timeout)

    def _find(self, by, value: str, timeout: float = 10) -> WebElement:
        return self._wait(timeout).until(EC.presence_of_element_located((by, value)))

    def _clickable(self, by, value: str, timeout: float = 10) -> WebElement:
        return self._wait(timeout).until(EC.element_to_be_clickable((by, value)))

    def _click(self, element: WebElement, from_element: WebElement | None = None) -> None:
        if self.humanize:
            try:
                humanize.human_click(self.driver, element, from_element)
                return
            except WebDriverException:
                logger.debug("humanized click failed, falling back to plain click")
        element.click()

    def _type(self, field: WebElement, text: str, from_element: WebElement | None = None) -> None:
        if self.humanize:
            try:
                humanize.human_type(self.driver, field, text, from_element)
                return
            except WebDriverException:
                logger.debug("humanized typing failed, falling back to plain typing")
        try:
            field.click()
        except WebDriverException:
            try:
                self.driver.execute_script("arguments[0].focus();", field)
            except WebDriverException:
                pass
        field.send_keys(text)

    def _close_blank_windows(self) -> None:
        """Close stray blank windows (uc's detached Chrome launch artifact).

        undetected-chromedriver starts Chrome detached, which can leave an
        empty new-tab window next to the real session window.
        """
        keep = self.driver.current_window_handle
        for handle in list(self.driver.window_handles):
            if handle == keep:
                continue
            try:
                self.driver.switch_to.window(handle)
                url = self.driver.current_url or ""
            except WebDriverException:
                continue
            if not url or url.startswith(("chrome://", "about:")):
                try:
                    self.driver.close()
                except WebDriverException:
                    continue
        self.driver.switch_to.window(keep)

    def _window_urls(self) -> dict[str, str]:
        """Map every open window handle to its URL (current window restored)."""
        urls: dict[str, str] = {}
        current = self.driver.current_window_handle
        for handle in list(self.driver.window_handles):
            try:
                self.driver.switch_to.window(handle)
                urls[handle] = self.driver.current_url or ""
            except WebDriverException:
                continue
        try:
            self.driver.switch_to.window(current)
        except WebDriverException:
            pass
        return urls

    def _inject_cookies(self, cookies: list[dict]) -> None:
        """Set saved session cookies on the current origin.

        ``add_cookie`` requires the cookie domain to match the current page,
        which breaks when the server bounces us to the lobby hub before the
        game-domain cookies (`s53-ru...`) can be injected. Chrome's CDP has no
        such restriction, so it is used first; plain ``add_cookie`` remains the
        fallback (per-cookie, ignoring failed ones).
        """
        injector = getattr(self.driver, "execute_cdp_cmd", None)
        if injector is not None:
            try:
                cdp_cookies = []
                for c in cookies:
                    entry: dict = {
                        "name": c["name"],
                        "value": c.get("value", ""),
                        "domain": c.get("domain", ""),
                        "path": c.get("path", "/"),
                        "httpOnly": bool(c.get("httpOnly")),
                        "secure": bool(c.get("secure")),
                    }
                    if c.get("expiry") is not None:
                        entry["expires"] = int(c["expiry"])
                    same_site = c.get("sameSite")
                    if same_site in ("Strict", "Lax", "None"):
                        entry["sameSite"] = same_site
                    cdp_cookies.append(entry)
                injector("Network.setCookies", {"cookies": cdp_cookies})
                logger.debug("injected %d cookies via CDP", len(cdp_cookies))
                return
            except WebDriverException:
                logger.debug("CDP cookie injection failed, falling back to add_cookie")
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except WebDriverException:
                logger.debug("could not restore cookie %r", cookie.get("name"))

    def _is_gameforge_tab(self, url: str) -> bool:
        """True when the URL belongs to the game/lobby (must never be closed)."""
        return bool(url) and "gameforge.com" in url

    def _game_window_handle(self) -> str | None:
        """Handle of the game-server window (not the lobby), if any."""
        for handle, url in self._window_urls().items():
            if handle == self.driver.current_window_handle:
                continue
            if "ikariam.gameforge.com" in url and not url.startswith("https://lobby."):
                return handle
        # the game window may still be loading (no URL yet) — assume the newest one
        for handle in reversed(self.driver.window_handles):
            if handle != self.driver.current_window_handle:
                return handle
        return None

    def _close_extra_windows(self) -> None:
        """Close stray ad windows only; NEVER a lobby or game tab.

        The lobby tab that the game window was opened from must stay alive —
        the game session dies with it. Tabs are classified by URL, not by
        handle order (`window_handles` ordering is not reliable across
        browsers, and the game tab may sit at any index).
        """
        keep_current = self.driver.current_window_handle
        keep = {keep_current}
        keep.update(handle for handle, url in self._window_urls().items() if not url or self._is_gameforge_tab(url))
        for handle in list(self.driver.window_handles):
            if handle in keep:
                continue
            try:
                self.driver.switch_to.window(handle)
                self.driver.close()
            except WebDriverException:
                logger.debug("could not close window %s", handle)
        self.driver.switch_to.window(keep_current)

    def _wait_captcha(self) -> None:
        """Detect a displayed CAPTCHA and wait for the manual solve.

        The wait window keeps extending while the CAPTCHA is still on screen, so a
        slow solve never kills the login session. Returns as soon as it is gone.
        """
        try:
            self._clickable(By.XPATH, CAPTCHA_XPATH, timeout=self.captcha_check)
        except TimeoutException:
            return
        logger.warning("CAPTCHA detected — solve it manually in the browser window")
        deadline = time.time() + self.captcha_wait
        while True:
            try:
                self.driver.find_element(By.XPATH, CAPTCHA_XPATH)
            except NoSuchElementException:
                logger.info("CAPTCHA resolved, continuing")
                return
            if time.time() >= deadline:
                logger.warning("CAPTCHA still displayed after %.0fs — extending the wait", self.captcha_wait)
                deadline = time.time() + self.captcha_wait
            self._sleep(3)

    def _captcha_present(self) -> bool:
        try:
            self.driver.find_element(By.XPATH, CAPTCHA_XPATH)
            return True
        except NoSuchElementException:
            return False

    def _play_button_present(self) -> bool:
        try:
            self.driver.find_element(By.XPATH, PLAY_BUTTON_XPATH)
            return True
        except NoSuchElementException:
            return False

    def _dismiss_cookie_banner(self) -> bool:
        """Click the consent-banner "Принять Cookies" button when present.

        The Gameforge lobby overlays the play button with ``cookiebanner3``,
        which silently swallows human-like pointer clicks on it (the click is
        "intercepted"), so the game window never opens in headless mode.
        Returns True when the banner was handled.
        """
        try:
            buttons = self.driver.find_elements(By.XPATH, COOKIE_ACCEPT_XPATH)
        except WebDriverException:
            return False
        if not buttons:
            return False
        try:
            buttons[0].click()
            self._sleep(1)
            logger.info("cookie consent banner accepted")
        except WebDriverException:
            try:
                self.driver.execute_script("document.querySelectorAll('.cookiebanner').forEach(e => e.remove())")
                logger.info("cookie consent banner removed via DOM")
            except WebDriverException:
                logger.debug("could not remove cookie consent banner")
        return True

    # ---------- main flow ----------

    def try_restore(self, url: str, cookies: list[dict], username: str = "") -> bool:
        """Restore a saved game session (game URL + cookies) without logging in.

        Injects the saved cookies and navigates to the saved game URL. The game
        window may load directly (full session still valid), or the server may
        bounce us to the lobby's play-button screen (lobby session only) — in
        that case the play button is clicked and the game window is awaited
        like after a normal login. Returns True when the game window loads;
        False when neither appears (session gone) — callers fall back to a
        full ``log_in``.
        """
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if not parsed.scheme or not parsed.netloc:
            logger.warning("saved token has no usable game URL (%r), ignoring", url)
            return False
        try:
            self.driver.get(origin)
            self._inject_cookies(cookies)
            self.driver.get(url)
            self._close_blank_windows()
            self._wait(self.game_timeout).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, CITY_BREAD_XPATH)),
                    EC.presence_of_element_located((By.XPATH, PLAY_BUTTON_XPATH)),
                )
            )
            if self._play_button_present():
                if not self._await_game_window(username):
                    return False
            else:
                close_ad_if_present(self.driver)
            logger.info("session restored from saved token")
            return True
        except TimeoutException:
            logger.info("saved token expired — falling back to full login")
            return False
        except WebDriverException as exc:
            logger.warning("token restore failed (%s) — falling back to full login", exc)
            return False

    def log_in(self, email: str, username: str, password: str | None = None) -> bool:
        for attempt in range(1, self.max_retries + 1):
            logger.info("login attempt %d/%d for %s", attempt, self.max_retries, username)
            try:
                return self._attempt(email, username, password)
            except (TimeoutException, WebDriverException) as exc:
                logger.warning("login attempt %d failed: %s", attempt, exc)
                time.sleep(2)
        logger.error("login failed for %s after %d attempts", username, self.max_retries)
        return False

    def _attempt(self, email: str, username: str, password: str | None = None) -> bool:
        password = password or self.settings.password
        self.driver.get(LOBBY_URL)
        self._close_blank_windows()
        self._wait_captcha()

        # The lobby session may already be valid (restore partially succeeded):
        # the hub shows a play button instead of the login form. Go straight to
        # awaiting the game window instead of failing on a missing login tab.
        if self._play_button_present():
            logger.info("lobby session already active for %s — skipping login form", username)
            return self._await_game_window(username)

        tab = self._clickable(By.XPATH, LOGIN_TAB_XPATH, timeout=15)
        self._click(tab)
        self._sleep(1)

        email_field = self._find(By.NAME, "email")
        password_field = self._find(By.NAME, "password")
        submit = self._clickable(By.XPATH, "//button[@type='submit']")

        self._type(email_field, email)
        self._sleep(random_short())
        self._type(password_field, password, from_element=email_field)
        self._sleep(random_short())
        self._click(submit, from_element=password_field)
        logger.info("login form submitted")

        return self._await_game_window(username)

    def _await_game_window(self, username: str) -> bool:
        try:
            play_clicked = False
            expected_windows = len(self.driver.window_handles)
            deadline = time.time() + self.play_timeout
            while not play_clicked:
                if self._login_error_present():
                    logger.error("login error: wrong email or password for %s", username)
                    return False
                if self._captcha_present():
                    self._wait_captcha()
                    deadline = time.time() + self.play_timeout  # fresh window after solving
                    continue
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    play = self._clickable(By.XPATH, PLAY_BUTTON_XPATH, timeout=min(5.0, remaining))
                    expected_windows = len(self.driver.window_handles) + 1
                    self._dismiss_cookie_banner()
                    try:
                        play = self._clickable(By.XPATH, PLAY_BUTTON_XPATH, timeout=5)
                    except TimeoutException:
                        logger.debug("play button stale after banner dismiss, retrying")
                        self._sleep(1)
                        continue
                    self._click(play)
                    play_clicked = True
                except StaleElementReferenceException:
                    logger.warning("play button stale, retrying")
                    self._sleep(1)
                except TimeoutException:
                    pass
            if play_clicked:
                logger.info("play button clicked, opening game window")
                try:
                    self._wait(self.window_timeout).until(EC.number_of_windows_to_be(expected_windows))
                except TimeoutException:
                    # the game may load in the current window (no popup) — still checks bread below
                    logger.debug("game window did not open as a new tab within %.0fs", self.window_timeout)
                if len(self.driver.window_handles) > 1:
                    game_handle = self._game_window_handle()
                    if game_handle is not None:
                        self.driver.switch_to.window(game_handle)
                    self._close_extra_windows()
                logger.info("open tabs after login: %s", list(self.driver.window_handles))
            else:
                logger.warning("no play button within %.0fs for %s", self.play_timeout, username)
        except WebDriverException as exc:
            logger.warning("play click failed: %s", exc)

        try:
            self._find(By.XPATH, CITY_BREAD_XPATH, timeout=self.game_timeout)
        except TimeoutException:
            if self._login_error_present():
                logger.error("login error: wrong email or password for %s", username)
                return False
            logger.error("game window did not load for %s (url=%s)", username, self.driver.current_url)
            return False

        close_ad_if_present(self.driver)
        logger.info("logged in: %s", username)
        return True

    def _login_error_present(self) -> bool:
        try:
            self.driver.find_element(By.XPATH, LOGIN_ERROR_XPATH)
            return True
        except NoSuchElementException:
            return False


def random_short() -> float:
    import random

    return random.uniform(0.4, 1.2)


def close_ad_if_present(driver: WebDriver) -> bool:
    """Close the ad pop-up if present after login. Returns True if closed."""
    time.sleep(2)
    selectors = [
        (By.CLASS_NAME, "openX_int_closeButton"),
        (By.XPATH, "//a[normalize-space(text())='Закрыть' or normalize-space(text())='Close']"),
        (By.XPATH, "//button[normalize-space(text())='Закрыть' or normalize-space(text())='Close']"),
    ]
    for by, value in selectors:
        try:
            for btn in driver.find_elements(by, value):
                try:
                    btn.click()
                    logger.info("ad closed (%s)", value)
                    return True
                except WebDriverException:
                    continue
        except WebDriverException:
            continue
    return False
