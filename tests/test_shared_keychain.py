"""No real Keychain, credentials, browsers, or game network."""
from __future__ import annotations

import os
import sys

import pytest

from daedalus import connection_prefs
from daedalus import shared_keychain as vault

pytestmark = pytest.mark.skipif(os.name != "posix", reason="macOS private file semantics")


class FakeNative:
    def __init__(self):
        self.values = {}
        self.reads = []
        self.writes = []
        self.denied = False

    def get_password(self, service, slot):
        self.reads.append((service, slot))
        if self.denied:
            raise RuntimeError("synthetic denial")
        return self.values.get((service, slot))

    def set_password(self, service, slot, value):
        self.writes.append((service, slot))
        self.values[service, slot] = value

    def delete_password(self, service, slot):
        del self.values[service, slot]


@pytest.fixture
def mac(monkeypatch, tmp_path):
    native = FakeNative()
    root = tmp_path / "private"
    monkeypatch.setattr(vault, "enabled", lambda: True)
    monkeypatch.setattr(vault, "_native_provider", lambda: native)
    monkeypatch.setattr(vault, "_directory", lambda: root)
    monkeypatch.setattr(vault, "_master", None)
    monkeypatch.setattr(vault, "_observer", None)
    return native, root


def test_shared_root_across_token_and_account_records(mac, tmp_path):
    native, root = mac
    from daedalus.desktop import selenium_credentials, selenium_vault
    from daedalus.desktop.selenium_auth import GameforgeCredentials

    token = "synthetic-token-" + "x" * 32
    origin = "https://example.invalid"
    prefs = tmp_path / "settings" / "connection.json"
    connection_prefs.remember_connection(origin, token, path=prefs)
    credentials = GameforgeCredentials("fixture@example.invalid", "synthetic-only-password")
    envelopes = {}
    for n in range(10):
        aid = f"account-{n}"
        selenium_credentials.remember_login(origin, aid, "s53-ru", credentials)
        envelopes[aid] = {k: v for k, v in selenium_vault.seal_login(origin, aid, "s53-ru", credentials).items() if k != "confirmed"}
    # The first lookup of a legacy slot may find no entry; no per-account
    # writes to Keychain ever occur in the new store.
    assert list(native.values) == [(vault._MASTER_SERVICE, vault._MASTER_SLOT)]
    assert native.writes == [(vault._MASTER_SERVICE, vault._MASTER_SLOT)]
    before = list(native.reads)
    for aid, envelope in envelopes.items():
        assert selenium_vault.unseal_login(origin, aid, "s53-ru", envelope) == credentials
        assert selenium_credentials.get_saved_login(origin, aid, "s53-ru") == credentials
    assert connection_prefs.saved_connection(prefs) == (origin, token)
    assert native.reads == before
    assert len(list(root.glob("*.sealed"))) == 21
    for path in root.glob("*.sealed"):
        assert path.stat().st_mode & 0o077 == 0
        assert b"synthetic-only-password" not in path.read_bytes()
        assert token.encode() not in path.read_bytes()
    assert root.stat().st_mode & 0o077 == 0


def test_existing_server_envelope_key_migrates_without_resealing(mac, monkeypatch):
    native, _root = mac
    from daedalus.desktop import selenium_credentials, selenium_vault
    from daedalus.desktop.selenium_auth import GameforgeCredentials

    origin, aid, world = "https://example.invalid", "old-account", "s53-ru"
    creds = GameforgeCredentials("fixture@example.invalid", "synthetic-password")
    # Generate a genuine version-1 envelope using the historical storage
    # contract, then switch to the unified vault with identical slot binding.
    with monkeypatch.context() as m:
        m.setattr(selenium_vault, "_keyring", lambda: native)
        envelope = selenium_vault.seal_login(origin, aid, world, creds)
    envelope.pop("confirmed")
    slot = selenium_credentials._slot(origin, aid, world)
    legacy = native.values[selenium_vault._KEY_SERVICE, slot]
    assert selenium_vault.unseal_login(origin, aid, world, envelope) == creds
    assert native.values[selenium_vault._KEY_SERVICE, slot] == legacy
    count = len(native.reads)
    assert selenium_vault.unseal_login(origin, aid, world, envelope) == creds
    assert len(native.reads) == count
    assert selenium_vault.unseal_login(origin, "different", world, envelope) is None
    # A new process imports the unlock result through the private protocol.
    state = vault.pipe_state()
    monkeypatch.setattr(vault, "_master", None)
    vault.accept_pipe_state(state)
    count = len(native.reads)
    assert selenium_vault.unseal_login(origin, aid, world, envelope) == creds
    assert len(native.reads) == count


def test_legacy_token_migration_persists_after_restart_and_explicit_forget(mac, tmp_path, monkeypatch):
    native, _ = mac
    origin = "https://example.invalid"
    token = "legacy-token-" + "x" * 32
    target = tmp_path / "connection.json"
    connection_prefs._save_url(origin, path=target)
    native.values[connection_prefs._SERVICE, origin] = token
    assert connection_prefs.saved_connection(target) == (origin, token)
    monkeypatch.setattr(vault, "_master", None)
    before = len(native.reads)
    assert connection_prefs.saved_connection(target) == (origin, token)
    assert native.reads[before:] == [(vault._MASTER_SERVICE, vault._MASTER_SLOT)]
    connection_prefs.forget_connection(target)
    assert not target.exists()
    assert (connection_prefs._SERVICE, origin) not in native.values
    assert vault.provider(native).get_password(connection_prefs._SERVICE, origin) is None


def test_denied_root_is_not_reprompted_in_following_helpers(mac, monkeypatch):
    native, _ = mac
    native.denied = True
    seen = []
    vault.observe_unlock(seen.append)
    for slot in ("one", "two", "three"):
        with pytest.raises(vault.SharedKeychainError):
            vault.provider(native).get_password("service", slot)
    assert native.reads == [(vault._MASTER_SERVICE, vault._MASTER_SLOT)]
    assert seen == [False]
    assert vault.pipe_state() is False
    monkeypatch.setattr(vault, "_master", None)
    vault.accept_pipe_state(False)
    with pytest.raises(vault.SharedKeychainError):
        vault.provider(native).get_password("service", "four")
    assert len(native.reads) == 1


def test_authenticated_records_fail_closed_on_corruption_or_slot_swap(mac):
    native, root = mac
    provider = vault.provider(native)
    provider.set_password("service", "a", "secret-a")
    provider.set_password("service", "b", "secret-b")
    path_a = root / (vault.hashlib.sha256(vault._binding("service", "a")).hexdigest() + ".sealed")
    path_b = root / (vault.hashlib.sha256(vault._binding("service", "b")).hexdigest() + ".sealed")
    path_a.write_bytes(path_b.read_bytes())
    before = list(native.reads)
    with pytest.raises(vault.SharedKeychainError):
        provider.get_password("service", "a")
    with pytest.raises(vault.SharedKeychainError):
        provider.set_password("service", "a", "replacement")
    assert native.reads == before
    assert provider.get_password("service", "b") == "secret-b"


def test_missing_master_never_replaces_existing_encrypted_records(mac, monkeypatch):
    native, _ = mac
    provider = vault.provider(native)
    provider.set_password("service", "slot", "secret")
    native.values.clear()
    monkeypatch.setattr(vault, "_master", None)
    with pytest.raises(vault.SharedKeychainError):
        provider.get_password("service", "slot")
    assert not native.values


def test_browser_helper_reuses_private_unlock_pipe(mac, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from daedalus.desktop import selenium_worker
    from daedalus.desktop.selenium_auth import GameforgeCredentials

    app = QApplication.instance() or QApplication([])
    synthetic_key = vault._encode(b"k" * 32)
    # Exercise the real QThread/subprocess protocol without ever running Chrome.
    script = """
import base64,json,sys
key=base64.b64encode(b"k"*32).decode("ascii")
p=json.loads(sys.stdin.buffer.readline())
state=p.get("local_vault_state")
if state is None:
    assert p["account_id"] == "first"
    print(json.dumps({"kind":"local_vault_state","value":key}),flush=True)
else:
    assert p["account_id"] == "second" and state == key
assert "DAEDALUS_MASTER_KEY" not in __import__("os").environ
print(json.dumps({"kind":"cookie","value":"synthetic-cookie"}),flush=True)
"""
    monkeypatch.setattr(selenium_worker, "child_command", lambda: [sys.executable, "-u", "-c", script])
    for aid in ("first", "second"):
        worker = selenium_worker.SeleniumLoginWorker(
            "s53-ru", GameforgeCredentials("fixture@example.invalid", "fixture-password"),
            origin="https://example.invalid", account_id=aid,
            record={"id": aid, "world": "s53-ru"},
        )
        cookies, failures = [], []
        worker.cookie_ready.connect(cookies.append)
        worker.login_failed.connect(failures.append)
        try:
            worker.start()
            assert worker.wait(5000)
            app.processEvents()
            assert cookies == ["synthetic-cookie"]
            assert not failures
            assert vault.pipe_state() == synthetic_key
        finally:
            worker.cancel()
            worker.deleteLater()
    assert not mac[0].reads
