"""Secret-free, opt-in cookie restore probe with synthetic IkaBot sessions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.saved_session_recovery import (
    SavedSessionUnavailable,
    bind_saved_email,
    probe_saved_cookies,
    unbind_saved_email,
)


class FakeKeyring:
    def __init__(self):
        self.entries = {}

    def get_password(self, service, username):
        return self.entries.get((service, username))

    def set_password(self, service, username, password):
        self.entries[(service, username)] = password

    def delete_password(self, service, username):
        del self.entries[(service, username)]


@pytest.fixture
def setup(tmp_path):
    accounts = [Account("alpha", "s301-en", "ExamplePlayer", "First", True)]
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "leases")
    keys = FakeKeyring()
    return accounts[0], owner, keys


def _session(*, logged=True, player="ExamplePlayer", world="301", server="en"):
    connection = SimpleNamespace(closed=False)

    def close():
        connection.closed = True

    connection.close = close
    return SimpleNamespace(
        logged=logged, username=player, mundo=world, servidor=server,
        s=connection,
    )


def test_email_is_only_stored_in_os_keyring_not_account_config(setup):
    account, _owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    assert len(keys.entries) == 1
    assert next(iter(keys.entries.values())) == "synthetic@example.invalid"
    assert "synthetic@example.invalid" not in str(account.to_dict())
    assert "synthetic@example.invalid" not in str(next(iter(keys.entries.keys())))
    unbind_saved_email(account, credential_store=keys)
    assert keys.entries == {}


@pytest.mark.parametrize("email", ["", "no-at-sign", "user@example", "a\n@example.invalid"])
def test_invalid_email_never_reaches_keyring(setup, email):
    account, _owner, keys = setup
    with pytest.raises(SavedSessionUnavailable):
        bind_saved_email(account, email, credential_store=keys)
    assert keys.entries == {}


def test_cookie_probe_requires_confirmation_lease_and_exact_identity(setup):
    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    calls = []
    session = _session()

    def restore(a, email):
        calls.append((a.id, email))
        return session

    with pytest.raises(SavedSessionUnavailable, match="confirmation"):
        probe_saved_cookies(
            account, owner, confirmed=False, credential_store=keys, restore=restore,
        )
    assert calls == []
    with owner.acquire(account.id), pytest.raises(SavedSessionUnavailable, match="owns"):
        probe_saved_cookies(
            account, owner, confirmed=True, credential_store=keys, restore=restore,
        )
    assert calls == []
    result = probe_saved_cookies(
        account, owner, confirmed=True, credential_store=keys, restore=restore,
    )
    assert result == {"account_id": "alpha", "status": "saved_session_valid"}
    assert session.s.closed
    assert owner.status(account.id) == "not_connected"
    assert calls == [("alpha", "synthetic@example.invalid")]


@pytest.mark.parametrize("override", [
    {"logged": False},
    {"username": "DifferentAccount"},
    {"mundo": "302"},
    {"servidor": "de"},
])
def test_bad_restored_identity_fails_closed_and_closes_session(setup, override):
    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    session = _session()
    for key, value in override.items():
        setattr(session, key, value)
    with pytest.raises(SavedSessionUnavailable, match="did not verify"):
        probe_saved_cookies(
            account, owner, confirmed=True, credential_store=keys,
            restore=lambda *_: session,
        )
    assert session.s.closed
    assert owner.status(account.id) == "not_connected"


def test_restorer_error_is_sanitized_and_lease_is_released(setup):
    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    secret = "DO-NOT-LEAK-THIS-PRIVATE-COOKIE"

    def fails(*_):
        raise RuntimeError(secret)

    with pytest.raises(SavedSessionUnavailable) as error:
        probe_saved_cookies(
            account, owner, confirmed=True, credential_store=keys, restore=fails,
        )
    assert secret not in str(error.value)
    assert owner.status(account.id) == "not_connected"


def test_missing_keyring_binding_never_calls_game_network(setup):
    account, owner, keys = setup
    with pytest.raises(SavedSessionUnavailable, match="Bind"):
        probe_saved_cookies(
            account, owner, confirmed=True, credential_store=keys,
            restore=lambda *_: pytest.fail("Should not call the network"),
        )


def test_changed_identity_does_not_reuse_keyring_mapping(setup):
    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    changed = Account("alpha", "s302-en", "ExamplePlayer", "First", True)
    with pytest.raises(SavedSessionUnavailable, match="identity"):
        probe_saved_cookies(
            changed, owner, confirmed=True, credential_store=keys,
            restore=lambda *_: pytest.fail("Should not call the network"),
        )


def test_ambiguous_named_world_requires_canonical_world(setup):
    _account, _owner, keys = setup
    named = Account("beta", "AlphaWorld", "ExamplePlayer", "Named", True)
    coordinator = AccountSessionCoordinator([named])
    bind_saved_email(named, "synthetic@example.invalid", credential_store=keys)
    with pytest.raises(SavedSessionUnavailable, match="canonical"):
        probe_saved_cookies(
            named, coordinator, confirmed=True, credential_store=keys,
            restore=lambda *_: pytest.fail("Should not call the network"),
        )


def test_default_restore_uses_cookie_only_engine_api(monkeypatch):
    import sys

    from daedalus.saved_session_recovery import _real_restore

    seen = []

    class FakeEngineSession:
        @staticmethod
        def from_saved(**kwargs):
            seen.append(kwargs)
            return object()

    monkeypatch.setitem(sys.modules, "ikabot.web.session", SimpleNamespace(Session=FakeEngineSession))
    account = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    _real_restore(account, "synthetic@example.invalid")
    assert seen == [{
        "mail": "synthetic@example.invalid", "world": "s301-en",
        "player": "ExamplePlayer", "cookies_only": True,
    }]


def test_cli_rejects_unconfirmed_network_probe_and_avoids_echo(capsys, monkeypatch, tmp_path):
    from daedalus.cli import main

    path = tmp_path / "config.toml"
    path.write_text('schema = 1\n[[accounts]]\nid = "alpha"\n'
                    'world = "s301-en"\nplayer = "ExamplePlayer"\n')
    monkeypatch.setattr(
        "getpass.getpass", lambda *_: "synthetic@example.invalid",
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    import daedalus.saved_session_recovery as recovery

    bound = []
    monkeypatch.setattr(recovery, "bind_saved_email", lambda account, email: bound.append(account.id))
    with pytest.raises(SystemExit) as exc:
        main(["sessions", "probe-saved-cookies", "alpha", "--config", str(path)])
    assert exc.value.code == 2
    assert "confirm-read-only-network" in capsys.readouterr().err
    assert main(["sessions", "bind-email", "alpha", "--config", str(path)]) == 0
    output = capsys.readouterr().out
    assert "saved_account_bound" in output
    assert "synthetic@example.invalid" not in output
    assert bound == ["alpha"]


def test_user_imports_world_cookie_only_after_verified_manual_handoff(setup):
    from daedalus.saved_session_recovery import bind_world_cookie

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    old_count = len(keys.entries)
    cookie = "A" * 48
    inspected = []
    session = _session()

    def verified_restore(a, email, raw_cookie):
        inspected.append((a.id, email, raw_cookie))
        return session

    with pytest.raises(SavedSessionUnavailable, match="confirmation"):
        bind_world_cookie(
            account, owner, cookie, confirmed=False, credential_store=keys,
            restore=verified_restore,
        )
    assert len(keys.entries) == old_count
    assert inspected == []

    result = bind_world_cookie(
        account, owner, cookie, confirmed=True, credential_store=keys,
        restore=verified_restore,
    )
    assert result == {"account_id": "alpha", "status": "world_cookie_bound"}
    assert session.s.closed
    assert inspected == [("alpha", "synthetic@example.invalid", cookie)]
    assert len(keys.entries) == old_count + 1
    cookie_entry = next((key for key in keys.entries if "world-cookie" in key[0]), None)
    assert cookie_entry is not None
    assert keys.entries[cookie_entry] == cookie
    assert cookie not in str(account.to_dict())
    assert cookie not in str(result)
    assert account.id not in str(cookie_entry[1])
    assert owner.status("alpha") == "not_connected"

    from daedalus.saved_session_recovery import unbind_world_cookie
    unbind_world_cookie(account, credential_store=keys)
    assert len(keys.entries) == old_count


@pytest.mark.parametrize("invalid", [
    "", "short", "spaces are invalid", "line\nfeed", "a;cookie", "a\\cookie",
    "Ö" * 30, "A" * 4097,
])
def test_invalid_world_cookie_never_reaches_network_or_keyring(setup, invalid):
    from daedalus.saved_session_recovery import bind_world_cookie

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    original = dict(keys.entries)
    with pytest.raises(SavedSessionUnavailable):
        bind_world_cookie(
            account, owner, invalid, confirmed=True, credential_store=keys,
            restore=lambda *_: pytest.fail("No network expected"),
        )
    assert keys.entries == original


def test_failed_cookie_import_keeps_previous_verified_credential(setup):
    from daedalus.saved_session_recovery import bind_world_cookie

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    bind_world_cookie(
        account, owner, "A" * 48, confirmed=True, credential_store=keys,
        restore=lambda *_: _session(),
    )
    snapshot = dict(keys.entries)
    secret = "private world response should not appear"

    def fails(*_):
        raise RuntimeError(secret)

    with pytest.raises(SavedSessionUnavailable) as error:
        bind_world_cookie(
            account, owner, "B" * 48, confirmed=True, credential_store=keys,
            restore=fails,
        )
    assert secret not in str(error.value)
    assert keys.entries == snapshot
    assert owner.status("alpha") == "not_connected"


def test_missing_saved_email_binding_prevents_cookie_import(setup):
    from daedalus.saved_session_recovery import bind_world_cookie

    account, owner, keys = setup
    with pytest.raises(SavedSessionUnavailable, match="Bind"):
        bind_world_cookie(
            account, owner, "A" * 48, confirmed=True, credential_store=keys,
            restore=lambda *_: pytest.fail("No network expected"),
        )


def test_existing_verified_handoff_is_used_only_in_cookie_only_engine_mode(
    setup, monkeypatch,
):
    import daedalus.saved_session_recovery as recovery
    from daedalus.saved_session_recovery import bind_world_cookie

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    bind_world_cookie(
        account, owner, "A" * 48, confirmed=True, credential_store=keys,
        restore=lambda *_: _session(),
    )
    observed = []

    def fake_restore(a, email, cookie=None):
        observed.append((a.id, email, cookie))
        return _session()

    original_restore = recovery._real_restore
    monkeypatch.setattr(recovery, "_real_restore", fake_restore)
    # Rebind the callable default as well: normal implementation chooses the
    # specific cookie-only engine restore path, never the standard login route.
    receipt = recovery.probe_saved_cookies(
        account, owner, confirmed=True, credential_store=keys,
        restore=recovery._real_restore,
    )
    assert receipt["status"] == "saved_session_valid"
    assert observed == [("alpha", "synthetic@example.invalid", "A" * 48)]
    # Test the direct restorer integration independently of monkeypatched defaults.
    import sys
    seen_engine = []

    class Engine:
        @staticmethod
        def from_saved(**kwargs):
            seen_engine.append(kwargs)
            return _session()

    monkeypatch.setitem(sys.modules, "ikabot.web.session", SimpleNamespace(Session=Engine))
    cookie = recovery._world_cookie_binding(account, keys)
    original_restore(account, "synthetic@example.invalid", cookie)
    assert seen_engine[0] == {
        "mail": "synthetic@example.invalid", "world": "s301-en",
        "player": "ExamplePlayer", "cookies_only": True,
        "world_cookie_override": "A" * 48,
    }


def test_manual_cookie_handoff_cli_requires_tty_and_read_only_consent(tmp_path, monkeypatch, capsys):
    import daedalus.saved_session_recovery as recovery
    from daedalus.cli import main

    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
        'player = "ExamplePlayer"\n',
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        main(["sessions", "bind-world-cookie", "alpha", "--config", str(config)])
    assert "confirm-read-only-network" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([
            "sessions", "bind-world-cookie", "alpha", "--config", str(config),
            "--confirm-read-only-network",
        ])
    assert "interactive terminal" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda *_: "A" * 48)
    calls = []
    monkeypatch.setattr(
        recovery, "bind_world_cookie",
        lambda account, owner, cookie, **kwargs: (
            calls.append((account.id, len(cookie), kwargs["confirmed"]))
            or {"account_id": account.id, "status": "world_cookie_bound"}
        ),
    )
    assert main([
        "sessions", "bind-world-cookie", "alpha", "--config", str(config),
        "--confirm-read-only-network",
    ]) == 0
    output = capsys.readouterr().out
    assert "world_cookie_bound" in output
    assert "A" * 48 not in output
    assert calls == [("alpha", 48, True)]


def test_untrusted_plaintext_keyring_backend_is_never_used(monkeypatch):
    import sys

    from daedalus.saved_session_recovery import _store

    class FileKeyring:
        __module__ = "keyrings.alt.file"

    fake_keyring = SimpleNamespace(get_keyring=lambda: FileKeyring())
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    with pytest.raises(SavedSessionUnavailable, match="protected operating-system"):
        _store(None)


def test_canonical_os_keyring_backend_is_accepted(monkeypatch):
    import sys

    from daedalus.saved_session_recovery import _store

    class MacKeyring:
        __module__ = "keyring.backends.macOS"

    fake_keyring = SimpleNamespace(get_keyring=lambda: MacKeyring())
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    assert _store(None) is fake_keyring


def test_assisted_browser_holds_lease_through_manual_challenge_and_storage(setup):
    from daedalus.saved_session_recovery import assisted_browser_cookie_login

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    events = []
    secret = "B" * 48

    def browser(url):
        assert url == "https://lobby.ikariam.gameforge.com/"
        assert owner.status(account.id) != "not_connected"
        events.append("browser")
        return True

    def human():
        assert owner.status(account.id) != "not_connected"
        events.append("manual_challenge")
        return secret

    def restore(a, email, cookie):
        assert owner.status(account.id) != "not_connected"
        assert cookie == secret
        events.append("verify")
        return _session()

    result = assisted_browser_cookie_login(
        account, owner, confirmed=True, credential_store=keys,
        browser_open=browser, read_cookie=human, restore=restore,
    )
    assert result == {"account_id": account.id, "status": "world_cookie_bound"}
    assert events == ["browser", "manual_challenge", "verify"]
    assert owner.status(account.id) == "not_connected"
    assert secret not in str(result)


def test_assisted_browser_denies_unauthorized_or_busy_accounts(setup):
    from daedalus.saved_session_recovery import assisted_browser_cookie_login

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    calls = []
    opts = {"credential_store": keys, "browser_open": lambda _: calls.append(1) or True,
            "read_cookie": lambda: "C" * 48,
            "restore": lambda *_: _session()}
    with pytest.raises(SavedSessionUnavailable, match="approval"):
        assisted_browser_cookie_login(account, owner, confirmed=False, **opts)
    with owner.acquire(account.id), pytest.raises(SavedSessionUnavailable, match="owns"):
        assisted_browser_cookie_login(account, owner, confirmed=True, **opts)
    assert calls == []


def test_assisted_browser_rejects_wrong_identity_without_persisting(setup):
    from daedalus.saved_session_recovery import assisted_browser_cookie_login

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    old = dict(keys.entries)
    with pytest.raises(SavedSessionUnavailable, match="could not verify"):
        assisted_browser_cookie_login(
            account, owner, confirmed=True, credential_store=keys,
            browser_open=lambda _: True, read_cookie=lambda: "D" * 48,
            restore=lambda *_: _session(player="WrongPlayer"),
        )
    assert keys.entries == old
    assert owner.status(account.id) == "not_connected"


def test_assisted_browser_failed_open_does_not_prompt_for_secret(setup):
    from daedalus.saved_session_recovery import assisted_browser_cookie_login

    account, owner, keys = setup
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    with pytest.raises(SavedSessionUnavailable, match="open"):
        assisted_browser_cookie_login(
            account, owner, confirmed=True, credential_store=keys,
            browser_open=lambda _: False,
            read_cookie=lambda: pytest.fail("No secret prompt expected"),
        )
    assert owner.status(account.id) == "not_connected"
