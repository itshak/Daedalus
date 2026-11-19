"""Offline contracts for the *copied* IkaBot headless Selenium login behavior.

Every browser and Keychain is fake; no Chrome, Gameforge, real credentials,
network or authorized backend is contacted by this test module.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("selenium")

import daedalus.desktop.selenium_automation as automation
from daedalus.desktop.selenium_credentials import (
    GameforgeCredentialError,
    GameforgeCredentials,
    GameforgeKeychain,
)

WORLD = "s301-en"
HOST = "s301-en.ikariam.gameforge.com"
URL = "https://" + HOST + "/?view=city&cityId=100"
CREDS = GameforgeCredentials("sample@example.test", "only-fixture-password")


class FakeKeyring:
    def __init__(self):
        self.saved = {}
    def get_password(self, service, key):
        return self.saved.get((service, key))
    def set_password(self, service, key, value):
        self.saved[(service, key)] = value
    def delete_password(self, service, key):
        del self.saved[(service, key)]


def fake_cookies(domain=HOST, value="A" * 48):
    return [{"name": "ikariam", "value": value, "path": "/",
             "domain": domain, "secure": True, "httpOnly": True}]


class FakeDriver:
    def __init__(self, headless, url=URL, cookie_domain=HOST):
        self.headless = headless
        self.current_url = url
        self._cookies = fake_cookies(cookie_domain)
    def get_cookies(self):
        return self._cookies


def _run(monkeypatch, *, restore=False, captcha=False, failed=False,
         cached=None, url=URL, cookie_domain=HOST):
    modes = []
    closed = []
    humanization = []
    messages = []

    def factory(name, headless):
        assert name == "chrome"
        modes.append(headless)
        return FakeDriver(headless, url, cookie_domain)

    class StubFlow:
        def __init__(self, driver, settings, *, headless, cancelled, progress):
            assert settings.password == CREDS.password
            self.headless = headless
            humanization.append(not headless)
        def try_restore(self, url, cookies, player):
            assert player == "ExamplePlayer"
            return restore
        def log_in(self, email, username, password=None):
            assert email == CREDS.email
            assert password == CREDS.password
            if captcha and self.headless:
                raise automation.CaptchaRequired("challenge")
            return not failed

    monkeypatch.setattr(automation, "DaedalusLoginFlow", StubFlow)
    try:
        result = automation.login_headless_first(
            credentials=CREDS, world=WORLD, player="ExamplePlayer",
            cached_session=cached,
            progress=messages.append, driver_factory=factory,
            driver_cleanup=closed.append,
            attempts=2,
        )
        return result, modes, closed, humanization, messages
    except Exception:
        assert len(closed) == len(modes)
        raise


def test_saved_session_restore_attempted_first_without_visible_chrome(monkeypatch):
    result, modes, closed, humanization, messages = _run(
        monkeypatch, restore=True, cached={"url": URL, "cookies": fake_cookies()},
    )
    assert result.cookie == "A" * 48
    assert result.manual_captcha is False
    assert modes == [True]
    assert humanization == [False]  # upstream: no mouse simulation in headless
    assert len(closed) == 1
    assert "Restoring saved session" in messages


def test_headless_login_without_captcha_does_not_show_browser(monkeypatch):
    result, modes, closed, humanization, _ = _run(monkeypatch)
    assert result.manual_captcha is False
    assert modes == [True]
    assert humanization == [False]
    assert len(closed) == 1


def test_only_real_captcha_escalates_to_original_visible_humanized_flow(monkeypatch):
    result, modes, closed, humanization, messages = _run(monkeypatch, captcha=True)
    assert result.manual_captcha is True
    assert modes == [True, False]
    assert humanization == [False, True]
    assert len(closed) == 2
    assert any("CAPTCHA" in status for status in messages)


def test_failed_login_without_captcha_never_shows_browser(monkeypatch):
    with pytest.raises(automation.SeleniumLoginError, match="no CAPTCHA was detected"):
        _run(monkeypatch, failed=True)


@pytest.mark.parametrize(("url", "domain"), [
    ("https://s302-en.ikariam.gameforge.com/?view=city", HOST),
    ("https://lobby.ikariam.gameforge.com/", HOST),
    ("http://" + HOST + "/", HOST),
    (URL, "s302-en.ikariam.gameforge.com"),
])
def test_wrong_world_or_cookie_never_handed_off(monkeypatch, url, domain):
    with pytest.raises(automation.SeleniumLoginError, match="world|session"):
        _run(monkeypatch, url=url, cookie_domain=domain)


def test_keychain_saved_login_and_session_is_account_and_backend_scoped():
    memory = FakeKeyring()
    first = GameforgeKeychain(
        "https://example.test", "alpha", WORLD, "ExamplePlayer", provider=memory,
    )
    first.save_credentials(CREDS)
    first.save_session(URL, fake_cookies())
    assert first.get_credentials() == CREDS
    assert first.get_session()["url"] == URL
    assert all("example.test" not in key for _service, key in memory.saved)
    assert not any("password" in key for _service, key in memory.saved)
    # Stored values are only in the injected Keychain, not a plaintext file.
    assert any(CREDS.password in value for value in memory.saved.values())
    for changed in [
        ("https://other.test", "alpha", WORLD, "ExamplePlayer"),
        ("https://example.test", "beta", WORLD, "ExamplePlayer"),
        ("https://example.test", "alpha", "s302-en", "ExamplePlayer"),
        ("https://example.test", "alpha", WORLD, "SomeoneElse"),
    ]:
        other = GameforgeKeychain(*changed, provider=memory)
        assert other.get_credentials() is None
        assert other.get_session() is None
    first.forget_all()
    assert memory.saved == {}


def test_keychain_refuses_session_redirects_and_unrelated_cookies():
    memory = FakeKeyring()
    store = GameforgeKeychain(
        "https://example.test", "alpha", WORLD, "ExamplePlayer", provider=memory,
    )
    with pytest.raises(GameforgeCredentialError):
        store.save_session("https://evil.test/", fake_cookies())
    with pytest.raises(GameforgeCredentialError):
        store.save_session(URL, fake_cookies("evil.test"))
    with pytest.raises(GameforgeCredentialError):
        store.save_session(URL, fake_cookies(value="X" * 5000))
    assert memory.saved == {}


def test_source_preserving_login_settings_are_in_memory_only():
    from daedalus.desktop.legacy_selenium.settings import Settings
    settings = Settings(password="do-not-log")
    assert settings.password == "do-not-log"
    assert "do-not-log" not in repr(settings)
    assert not hasattr(settings, "config_path")


def test_progress_never_contains_user_password(monkeypatch):
    result, _, _, _, messages = _run(monkeypatch, captcha=True)
    assert result.email == CREDS.email
    assert CREDS.password not in json.dumps(messages)


def test_unsafe_origin_blocks_typing_even_with_valid_credentials():
    from daedalus.desktop.legacy_selenium.settings import Settings

    class StubDriver:
        current_url = "https://gameforge.com.attacker.example/signin"

    flow = automation.DaedalusLoginFlow(
        StubDriver(), Settings(password="not-a-secret"),
        headless=True, cancelled=lambda: False, progress=lambda _: None,
    )
    with pytest.raises(automation.SeleniumLoginError, match="changed origin"):
        flow._type(object(), "credentials")
