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
