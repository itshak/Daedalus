"""Headless-first Selenium login, adapted from itshak/ikabot warehouse bot.

Uses the legacy lobby selectors and play-button workflow. Headless Chrome is
the default. An actual CAPTCHA alone triggers a visible Chrome retry; Selenium
never solves a challenge. Only the exact, secure world cookie is returned for
the established encrypted server handoff and independent player verification.
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

log = logging.getLogger("daedalus.desktop.selenium_auth")
WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z", re.IGNORECASE)
LOBBY_URL = "https://lobby.ikariam.gameforge.com/ru_RU/"
CAPTCHA_XPATHS = (
    "//span[contains(text(), 'Подтвердите, что вы человек')]",
    ("//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
     "'abcdefghijklmnopqrstuvwxyz'),'verify you are human')]"),
    ("//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
     "'abcdefghijklmnopqrstuvwxyz'),'captcha')]"),
)
CAPTCHA_FRAMES = (
    "iframe[src*='captcha']", "iframe[title*='CAPTCHA']",
    "iframe[title*='captcha']", "iframe[src*='arkoselabs']",
    "iframe[src*='hcaptcha']", "iframe[src*='recaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
)
LOGIN_TAB_XPATH = "//div[@id='loginRegisterTabs']/ul[@class='tabsList']/li"
CITY_BREAD_XPATH = "//span[@id='js_cityBread']"
PLAY_BUTTON_XPATH = (
    "//button[contains(text(), 'Последнее сохранение') "
    "or contains(text(), 'Last played') or contains(text(), 'Last save')]"
)
LOGIN_ERROR_XPATH = (
    "//div[contains(text(), 'Неизвестный e-mail адрес или неверный пароль.') "
    "or contains(text(), 'Incorrect password') "
    "or contains(text(), 'Invalid email')]"
)
CHROME_FLAGS = (
    "--no-first-run", "--no-default-browser-check", "--disable-gpu",
    "--disable-dev-shm-usage",
)


class SeleniumLoginUnavailable(RuntimeError):
    """Sanitized authentication failure; never include user credentials."""


class ManualChallengeRequired(SeleniumLoginUnavailable):
    """Visible user challenge detected; only this triggers windowed Chrome."""


@dataclass(frozen=True)
class GameforgeCredentials:
    email: str
    password: str

    def __post_init__(self) -> None:
        if (not isinstance(self.email, str) or not 3 <= len(self.email) <= 320
                or "@" not in self.email or any(c in self.email for c in "\x00\r\n")
                or not isinstance(self.password, str)
                or not 1 <= len(self.password) <= 1024
                or any(c in self.password for c in "\x00\r\n")):
            raise SeleniumLoginUnavailable("A valid Gameforge email and password are required")

    def __repr__(self) -> str:
        return "GameforgeCredentials(<redacted>)"


def create_chrome(headless: bool):
    """Legacy Chrome driver selection and headless flags with plain fallback."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        raise SeleniumLoginUnavailable("Selenium is not installed in this Mac preview") from exc
    options = Options()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    for arg in CHROME_FLAGS:
        options.add_argument(arg)
    try:
        import undetected_chromedriver as uc

        opts = uc.ChromeOptions()
        for arg in options.arguments:
            opts.add_argument(arg)
        driver = uc.Chrome(options=opts, use_subprocess=False)
    except Exception:  # noqa: BLE001 - optional legacy Chrome driver may fail in many ways
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as exc:
            raise SeleniumLoginUnavailable(
                "Google Chrome or a compatible ChromeDriver could not start"
            ) from exc
    try:
        driver.set_page_load_timeout(45)
    except Exception:  # noqa: BLE001 - best-effort Selenium timeout setting
        log.debug("Chrome does not support page load timeout configuration")
    return driver


def _visible(element) -> bool:
    try:
        return bool(element.is_displayed())
    except Exception:  # noqa: BLE001 - Selenium elements may disappear during a poll
        return False


def challenge_present(driver) -> bool:
    """Check actual challenge elements, not an arbitrary failed login."""
    from selenium.webdriver.common.by import By

    try:
        for xpath in CAPTCHA_XPATHS:
            if any(_visible(item) for item in driver.find_elements(By.XPATH, xpath)):
                return True
        for css in CAPTCHA_FRAMES:
            if any(_visible(item) for item in driver.find_elements(By.CSS_SELECTOR, css)):
                return True
    except Exception:  # noqa: BLE001 - Selenium elements may disappear during a poll
        return False
    return False


def _wait_challenge(driver, *, deadline: float, notify: Callable[[str], None],
                    cancelled: Callable[[], bool]) -> None:
    notify("captcha_required")
    while time.monotonic() < deadline:
        if cancelled():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        if not challenge_present(driver):
            notify("captcha_resolved")
            return
        time.sleep(1)
    raise SeleniumLoginUnavailable("The CAPTCHA was not solved before session expiry")


def _world_ready(driver, host: str) -> bool:
    from selenium.webdriver.common.by import By

    try:
        if (urlsplit(driver.current_url).hostname or "").casefold() != host:
            return False
        return any(_visible(e) for e in driver.find_elements(By.XPATH, CITY_BREAD_XPATH))
    except Exception:  # noqa: BLE001 - Selenium elements may disappear during a poll
        return False


def _await_world(driver, world_host: str, *, deadline: float,
                 headless: bool, notify: Callable[[str], None],
                 cancelled: Callable[[], bool]) -> None:
    from selenium.webdriver.common.by import By

    lobby_handle = driver.current_window_handle
    play_clicked = False
    while time.monotonic() < deadline:
        if cancelled():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        if challenge_present(driver):
            if headless:
                raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
            _wait_challenge(driver, deadline=deadline, notify=notify, cancelled=cancelled)
        for handle in list(driver.window_handles):
            try:
                driver.switch_to.window(handle)
            except Exception:  # noqa: BLE001 - a stale tab is not a valid session
                log.debug("Gameforge tab no longer exists")
                continue
            if _world_ready(driver, world_host):
                return
        try:
            driver.switch_to.window(lobby_handle)
            if driver.find_elements(By.XPATH, LOGIN_ERROR_XPATH):
                raise SeleniumLoginUnavailable("Gameforge rejected the saved credentials")
            buttons = driver.find_elements(By.XPATH, PLAY_BUTTON_XPATH)
            if buttons and not play_clicked:
                for item in driver.find_elements(
                    By.XPATH, "//button[contains(@class,'cookiebanner') "
                    "and (contains(., 'Принять') or contains(., 'Accept'))]"
                ):
                    if _visible(item):
                        item.click()
                buttons[0].click()
                play_clicked = True
        except SeleniumLoginUnavailable:
            raise
        except Exception:  # noqa: BLE001 - game may be navigating between tabs
            log.debug("Gameforge lobby is still navigating")
        time.sleep(0.7)
    raise SeleniumLoginUnavailable(
        "The exact selected game world did not open; no session was imported"
    )


def _restore_legacy_session(driver, saved: tuple[str, list[dict[str, object]]],
                            host: str, *, deadline: float) -> str | None:
    """Legacy warehouse bot behavior: restore cookies before full Selenium login."""
    url, cookies = saved
    if (urlsplit(url).scheme != "https"
            or (urlsplit(url).hostname or "").casefold() != host):
        return None
    try:
        driver.get("https://" + host + "/")
        injector = getattr(driver, "execute_cdp_cmd", None)
        if callable(injector):
            injector("Network.setCookies", {"cookies": cookies})
        else:
            for cookie in cookies:
                if cookie.get("domain") == host:
                    driver.add_cookie(cookie)
        driver.get(url)
        until = min(deadline, time.monotonic() + 12)
        while time.monotonic() < until:
            if _world_ready(driver, host):
                candidates = [
                    c for c in driver.get_cookies()
                    if c.get("name") == "ikariam"
                    and str(c.get("domain") or "").lstrip(".").casefold() == host
                    and c.get("secure") is True
                ]
                if len(candidates) == 1:
                    from daedalus.saved_session_recovery import _validated_world_cookie

                    return _validated_world_cookie(candidates[0].get("value"))
                return None
            time.sleep(0.5)
    except Exception:  # noqa: BLE001 - expired original tokens simply cause fresh login
        log.info("Previous warehouse session is no longer usable")
    return None


def _login_once(driver, credentials: GameforgeCredentials, world_host: str, *,
                headless: bool, deadline: float, notify: Callable[[str], None],
                cancelled: Callable[[], bool]) -> str:
    """Original warehouse bot's lobby -> login -> play -> game logic."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    notify("headless_login" if headless else "visible_captcha_login")
    try:
        if cancelled():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        driver.get(LOBBY_URL)
        if challenge_present(driver):
            if headless:
                raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
            _wait_challenge(driver, deadline=deadline, notify=notify, cancelled=cancelled)
        if not driver.find_elements(By.XPATH, PLAY_BUTTON_XPATH):
            tabs = driver.find_elements(By.XPATH, LOGIN_TAB_XPATH)
            if tabs and _visible(tabs[0]):
                tabs[0].click()
            wait = WebDriverWait(driver, max(1.0, min(12.0, deadline - time.monotonic())))
            email_field = wait.until(EC.element_to_be_clickable((By.NAME, "email")))
            password_field = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
            submit = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
            email_field.clear()
            email_field.send_keys(credentials.email)
            password_field.clear()
            password_field.send_keys(credentials.password)
            submit.click()
        _await_world(driver, world_host, deadline=deadline,
                     headless=headless, notify=notify, cancelled=cancelled)
        matches = [
            c for c in driver.get_cookies()
            if c.get("name") == "ikariam"
            and str(c.get("domain") or "").lstrip(".").casefold() == world_host
            and c.get("secure") is True
        ]
        if len(matches) != 1:
            raise SeleniumLoginUnavailable("The expected secure world cookie is missing")
        from daedalus.saved_session_recovery import _validated_world_cookie

        return _validated_world_cookie(matches[0].get("value"))
    except (ManualChallengeRequired, SeleniumLoginUnavailable):
        raise
    except Exception as exc:
        raise SeleniumLoginUnavailable(
            "Automatic login failed; check your saved credentials and Gameforge page"
        ) from exc


def login_world(
    credentials: GameforgeCredentials, world: str,
    *, driver_factory: Callable[[bool], object] = create_chrome,
    notify: Callable[[str], None] | None = None, timeout_seconds: float = 240,
    cancelled: Callable[[], bool] | None = None,
) -> str:
    """Headless first; visible login only on detected CAPTCHA, never on timeout."""
    if not WORLD.fullmatch(world):
        raise SeleniumLoginUnavailable("Invalid selected world")
    if not 30 <= timeout_seconds <= 540:
        raise ValueError("Login timeout must be between 30 and 540 seconds")
    report = notify or (lambda _stage: None)
    stop_requested = cancelled or (lambda: False)
    deadline = time.monotonic() + timeout_seconds
    host = f"{world.casefold()}.ikariam.gameforge.com"
    for headless in (True, False):
        if stop_requested():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        driver = None
        try:
            driver = driver_factory(headless)
            if headless:
                from daedalus.desktop.selenium_credentials import legacy_saved_session

                previous = legacy_saved_session(credentials.email, world)
                if previous and not stop_requested():
                    restored = _restore_legacy_session(
                        driver, previous, host, deadline=deadline
                    )
                    if restored is not None:
                        report("saved_session_restored")
                        return restored
            return _login_once(
                driver, credentials, host, headless=headless,
                deadline=deadline, notify=report, cancelled=stop_requested,
            )
        except ManualChallengeRequired:
            if not headless:
                raise SeleniumLoginUnavailable(
                    "The CAPTCHA was not completed in visible Chrome"
                ) from None
            report("opening_visible_captcha")
        except SeleniumLoginUnavailable:
            raise
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:  # noqa: BLE001 - driver may already have exited
                    log.warning("Selenium Chrome cleanup did not complete")
    raise SeleniumLoginUnavailable("Login session expired")
