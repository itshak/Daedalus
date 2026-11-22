"""Headless-first Selenium login, adapted from itshak/ikabot warehouse bot.

Uses the legacy lobby selectors and play-button workflow. Headless Chrome is
the default. A failed headless login gets one bounded visible Chrome retry,
where a human can solve CAPTCHA or correct credentials. Selenium never solves a challenge. Only the exact, secure world cookie is returned for
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
LOGIN_TAB_XPATH = "//div[@id='loginRegisterTabs']//li"
_SIGN_IN_LABELS = ("войти", "вход", "авторизация", "login", "log in",
                   "sign in", "anmelden", "se connecter", "iniciar sesión",
                   "acceder", "entrar")
_REGISTER_LABELS = ("регистрация", "зарегистр", "register", "sign up", "sign-up",
                    "create account", "создать аккаунт", "registrieren")
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
    """Visible user challenge detected; restart with windowed Chrome."""


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
    notify("waiting_for_world")
    while time.monotonic() < deadline:
        if cancelled():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        try:
            handles = list(driver.window_handles)
            # Once Play is pressed, follow the newest game tab only. The old
            # code switched *every* open tab on every 700-ms poll, repeatedly
            # pulling visible Chrome to the foreground on macOS.
            if play_clicked:
                handle = next((h for h in reversed(handles) if h != lobby_handle),
                              lobby_handle)
                if driver.current_window_handle != handle:
                    driver.switch_to.window(handle)
                if challenge_present(driver):
                    if headless:
                        raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
                    _wait_challenge(
                        driver, deadline=deadline, notify=notify, cancelled=cancelled,
                    )
                if _world_ready(driver, world_host):
                    notify("world_ready")
                    return
            else:
                # Before Play, inspect other open tabs once per new handle to
                # recognize an already active world, then return to the lobby.
                for handle in reversed(handles):
                    if handle == lobby_handle:
                        continue
                    if driver.current_window_handle != handle:
                        driver.switch_to.window(handle)
                    if challenge_present(driver):
                        if headless:
                            raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
                        _wait_challenge(
                            driver, deadline=deadline, notify=notify, cancelled=cancelled,
                        )
                    if _world_ready(driver, world_host):
                        notify("world_ready")
                        return
                    break
                if driver.current_window_handle != lobby_handle:
                    driver.switch_to.window(lobby_handle)
                if challenge_present(driver):
                    if headless:
                        raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
                    _wait_challenge(
                        driver, deadline=deadline, notify=notify, cancelled=cancelled,
                    )
                if _world_ready(driver, world_host):
                    notify("world_ready")
                    return
                if driver.find_elements(By.XPATH, LOGIN_ERROR_XPATH) and headless:
                    raise SeleniumLoginUnavailable("Gameforge rejected the saved credentials")
                buttons = driver.find_elements(By.XPATH, PLAY_BUTTON_XPATH)
                if buttons:
                    for item in driver.find_elements(
                        By.XPATH, "//button[contains(@class,'cookiebanner') "
                        "and (contains(., 'Принять') or contains(., 'Accept'))]"
                    ):
                        if _visible(item):
                            item.click()
                    buttons[0].click()
                    play_clicked = True
                    notify("play_clicked")
        except (SeleniumLoginUnavailable, ManualChallengeRequired):
            raise
        except Exception:  # noqa: BLE001 - game may be navigating between tabs
            log.debug("Gameforge browser is still navigating")
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


def _select_sign_in_tab(driver, notify: Callable[[str], None]) -> None:
    """Never use the first tab blindly: it can be Registration on Gameforge."""
    from selenium.webdriver.common.by import By

    tabs = driver.find_elements(By.XPATH, LOGIN_TAB_XPATH)
    if not tabs:
        # A direct login form on a newer Gameforge page needs no tab switch.
        return
    for tab in tabs:
        if not _visible(tab):
            continue
        # Some translations place the label in aria-label or title instead of
        # visible text. Do not infer sign-in from an unrecognized tab index.
        description = " ".join(
            str(value or "") for value in (
                tab.text, tab.get_attribute("aria-label"), tab.get_attribute("title")
            )
        ).casefold()
        if any(label in description for label in _REGISTER_LABELS):
            continue
        if any(label in description for label in _SIGN_IN_LABELS):
            tab.click()
            notify("sign_in_tab_selected")
            return
    notify("sign_in_tab_not_found")
    raise SeleniumLoginUnavailable(
        "Could not identify the Gameforge sign-in tab; use visible manual recovery"
    )


def _visible_sign_in_form(driver):
    """Choose *one* visible login form; never fill the registration panel."""
    from selenium.webdriver.common.by import By

    matching = []
    for form in driver.find_elements(By.CSS_SELECTOR, "form"):
        if not _visible(form):
            continue
        identity = " ".join(str(form.get_attribute(k) or "") for k in ("id", "class"))
        if any(label in identity.casefold() for label in ("register", "signup", "sign-up")):
            continue
        emails = [field for field in form.find_elements(By.CSS_SELECTOR, "input[name='email']")
                  if _visible(field)]
        passwords = [field for field in form.find_elements(
            By.CSS_SELECTOR, "input[name='password']"
        ) if _visible(field)]
        submits = [button for button in form.find_elements(
            By.CSS_SELECTOR, "button[type='submit'],input[type='submit']"
        ) if _visible(button) and button.is_enabled()]
        if len(emails) == len(passwords) == 1 and len(submits) == 1:
            matching.append((emails[0], passwords[0], submits[0]))
    return matching[0] if len(matching) == 1 else False


def _login_once(driver, credentials: GameforgeCredentials, world_host: str, *,
                headless: bool, deadline: float, notify: Callable[[str], None],
                cancelled: Callable[[], bool]) -> str:
    """Original warehouse bot's lobby -> login -> play -> game logic."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    notify("headless_login" if headless else "visible_captcha_login")
    try:
        if cancelled():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        notify("opening_lobby")
        driver.get(LOBBY_URL)
        notify("lobby_loaded")
        if challenge_present(driver):
            if headless:
                raise ManualChallengeRequired("Gameforge CAPTCHA needs human input")
            _wait_challenge(driver, deadline=deadline, notify=notify, cancelled=cancelled)
        if not driver.find_elements(By.XPATH, PLAY_BUTTON_XPATH):
            notify("waiting_for_login_form")
            _select_sign_in_tab(driver, notify)
            wait = WebDriverWait(driver, max(1.0, min(12.0, deadline - time.monotonic())))
            email_field, password_field, submit = wait.until(_visible_sign_in_form)
            email_field.clear()
            email_field.send_keys(credentials.email)
            password_field.clear()
            password_field.send_keys(credentials.password)
            submit.click()
            notify("login_submitted")
        else:
            notify("lobby_session_active")
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

        cookie = _validated_world_cookie(matches[0].get("value"))
        notify("world_cookie_ready")
        return cookie
    except (ManualChallengeRequired, SeleniumLoginUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - sanitize arbitrary WebDriver failures
        # WebDriver exceptions may embed cookies, URLs and DOM values.
        # Report a sanitized category rather than the exception itself.
        from selenium.common.exceptions import TimeoutException
        if isinstance(exc, TimeoutException):
            notify("login_form_timeout")
            raise SeleniumLoginUnavailable(
                "Gameforge login form did not become usable in time"
            ) from None
        notify("browser_navigation_error")
        raise SeleniumLoginUnavailable(
            "Chrome could not complete the Gameforge login page"
        ) from None


def login_world(
    credentials: GameforgeCredentials, world: str,
    *, driver_factory: Callable[[bool], object] = create_chrome,
    notify: Callable[[str], None] | None = None, timeout_seconds: float = 240,
    cancelled: Callable[[], bool] | None = None,
    visible_only: bool = False,
) -> str:
    """Try headless first; give failures a bounded visible-browser recovery.

    The headless deadline reserves time for the visible fallback if a page
    silently hangs. Only the exact world-host cookie can complete a login.
    """
    if not WORLD.fullmatch(world):
        raise SeleniumLoginUnavailable("Invalid selected world")
    if not 30 <= timeout_seconds <= 540:
        raise ValueError("Login timeout must be between 30 and 540 seconds")
    report = notify or (lambda _stage: None)
    stop_requested = cancelled or (lambda: False)
    deadline = time.monotonic() + timeout_seconds
    headless_deadline = min(
        deadline, time.monotonic() + max(15, min(90, timeout_seconds * 0.4))
    )
    host = f"{world.casefold()}.ikariam.gameforge.com"

    # A rejected server-side handoff must use a fresh, human-visible browser;
    # replaying the same locally restored cookie would repeat the rejection.
    for headless in ((False,) if visible_only else (True, False)):
        if stop_requested():
            raise SeleniumLoginUnavailable("Automatic login cancelled")
        if time.monotonic() >= deadline:
            raise SeleniumLoginUnavailable("Login timed out before browser recovery")
        driver = None
        report("starting_headless_browser" if headless else "opening_visible_browser")
        try:
            driver = driver_factory(headless)
            if headless:
                from daedalus.desktop.selenium_credentials import legacy_saved_session

                report("checking_saved_session")
                previous = legacy_saved_session(credentials.email, world)
                if previous and not stop_requested():
                    restored = _restore_legacy_session(
                        driver, previous, host, deadline=headless_deadline
                    )
                    if restored is not None:
                        report("saved_session_restored")
                        return restored
            try:
                return _login_once(
                    driver, credentials, host, headless=headless,
                    deadline=headless_deadline if headless else deadline,
                    notify=report, cancelled=stop_requested,
                )
            except ManualChallengeRequired:
                if not headless:
                    raise SeleniumLoginUnavailable(
                        "The CAPTCHA was not completed in visible Chrome"
                    ) from None
                report("headless_login_failed")
                report("opening_visible_captcha")
            except SeleniumLoginUnavailable:
                if headless:
                    report("headless_login_failed")
                    report("opening_visible_recovery")
                else:
                    if stop_requested():
                        raise SeleniumLoginUnavailable("Automatic login cancelled") from None
                    # Visible Chrome remains open so a human can correct a
                    # rejected password or changed login form and click Play.
                    report("manual_login_required")
                    _await_world(
                        driver, host, deadline=deadline, headless=False,
                        notify=report, cancelled=stop_requested,
                    )
                    matches = [
                        c for c in driver.get_cookies()
                        if c.get("name") == "ikariam"
                        and str(c.get("domain") or "").lstrip(".").casefold() == host
                        and c.get("secure") is True
                    ]
                    if len(matches) != 1:
                        raise SeleniumLoginUnavailable(
                            "The expected secure world cookie is missing"
                        ) from None
                    from daedalus.saved_session_recovery import _validated_world_cookie

                    cookie = _validated_world_cookie(matches[0].get("value"))
                    report("world_cookie_ready")
                    return cookie
        except SeleniumLoginUnavailable:
            if not headless:
                report("visible_login_failed")
                raise
            report("headless_login_failed")
            report("opening_visible_recovery")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:  # noqa: BLE001 - driver may already have exited
                    log.warning("Selenium Chrome cleanup did not complete")
    raise SeleniumLoginUnavailable("Login session expired")
