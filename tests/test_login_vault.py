"""Synthetic encrypted login vault tests: never contact Gameforge or use live secrets."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.login_vault import (
    LoginVaultUnavailable,
    read_login_vault,
    validate_login_vault,
    write_login_vault,
)
from daedalus.native_browser_handoff import NativeBrowserHandoff
from daedalus.saved_session_recovery import bind_saved_email

TOKEN = "unit-test-token-with-at-least-32-characters"
EMAIL = "synthetic@example.invalid"
CIPHERTEXT = "B" * 64
SEALED = {"version": 1, "nonce": "A" * 16, "ciphertext": CIPHERTEXT}


class FakeStore:
    def __init__(self):
        self.entries = {}

    def get_password(self, service, slot):
        return self.entries.get((service, slot))

    def set_password(self, service, slot, value):
        self.entries[(service, slot)] = value

    def delete_password(self, service, slot):
        self.entries.pop((service, slot), None)


def test_vault_requires_verified_email_and_keeps_only_ciphertext():
    account = Account("alpha", "s53-ru", "Player", "Imported IkaBot identity 01", True)
    store = FakeStore()
    with pytest.raises(LoginVaultUnavailable, match="binding"):
        write_login_vault(account, {**SEALED, "confirmed": True}, credential_store=store)
    assert store.entries == {}
    bind_saved_email(account, EMAIL, credential_store=store)
    write_login_vault(account, {**SEALED, "confirmed": True}, credential_store=store)
    saved = read_login_vault(account, credential_store=store)
    assert saved == SEALED
    assert EMAIL not in json.dumps(saved)
    assert "password" not in json.dumps(saved)
    second = Account("beta", "s53-ru", "Other", "Other", True)
    assert read_login_vault(second, credential_store=store) is None


@pytest.mark.parametrize("bad", [
    {"version": 2, "nonce": "A" * 16, "ciphertext": CIPHERTEXT, "confirmed": True},
    {"version": 1, "nonce": "A" * 16, "ciphertext": CIPHERTEXT, "confirmed": False},
    {"version": 1, "nonce": "a", "ciphertext": CIPHERTEXT, "confirmed": True},
    {"version": 1, "nonce": "A" * 16, "ciphertext": CIPHERTEXT,
     "confirmed": True, "password": "not-allowed"},
])
def test_vault_rejects_invalid_or_unsealed_records(bad):
    with pytest.raises(LoginVaultUnavailable):
        validate_login_vault(bad, confirmed=True)


def test_vault_endpoint_authentication_and_recovery(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s53-ru"\n'
        'player = "Player"\nlabel = "Imported IkaBot identity 01"\n'
        'enabled = true\n', encoding="utf-8",
    )
    account = Account("alpha", "s53-ru", "Player", "Imported IkaBot identity 01", True)
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "leases")
    store = FakeStore()
    broker = NativeBrowserHandoff([account], owner, credential_store=store)
    client = TestClient(create_app(
        accounts_path=config, api_token=TOKEN,
        session_coordinator=owner, native_browser_handoff=broker,
    ))
    auth = {"Authorization": "Bearer " + TOKEN}
    assert client.get("/api/v1/login-vaults").status_code == 401
    assert client.post(
        "/api/v1/accounts/alpha/login-vault", headers=auth,
        json={**SEALED, "confirmed": True},
    ).status_code == 409
    bind_saved_email(account, EMAIL, credential_store=store)
    assert client.post(
        "/api/v1/accounts/alpha/login-vault", headers=auth,
        json={**SEALED, "confirmed": True},
    ).json() == {"saved": True}
    assert client.get("/api/v1/login-vaults", headers=auth).json() == {
        "vaults": {"alpha": SEALED},
    }
    assert client.get("/api/v1/accounts", headers=auth).json()["accounts"][0]["email"] == EMAIL
    assert client.post(
        "/api/v1/accounts/unknown/login-vault", headers=auth,
        json={**SEALED, "confirmed": True},
    ).status_code == 404


def test_mac_seals_with_keychain_and_never_sends_plain_password(monkeypatch):
    from daedalus.desktop import selenium_vault
    from daedalus.desktop.selenium_auth import GameforgeCredentials

    keychain = FakeStore()
    monkeypatch.setattr(selenium_vault, "_keyring", lambda: keychain)
    creds = GameforgeCredentials(EMAIL, "synthetic-only-password")
    sealed = selenium_vault.seal_login("https://server.example", "alpha", "s53-ru", creds)
    assert EMAIL not in json.dumps(sealed)
    assert creds.password not in json.dumps(sealed)
    assert selenium_vault.unseal_login(
        "https://server.example", "alpha", "s53-ru",
        {key: sealed[key] for key in ("version", "nonce", "ciphertext")},
    ) == creds
    assert selenium_vault.unseal_login(
        "https://other.example", "alpha", "s53-ru", SEALED,
    ) is None
