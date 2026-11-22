"""Offline-only parity tests for the old IkaBot warehouse bot's Selenium login.

Never opens a real browser or contacts Gameforge, Daedalus API, or keyrings.
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from daedalus.desktop import selenium_auth as auth
from daedalus.desktop.selenium_credentials import (
    get_saved_login,
    legacy_warehouse_login,
    remember_login,
)


class FakeChrome:
    def __init__(self) -> None:
        self.closed = False

    def quit(self) -> None:
        self.closed = True


def _creds() -> auth.GameforgeCredentials:
    return auth.GameforgeCredentials("synthetic@example.invalid", "not-a-real-password")


def test_headless_login_succeeds_without_visible_browser(monkeypatch):
    modes = []
    browsers = []

    def factory(headless):
        modes.append(headless)
        driver = FakeChrome()
        browsers.append(driver)
        return driver

    monkeypatch.setattr(auth, "_login_once", lambda _driver, *_args, **_kw: "fake-cookie")
    assert auth.login_world(_creds(), "s53-ru", driver_factory=factory) == "fake-cookie"
    assert modes == [True]
    assert all(browser.closed for browser in browsers)


def test_visible_chrome_retries_captcha_failure(monkeypatch):
    modes = []
    stages = []

    def attempt(_driver, _credentials, _world, *, headless, **_kw):
        if headless:
            raise auth.ManualChallengeRequired("CAPTCHA")
        return "manual-result"

    monkeypatch.setattr(auth, "_login_once", attempt)
    assert auth.login_world(
        _creds(), "s53-ru",
        driver_factory=lambda headless: (modes.append(headless) or FakeChrome()),
        notify=stages.append,
    ) == "manual-result"
    assert modes == [True, False]
    assert stages == [
        "starting_headless_browser", "checking_saved_session",
        "headless_login_failed", "opening_visible_captcha",
        "opening_visible_browser",
    ]


def test_wrong_password_opens_visible_chrome_for_manual_correction(monkeypatch):
    modes, stages = [], []

    def attempt(*_args, **_kwargs):
        raise auth.SeleniumLoginUnavailable("Gameforge rejected credentials")

    monkeypatch.setattr(auth, "_login_once", attempt)
    monkeypatch.setattr(auth, "_await_world", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(auth.SeleniumLoginUnavailable(
            "Manual login not completed"
        ))
    ))
    with pytest.raises(auth.SeleniumLoginUnavailable, match="Manual login not completed"):
        auth.login_world(
            _creds(), "s53-ru",
            driver_factory=lambda headless: (
                modes.append(headless) or FakeChrome()
            ), notify=stages.append,
        )
    assert modes == [True, False]
    assert "opening_visible_recovery" in stages
    assert "manual_login_required" in stages


def test_non_captcha_failure_recovers_with_visible_browser(monkeypatch):
    modes, stages, browsers = [], [], []

    def attempt(_driver, _credentials, _host, *, headless, **_kwargs):
        if headless:
            raise auth.SeleniumLoginUnavailable("Headless page did not load")
        return "synthetic-visible-session"

    def factory(headless):
        modes.append(headless)
        chrome = FakeChrome()
        browsers.append(chrome)
        return chrome

    monkeypatch.setattr(auth, "_login_once", attempt)
    result = auth.login_world(
        _creds(), "s53-ru", driver_factory=factory, notify=stages.append,
    )
    assert result == "synthetic-visible-session"
    assert modes == [True, False]
    assert "headless_login_failed" in stages
    assert "opening_visible_recovery" in stages
    assert all(browser.closed for browser in browsers)


def test_visible_browser_can_complete_manual_corrected_login(monkeypatch):
    modes, stages = [], []

    class ManualBrowser(FakeChrome):
        def get_cookies(self):
            return [{
                "name": "ikariam", "domain": "s53-ru.ikariam.gameforge.com",
                "secure": True, "value": "x" * 48,
            }]

    def attempt(*_args, **_kwargs):
        raise auth.SeleniumLoginUnavailable("Login form needs manual correction")

    monkeypatch.setattr(auth, "_login_once", attempt)
    monkeypatch.setattr(auth, "_await_world", lambda *_args, **_kwargs: None)
    result = auth.login_world(
        _creds(), "s53-ru",
        driver_factory=lambda headless: (
            modes.append(headless) or ManualBrowser()
        ), notify=stages.append,
    )
    assert result == "x" * 48
    assert modes == [True, False]
    assert "manual_login_required" in stages
    assert "world_cookie_ready" in stages


def test_invalid_world_fails_before_driver_start():
    with pytest.raises(auth.SeleniumLoginUnavailable, match="world"):
        auth.login_world(_creds(), "evil.example.com", driver_factory=lambda _: 1)


def test_cancelled_login_does_not_start_a_browser():
    modes = []
    with pytest.raises(auth.SeleniumLoginUnavailable, match="cancelled"):
        auth.login_world(
            _creds(), "s53-ru",
            driver_factory=lambda headless: (modes.append(headless) or FakeChrome()),
            cancelled=lambda: True,
        )
    assert modes == []


def test_captcha_requires_actual_visible_element(monkeypatch):
    pytest.importorskip("selenium")
    from selenium.webdriver.common.by import By

    class FakeElement:
        def __init__(self, shown):
            self.shown = shown

        def is_displayed(self):
            return self.shown

    class Browser:
        def __init__(self, displayed):
            self.displayed = displayed

        def find_elements(self, by, query):
            if by == By.XPATH and "Подтвердите" in query:
                return [FakeElement(self.displayed)]
            return []

    assert auth.challenge_present(Browser(True)) is True
    assert auth.challenge_present(Browser(False)) is False


def test_saved_keychain_login_is_exact_backend_and_account_scoped(monkeypatch):
    records = {}

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(
        get_password=lambda service, name: records.get((service, name)),
        set_password=lambda service, name, password: records.__setitem__(
            (service, name), password
        ),
        delete_password=lambda service, name: records.pop((service, name), None),
    ))
    url = "https://daedalus.example"
    creds = _creds()
    remember_login(url, "account-a", "s53-ru", creds)
    assert get_saved_login(url, "account-a", "s53-ru") == creds
    assert get_saved_login(url, "account-b", "s53-ru") is None
    assert get_saved_login(url, "account-a", "s54-ru") is None
    assert get_saved_login("https://other.example", "account-a", "s53-ru") is None
    assert "not-a-real-password" not in repr(creds)
    assert len(records) == 1


def test_legacy_bot_credentials_match_account_alias_without_guessing(tmp_path: Path):
    path = tmp_path / "config.ini"
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser["IKARIAM_LOGIN"] = {"PASSWORD": "legacy-default", "SERVER": "s53-ru"}
    parser["ACCOUNTS"] = {
        "Xiaomi": "xm@example.invalid",
        "DifferentPlayer": "other@example.invalid:other-secret",
    }
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)
    path.chmod(0o600)
    record = {"id": "alpha", "world": "s53-ru", "player": "Xiaomi"}
    assert legacy_warehouse_login(record, path=path) == auth.GameforgeCredentials(
        "xm@example.invalid", "legacy-default"
    )
    assert legacy_warehouse_login({**record, "player": "unknown"}, path=path) is None
    assert legacy_warehouse_login({**record, "world": "s54-ru"}, path=path) is None


def test_legacy_symlink_is_never_followed(tmp_path: Path):
    target = tmp_path / "actual.ini"
    target.write_text("[ACCOUNTS]\nXiaomi = x@e.invalid:password\n")
    alias = tmp_path / "config.ini"
    alias.symlink_to(target)
    assert legacy_warehouse_login({"id": "x", "player": "Xiaomi"}, path=alias) is None


def test_legacy_token_store_is_read_only_and_exact_world_scoped(tmp_path: Path):
    import json

    from daedalus.desktop.selenium_credentials import legacy_saved_session

    target = tmp_path / "tokens.json"
    target.write_text(json.dumps({
        "synthetic@example.invalid": {
            "url": "https://s53-ru.ikariam.gameforge.com/?view=city",
            "cookies": [
                {"name": "ikariam", "value": "x" * 48,
                 "domain": "s53-ru.ikariam.gameforge.com", "secure": True},
                {"name": "some_lobby", "value": "a" * 10,
                 "domain": "lobby.ikariam.gameforge.com", "secure": True},
                {"name": "other_account", "value": "bad",
                 "domain": "s54-ru.ikariam.gameforge.com", "secure": True},
            ],
        },
    }), encoding="utf-8")
    target.chmod(0o600)
    before = target.read_bytes()
    saved = legacy_saved_session(
        "synthetic@example.invalid", "s53-ru", path=target
    )
    assert saved is not None
    assert saved[0].startswith("https://s53-ru.")
    assert len(saved[1]) == 2
    assert legacy_saved_session(
        "synthetic@example.invalid", "s54-ru", path=target
    ) is None
    assert target.read_bytes() == before


def test_prior_warehouse_session_is_restored_without_password_or_visible_chrome(monkeypatch):
    from daedalus.desktop import selenium_credentials as source

    class FakeChromeWithCookies(FakeChrome):
        current_url = "https://s53-ru.ikariam.gameforge.com/?view=city"

        def get(self, url):
            self.current_url = url

        def execute_cdp_cmd(self, name, payload):
            assert name == "Network.setCookies"
            assert len(payload["cookies"]) == 1

        def get_cookies(self):
            return [{
                "name": "ikariam", "value": "x" * 48,
                "domain": "s53-ru.ikariam.gameforge.com", "secure": True,
            }]

    monkeypatch.setattr(source, "legacy_saved_session",
                        lambda *_args: (
                            "https://s53-ru.ikariam.gameforge.com/?view=city",
                            [{"name": "ikariam", "value": "x" * 48,
                              "domain": "s53-ru.ikariam.gameforge.com", "secure": True}],
                        ))
    monkeypatch.setattr(auth, "_world_ready", lambda *_args: True)
    monkeypatch.setattr(
        auth, "_login_once",
        lambda *_args, **_kw: pytest.fail(
            "Should never re-enter credentials when original session restores"
        ),
    )
    modes = []
    assert auth.login_world(
        _creds(), "s53-ru",
        driver_factory=lambda headless: (
            modes.append(headless) or FakeChromeWithCookies()
        ),
    ) == "x" * 48
    assert modes == [True]



def test_secondary_game_tab_captcha_is_detected_before_timeout(monkeypatch):
    """Gameforge can challenge the new game tab rather than the lobby."""
    # Lean core/development environments do not install desktop Selenium.
    # The fixture runs with the daedalus[desktop] dependencies.
    pytest.importorskip("selenium")
    import time

    class Tabs:
        def __init__(self, driver):
            self.driver = driver

        def window(self, handle):
            self.driver.current_window_handle = handle

    class Driver:
        def __init__(self):
            self.window_handles = ["lobby", "game"]
            self.current_window_handle = "lobby"
            self.switch_to = Tabs(self)

        def find_elements(self, *_args):
            return []

    browser = Driver()
    monkeypatch.setattr(
        auth, "challenge_present",
        lambda driver: driver.current_window_handle == "game",
    )
    monkeypatch.setattr(auth, "_world_ready", lambda *_args: False)
    with pytest.raises(auth.ManualChallengeRequired, match="CAPTCHA"):
        auth._await_world(
            browser, "s53-ru.ikariam.gameforge.com",
            deadline=time.monotonic() + 3,
            headless=True, notify=lambda _event: None,
            cancelled=lambda: False,
        )

def test_visible_only_recovery_never_replays_saved_headless_session(monkeypatch):
    """A fresh ticket and interactive Chrome, not the rejected legacy cookie."""
    from daedalus.desktop import selenium_auth as auth
    from daedalus.desktop import selenium_credentials

    modes, stages = [], []
    monkeypatch.setattr(
        selenium_credentials, "legacy_saved_session",
        lambda *_args: pytest.fail("rejected saved cookie must never be replayed"),
    )

    def login_once(_driver, _credentials, _host, *, headless, **_kwargs):
        assert headless is False
        return "synthetic-visible-cookie"

    monkeypatch.setattr(auth, "_login_once", login_once)
    result = auth.login_world(
        _creds(), "s53-ru", visible_only=True,
        driver_factory=lambda headless: (modes.append(headless) or FakeChrome()),
        notify=stages.append,
    )
    assert result == "synthetic-visible-cookie"
    assert modes == [False]
    assert stages[0] == "opening_visible_browser"
    assert "checking_saved_session" not in stages

def test_sign_in_tab_is_selected_by_semantics_not_registration_index():
    pytest.importorskip("selenium")

    class Tab:
        def __init__(self, label):
            self.text = label
            self.clicked = False

        def is_displayed(self):
            return True

        def get_attribute(self, _name):
            return None

        def click(self):
            self.clicked = True

    register = Tab("Регистрация")
    login = Tab("Вход")

    class Browser:
        def find_elements(self, _by, selector):
            assert selector == auth.LOGIN_TAB_XPATH
            return [register, login]

    events = []
    auth._select_sign_in_tab(Browser(), events.append)
    assert login.clicked is True
    assert register.clicked is False
    assert events == ["sign_in_tab_selected"]


def test_unknown_sign_in_tab_does_not_type_into_registration():
    pytest.importorskip("selenium")

    class UnknownTab:
        text = "Create your new account"

        def is_displayed(self):
            return True

        def get_attribute(self, _name):
            return None

        def click(self):
            pytest.fail("Never click an unrecognized or registration tab")

    class Browser:
        def find_elements(self, *_args):
            return [UnknownTab()]

    stages = []
    with pytest.raises(auth.SeleniumLoginUnavailable, match="sign-in tab"):
        auth._select_sign_in_tab(Browser(), stages.append)
    assert stages == ["sign_in_tab_not_found"]


def test_only_visible_sign_in_form_can_receive_credentials():
    pytest.importorskip("selenium")

    class Input:
        def is_displayed(self):
            return True

        def is_enabled(self):
            return True

    class Form:
        def __init__(self, identity):
            self.identity = identity
            self.email, self.password, self.submit = Input(), Input(), Input()

        def is_displayed(self):
            return True

        def get_attribute(self, name):
            return self.identity if name == "id" else ""

        def find_elements(self, _by, selector):
            return {
                "input[name='email']": [self.email],
                "input[name='password']": [self.password],
                "button[type='submit'],input[type='submit']": [self.submit],
            }.get(selector, [])

    register = Form("registerForm")
    login = Form("loginForm")

    class Browser:
        def find_elements(self, _by, selector):
            assert selector == "form"
            return [register, login]

    assert auth._visible_sign_in_form(Browser()) == (
        login.email, login.password, login.submit,
    )


def test_visible_chrome_does_not_switch_tabs_on_every_poll(monkeypatch):
    pytest.importorskip("selenium")

    class Play:
        def __init__(self, browser):
            self.browser = browser

        def click(self):
            self.browser.played = True
            self.browser.window_handles = ["lobby", "game"]

    class TabControl:
        def __init__(self, browser):
            self.browser = browser

        def window(self, handle):
            self.browser.switches.append(handle)
            self.browser.current_window_handle = handle

    class Browser:
        def __init__(self):
            self.current_window_handle = "lobby"
            self.window_handles = ["lobby"]
            self.switches = []
            self.played = False
            self.switch_to = TabControl(self)
            self.play = Play(self)

        def find_elements(self, _by, selector):
            return [self.play] if selector == auth.PLAY_BUTTON_XPATH and not self.played else []

    browser = Browser()
    polled = []
    monkeypatch.setattr(auth, "challenge_present", lambda *_args: False)

    def world_ready(driver, *_args):
        if driver.current_window_handle == "game":
            polled.append("game")
            return len(polled) >= 5
        return False

    monkeypatch.setattr(auth, "_world_ready", world_ready)
    monkeypatch.setattr(auth.time, "sleep", lambda *_args: None)
    auth._await_world(
        browser, "s53-ru.ikariam.gameforge.com",
        deadline=auth.time.monotonic() + 3,
        headless=False, notify=lambda *_args: None, cancelled=lambda: False,
    )
    assert browser.switches == ["game"]
    assert len(polled) == 5

def test_ephemeral_chromium_profile_uses_mock_keychain_only_on_mac(monkeypatch):
    """Chrome Safe Storage must not prompt or read the user's normal profile."""
    pytest.importorskip("selenium")
    import os
    from types import SimpleNamespace
    from selenium import webdriver
    from selenium.webdriver.chrome import options as chrome_options

    class Options:
        def __init__(self):
            self.arguments = []

        def add_argument(self, value):
            self.arguments.append(value)

    class Browser:
        def __init__(self, options):
            self.args = options.arguments
            self.closed = False

        def set_page_load_timeout(self, timeout):
            assert timeout == 45

        def quit(self):
            self.closed = True

    monkeypatch.setattr(chrome_options, "Options", Options)
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "undetected_chromedriver", SimpleNamespace(
        ChromeOptions=Options,
        Chrome=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic uc failure")),
    ))
    monkeypatch.setattr(webdriver, "Chrome", lambda *, options: Browser(options))
    driver = auth.create_chrome(headless=True)
    profile = driver._daedalus_temporary_profile
    try:
        assert "--headless=new" in driver.args
        assert "--use-mock-keychain" in driver.args
        assert "--password-store=basic" in driver.args
        assert f"--user-data-dir={profile}" in driver.args
        assert os.path.isdir(profile)
    finally:
        auth._dispose_chrome(driver)
    assert driver.closed
    assert not os.path.exists(profile)
