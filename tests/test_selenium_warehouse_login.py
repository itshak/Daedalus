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


def test_visible_chrome_only_for_detected_captcha(monkeypatch):
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
    assert stages == ["opening_visible_captcha"]


def test_wrong_password_does_not_open_visible_chrome(monkeypatch):
    modes = []

    def attempt(*_args, **_kwargs):
        raise auth.SeleniumLoginUnavailable("Gameforge rejected credentials")

    monkeypatch.setattr(auth, "_login_once", attempt)
    with pytest.raises(auth.SeleniumLoginUnavailable, match="rejected"):
        auth.login_world(_creds(), "s53-ru",
                         driver_factory=lambda headless: (
                             modes.append(headless) or FakeChrome()
                         ))
    assert modes == [True]


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
