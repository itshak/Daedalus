"""Offline secret-free account metadata editing and failure-path tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from daedalus.account_editor import AccountEditUnavailable, AccountMetadataStore
from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app

TOKEN = "x" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def private_config(tmp_path: Path) -> Path:
    directory = tmp_path / "private-config"
    directory.mkdir(mode=0o700)
    path = directory / "accounts.toml"
    path.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
        'player = "Example"\nlabel = "Example"\nenabled = true\n',
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


def _rows(**updates: object) -> list[dict[str, object]]:
    row: dict[str, object] = {
        "id": "alpha", "world": "s301-en", "player": "Example",
        "label": "Example", "enabled": True,
    }
    row.update(updates)
    return [row]


def _app(path: Path, **kwargs: object) -> TestClient:
    return TestClient(create_app(
        accounts_path=path, api_token=TOKEN, enable_account_editing=True, **kwargs
    ))


def test_opt_in_protected_full_metadata_lifecycle(private_config):
    read_only = TestClient(create_app(accounts_path=private_config, api_token=TOKEN))
    assert read_only.get("/api/v1/account-config").status_code == 401
    assert read_only.get("/api/v1/account-config", headers=AUTH).json()["enabled"] is False
    assert read_only.put("/api/v1/account-config", headers=AUTH, json={}).status_code == 503

    client = _app(private_config)
    assert client.get("/api/v1/account-config").status_code == 401
    old = client.get("/api/v1/account-config", headers=AUTH).json()
    assert old["enabled"] is True
    assert len(old["accounts"]) == 1
    assert old["revision"] == hashlib.sha256(private_config.read_bytes()).hexdigest()
    assert client.put("/api/v1/account-config", json={
        "revision": old["revision"], "accounts": _rows(), "confirmed": True,
    }).status_code == 401
    assert client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": old["revision"], "accounts": _rows(), "confirmed": False,
    }).status_code == 422

    updated = _rows(label="Renamed", enabled=False) + [{
        "id": "beta", "world": "s302-en", "player": "Second",
        "label": "New account", "enabled": True,
    }]
    res = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": old["revision"], "accounts": updated, "confirmed": True,
    })
    assert res.status_code == 200, res.text
    assert res.json()["revision"] != old["revision"]
    assert private_config.read_text().count("[[accounts]]") == 2
    assert [a.id for a in load_accounts(private_config)] == ["alpha", "beta"]
    assert client.get("/api/v1/accounts", headers=AUTH).json()["accounts"][0]["enabled"] is False
    assert client.get("/api/v1/accounts/beta/session", headers=AUTH).status_code == 200
    assert client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": res.json()["revision"], "accounts": _rows(enabled=True),
        "confirmed": True,
    }).status_code == 200
    assert [a.id for a in load_accounts(private_config)] == ["alpha"]
    if os.name != "nt":
        assert private_config.stat().st_mode & 0o777 == 0o600
    assert not list(private_config.parent.glob(".accounts-*.tmp"))


def test_stale_revision_rejected_with_no_partial_write(private_config):
    client = _app(private_config)
    initial = client.get("/api/v1/account-config", headers=AUTH).json()
    first = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": initial["revision"], "accounts": _rows(label="First"), "confirmed": True,
    })
    assert first.status_code == 200
    saved = private_config.read_bytes()
    res = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": initial["revision"], "accounts": _rows(label="Stale"), "confirmed": True,
    })
    assert res.status_code == 409
    assert private_config.read_bytes() == saved
    private_config.write_text(private_config.read_text() + "# concurrent change\n")
    res = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": hashlib.sha256(private_config.read_bytes()).hexdigest(),
        "accounts": _rows(label="Concurrent"), "confirmed": True,
    })
    assert res.status_code == 409
    assert "Concurrent" not in private_config.read_text()


@pytest.mark.parametrize("invalid", [
    _rows(password="private-token"),
    _rows(email="secret@example.invalid"),
    _rows(enabled="yes"),
    _rows(id="INVALID"),
    _rows(player=""),
    _rows(label=""),
    _rows(world="../invalid"),
    _rows() * 2,
])
def test_credential_and_identity_validation_precedes_writes(private_config, invalid):
    client = _app(private_config)
    before = private_config.read_bytes()
    current = client.get("/api/v1/account-config", headers=AUTH).json()
    result = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": current["revision"], "accounts": invalid, "confirmed": True,
    })
    assert result.status_code == 422
    assert private_config.read_bytes() == before
    assert "private-token" not in result.text


def test_lease_and_task_controller_exclude_mutations(private_config, tmp_path):
    accounts = load_accounts(private_config)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "leases")
    client = _app(private_config, session_coordinator=owner)
    current = client.get("/api/v1/account-config", headers=AUTH).json()
    before = private_config.read_bytes()
    with owner.acquire("alpha"):
        result = client.put("/api/v1/account-config", headers=AUTH, json={
            "revision": current["revision"], "accounts": _rows(label="Changed"),
            "confirmed": True,
        })
        assert result.status_code == 409
    assert private_config.read_bytes() == before
    with pytest.raises(ValueError, match="cannot run together"):
        create_app(
            accounts_path=private_config, api_token=TOKEN,
            enable_account_editing=True, task_controller=object(),
        )


def test_lease_held_by_independent_local_coordinator_is_detected(private_config, tmp_path):
    accounts = load_accounts(private_config)
    state = tmp_path / "leases"
    other = AccountSessionCoordinator(accounts, state_dir=state)
    target = AccountSessionCoordinator(accounts, state_dir=state)
    client = _app(private_config, session_coordinator=target)
    snapshot = client.get("/api/v1/account-config", headers=AUTH).json()
    with other.acquire("alpha"):
        result = client.put("/api/v1/account-config", headers=AUTH, json={
            "revision": snapshot["revision"], "accounts": _rows(label="Blocked"),
            "confirmed": True,
        })
        assert result.status_code == 409
    assert load_accounts(private_config)[0].label == "Example"


def test_private_path_and_symlink_enforced(private_config, tmp_path):
    path = tmp_path / "link.toml"
    path.symlink_to(private_config)
    with pytest.raises(AccountEditUnavailable):
        AccountMetadataStore(path)
    if os.name != "nt":
        private_config.chmod(0o644)
        with pytest.raises(AccountEditUnavailable):
            AccountMetadataStore(private_config)
        private_config.chmod(0o600)
        private_config.parent.chmod(0o755)
        with pytest.raises(AccountEditUnavailable):
            AccountMetadataStore(private_config)


def test_empty_default_config_can_create_first_account(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    client = TestClient(create_app(api_token=TOKEN, enable_account_editing=True))
    snapshot = client.get("/api/v1/account-config", headers=AUTH).json()
    assert snapshot["accounts"] == []
    result = client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": snapshot["revision"], "accounts": _rows(), "confirmed": True,
    })
    assert result.status_code == 200
    assert client.get("/api/v1/accounts", headers=AUTH).json()["accounts"][0]["id"] == "alpha"
