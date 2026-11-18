"""Offline browser-handoff tests; no live Gameforge navigation or credentials."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.browser_recovery import PlaywrightHumanBrowser, recover_with_human_browser
from daedalus.saved_session_recovery import SavedSessionUnavailable, bind_saved_email


class Keys:
    def __init__(self):
        self.data = {}

    def set_password(self, service, user, value):
        self.data[(service, user)] = value

    def get_password(self, service, user):
        return self.data.get((service, user))


class Browser:
    def __init__(self, cookie="A" * 48):
        self.cookie = cookie
        self.events = []

    def open(self, lobby, world):
        self.events.append(("open", lobby, world))

    def world_cookie(self, host):
        self.events.append(("cookie", host))
        return self.cookie

    def close(self):
        self.events.append(("close",))


@pytest.fixture
def ctx(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    coordinator = AccountSessionCoordinator([account], state_dir=tmp_path / "leases")
    keys = Keys()
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    return account, coordinator, keys


def _session(player="ExamplePlayer"):
    return SimpleNamespace(logged=True, mundo="301", servidor="en", username=player,
                           s=SimpleNamespace(close=lambda: None))


def test_browser_handoff_is_verified_under_one_lease(ctx):
    account, owner, keys = ctx
    browser = Browser()
    seen = []

    def confirm():
        assert owner.status(account.id) != "not_connected"
        seen.append("human")
        return True

    def verify(a, email, cookie):
        assert owner.status(account.id) != "not_connected"
        assert email == "synthetic@example.invalid" and cookie == "A" * 48
        seen.append("engine")
        return _session()

    result = recover_with_human_browser(
        account, owner, confirmed=True, human_confirm=confirm, browser=browser,
        credential_store=keys, restore=verify,
    )
    assert result == {"account_id": "alpha", "status": "world_cookie_bound"}
    assert seen == ["human", "engine"]
    assert browser.events == [
        ("open", "https://lobby.ikariam.gameforge.com/",
         "https://s301-en.ikariam.gameforge.com/"),
        ("cookie", "s301-en.ikariam.gameforge.com"), ("close",),
    ]
    assert owner.status(account.id) == "not_connected"
    assert "A" * 48 not in str(result)


def test_browser_recovery_denies_unconfirmed_and_busy(ctx):
    account, owner, keys = ctx
    browser = Browser()
    kwargs = {"human_confirm": lambda: True, "browser": browser,
              "credential_store": keys, "restore": lambda *_: _session()}
    with pytest.raises(SavedSessionUnavailable, match="consent"):
        recover_with_human_browser(account, owner, confirmed=False, **kwargs)
    with owner.acquire(account.id), pytest.raises(SavedSessionUnavailable, match="owns"):
        recover_with_human_browser(account, owner, confirmed=True, **kwargs)
    assert browser.events == []


@pytest.mark.parametrize("cookie,player,confirm", [
    (None, "ExamplePlayer", True),
    ("B" * 48, "OtherPlayer", True),
    ("B" * 48, "ExamplePlayer", False),
])
def test_browser_recovery_failure_closes_and_never_stores(ctx, cookie, player, confirm):
    account, owner, keys = ctx
    before = dict(keys.data)
    browser = Browser(cookie)
    with pytest.raises(SavedSessionUnavailable):
        recover_with_human_browser(
            account, owner, confirmed=True, human_confirm=lambda: confirm,
            browser=browser, credential_store=keys,
            restore=lambda *_: _session(player),
        )
    assert browser.events[-1] == ("close",)
    assert keys.data == before
    assert owner.status(account.id) == "not_connected"


def test_playwright_adapter_accepts_only_exact_secure_world_cookie():
    class FakeContext:
        def cookies(self, urls):
            assert urls == ["https://s301-en.ikariam.gameforge.com/"]
            return [
                {"name": "ikariam", "domain": "s302-en.ikariam.gameforge.com",
                 "secure": True, "value": "X" * 48},
                {"name": "ikariam", "domain": "s301-en.ikariam.gameforge.com",
                 "secure": False, "value": "Y" * 48},
                {"name": "ikariam", "domain": "s301-en.ikariam.gameforge.com",
                 "secure": True, "value": "Z" * 48},
            ]

    adapter = PlaywrightHumanBrowser()
    adapter._context = FakeContext()
    assert adapter.world_cookie("s301-en.ikariam.gameforge.com") == "Z" * 48
