"""Synthetic OS keyring tests: no real credentials or user settings are touched."""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from daedalus.connection_prefs import (
    PreferenceError,
    forget_connection,
    load_connection_url,
    remember_connection,
    saved_connection,
)

TOKEN = "synthetic-test-only-" + ("x" * 32)
URL = "http://127.0.0.1:8765"


@pytest.fixture(autouse=True)
def legacy_provider_only(monkeypatch):
    from daedalus import shared_keychain
    monkeypatch.setattr(shared_keychain, "enabled", lambda: False)


@pytest.fixture
def keyring(monkeypatch):
    records = {}

    def set_password(service, username, password):
        records[(service, username)] = password

    def get_password(service, username):
        return records.get((service, username))

    def delete_password(service, username):
        records.pop((service, username))

    backend = SimpleNamespace(
        set_password=set_password,
        get_password=get_password,
        delete_password=delete_password,
    )
    monkeypatch.setitem(sys.modules, "keyring", backend)
    return records


def test_opt_in_creates_private_url_file_and_separate_keyring_entry(keyring, tmp_path):
    target = tmp_path / "private" / "connection.json"
    remember_connection(URL, TOKEN, path=target)
    assert load_connection_url(target) == URL
    assert saved_connection(target) == (URL, TOKEN)
    contents = target.read_text(encoding="utf-8")
    assert TOKEN not in contents
    assert json.loads(contents) == {"version": 1, "server_url": URL}
    assert len(keyring) == 1
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.parent.stat().st_mode & 0o777 == 0o700
    forget_connection(target)
    assert not target.exists()
    assert not keyring


def test_no_saved_or_missing_keyring_token_cannot_reconnect(keyring, tmp_path):
    target = tmp_path / "connection.json"
    assert saved_connection(target) is None
    remember_connection(URL, TOKEN, path=target)
    keyring.clear()
    with pytest.raises(PreferenceError, match="No saved"):
        saved_connection(target)


def test_keyring_failure_leaves_no_plaintext_fallback(monkeypatch, tmp_path):
    backend = SimpleNamespace(
        set_password=lambda *_: (_ for _ in ()).throw(RuntimeError("hidden-secret-should-not-appear")),
        get_password=lambda *_: None,
        delete_password=lambda *_: None,
    )
    monkeypatch.setitem(sys.modules, "keyring", backend)
    target = tmp_path / "connection.json"
    with pytest.raises(PreferenceError, match="OS keyring") as info:
        remember_connection(URL, TOKEN, path=target)
    assert "hidden-secret" not in str(info.value)
    assert not target.exists()


@pytest.mark.parametrize("bad", [
    "http://evil.example", "http://user:token@localhost:8765",
    "http://127.0.0.1:8765/?token=secret",
])
def test_invalid_urls_are_rejected_before_keyring_access(keyring, tmp_path, bad):
    with pytest.raises(PreferenceError):
        remember_connection(bad, TOKEN, path=tmp_path / "connection.json")
    assert not keyring


def test_malformed_url_file_fails_closed(tmp_path):
    target = tmp_path / "connection.json"
    for text in (
        "not-json",
        '{"version": 1, "server_url": "http://evil.example"}',
        '{"version":1,"server_url":"http://localhost:8765","token":"secret"}',
    ):
        target.write_text(text)
        if os.name != "nt":
            target.chmod(0o600)
        with pytest.raises(PreferenceError):
            load_connection_url(target)


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes not used on Windows")
def test_insecure_settings_permissions_are_rejected(tmp_path):
    target = tmp_path / "connection.json"
    target.write_text(json.dumps({"version": 1, "server_url": URL}))
    target.chmod(0o644)
    with pytest.raises(PreferenceError, match="owner-only"):
        load_connection_url(target)


def test_settings_symlink_is_rejected_without_following_it(keyring, tmp_path):
    real = tmp_path / "real.json"
    real.write_text('{"version":1,"server_url":"http://localhost:8765"}')
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(real)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(PreferenceError, match="Unsafe"):
        load_connection_url(alias)
    with pytest.raises(PreferenceError, match="symlink"):
        remember_connection(URL, TOKEN, path=alias)
    assert not keyring
