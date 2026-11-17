"""Local account configuration is validated and never contains secrets."""

from pathlib import Path

import pytest

from daedalus.accounts import (
    AccountConfigError,
    default_accounts_path,
    load_accounts,
    parse_accounts,
)


def test_valid_two_accounts():
    accounts = parse_accounts(
        '''
schema = 1
[[accounts]]
id = "alpha"
world = "s301-en"
player = "ExampleOne"
[[accounts]]
id = "beta"
world = "s301-en"
player = "ExampleTwo"
label = "Other"
enabled = false
'''
    )
    assert [a.id for a in accounts] == ["alpha", "beta"]
    assert accounts[0].enabled is True
    assert accounts[1].enabled is False
    assert accounts[0].to_dict()["session_status"] == "not_connected"
    assert "password" not in accounts[0].to_dict()


@pytest.mark.parametrize(
    "extra",
    [
        'password = "do-not-accept"',
        'gf_token = "do-not-accept"',
        'email = "do-not-accept"',
        'cookies = "do-not-accept"',
    ],
)
def test_reject_credentials_in_metadata(extra):
    with pytest.raises(AccountConfigError, match="credentials"):
        parse_accounts('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
                       'player = "Example"\n' + extra)


def test_reject_duplicate_ids():
    with pytest.raises(AccountConfigError, match="Duplicate account id"):
        parse_accounts(
            'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
            'player = "One"\n[[accounts]]\nid = "alpha"\nworld = "s302-en"\n'
            'player = "Two"'
        )


def test_reject_duplicate_world_player():
    with pytest.raises(AccountConfigError, match="Duplicate world/player"):
        parse_accounts(
            'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
            'player = "One"\n[[accounts]]\nid = "beta"\nworld = "S301-EN"\n'
            'player = "one"'
        )


def test_default_missing_returns_empty_without_writing(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert load_accounts() == []
    assert default_accounts_path() == tmp_path / "daedalus" / "accounts.toml"
    assert list(tmp_path.iterdir()) == []


def test_explicit_missing_raises_redacted_error(tmp_path: Path):
    with pytest.raises(AccountConfigError, match="Unable to read accounts configuration"):
        load_accounts(tmp_path / "missing.toml")


def test_example_config_is_parsable():
    root = Path(__file__).resolve().parents[1]
    config = root / "docs" / "examples" / "accounts.toml"
    assert len(load_accounts(config)) == 2


@pytest.mark.parametrize(
    "text",
    ["", "schema = 2\naccounts = []", 'schema = 1\n[[accounts]]\nid = "INVALID"'],
)
def test_schema_and_identity_rejections(text):
    with pytest.raises(AccountConfigError):
        parse_accounts(text)
