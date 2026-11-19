"""Linux systemd host-bound credential storage: encrypted, fail-closed, portable."""
from __future__ import annotations

import hashlib
import os

import pytest

from daedalus.systemd_credential_store import (
    ProtectedStoreUnavailable,
    SystemdCredentialStore,
    store_from_systemd_environment,
)

SERVICE = "io.github.itshak.daedalus.world-cookie"
USER = hashlib.sha256(b"test-account").hexdigest()
OTHER = hashlib.sha256(b"another-account").hexdigest()


def _store(tmp_path, *, key=b"k"*32):
    root = tmp_path / "keys"
    root.mkdir(mode=0o700, exist_ok=True)
    keyfile = root / "daedalus-store-key"
    keyfile.write_bytes(key)
    keyfile.chmod(0o600)
    return SystemdCredentialStore(tmp_path / "private", key_file=keyfile)


def test_keyed_secret_encryption_survives_store_reconstruction(tmp_path):
    store = _store(tmp_path)
    store.set_password(SERVICE, USER, "synthetic-secret-must-not-appear-on-disk")
    files = list((tmp_path / "private").glob("*.secret"))
    assert len(files) == 1
    raw = files[0].read_bytes()
    assert b"synthetic-secret" not in raw
    assert USER.encode() not in raw
    assert SERVICE.encode() not in raw
    assert files[0].stat().st_mode & 0o077 == 0
    assert store.get_password(SERVICE, USER) == "synthetic-secret-must-not-appear-on-disk"
    restored = _store(tmp_path)
    assert restored.get_password(SERVICE, USER) == store.get_password(SERVICE, USER)
    assert restored.get_password(SERVICE, OTHER) is None
    store.delete_password(SERVICE, USER)
    assert restored.get_password(SERVICE, USER) is None


def test_encryption_binds_account_and_service_and_rejects_tampering(tmp_path):
    store = _store(tmp_path)
    store.set_password(SERVICE, USER, "fictional-cookie")
    root = tmp_path / "private"
    file = next(root.glob("*.secret"))
    store.set_password(SERVICE, OTHER, "different-cookie")
    other = next(p for p in root.glob("*.secret") if p != file)
    a, b = file.read_bytes(), other.read_bytes()
    file.write_bytes(b)
    with pytest.raises(ProtectedStoreUnavailable, match="authentication failed"):
        store.get_password(SERVICE, USER)
    file.write_bytes(a[:-1] + bytes([a[-1] ^ 1]))
    with pytest.raises(ProtectedStoreUnavailable, match="authentication failed"):
        store.get_password(SERVICE, USER)


def test_no_weak_fallback_when_systemd_key_unavailable(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    monkeypatch.setenv("DAEDALUS_PROTECTED_STORE_DIR", str(directory))
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    with pytest.raises(ProtectedStoreUnavailable, match="not loaded"):
        store_from_systemd_environment()
    assert not directory.exists()
    keydir = tmp_path / "keys"
    keydir.mkdir()
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(keydir))
    with pytest.raises(ProtectedStoreUnavailable, match="unavailable"):
        store_from_systemd_environment()
    assert not directory.exists() or list(directory.glob("*.secret")) == []


def test_secret_isolation_invalid_identity_and_unsafe_file_modes(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ProtectedStoreUnavailable):
        store.set_password("untrusted.service", USER, "bad")
    with pytest.raises(ProtectedStoreUnavailable):
        store.set_password(SERVICE, "../../untrusted", "bad")
    store.set_password(SERVICE, USER, "test-value")
    file = next((tmp_path / "private").glob("*.secret"))
    file.chmod(0o644)
    if os.name != "nt":
        with pytest.raises(ProtectedStoreUnavailable, match="permissions"):
            store.get_password(SERVICE, USER)
    file.chmod(0o600)
    file.unlink()
    file.symlink_to(tmp_path / "missing")
    with pytest.raises(ProtectedStoreUnavailable):
        store.get_password(SERVICE, USER)
    with pytest.raises(ProtectedStoreUnavailable):
        store.set_password(SERVICE, USER, "test-value")


def test_wrong_key_fails_closed_without_secret_echo(tmp_path):
    store = _store(tmp_path)
    store.set_password(SERVICE, USER, "fictional-sensitive-text")
    keyfile = tmp_path / "keys" / "daedalus-store-key"
    keyfile.write_bytes(b"v"*32)
    replaced = SystemdCredentialStore(tmp_path / "private", key_file=keyfile)
    with pytest.raises(ProtectedStoreUnavailable) as exc:
        replaced.get_password(SERVICE, USER)
    assert "fictional-sensitive-text" not in str(exc.value)


def test_integration_saved_session_recovery_uses_explicit_encrypted_store(tmp_path, monkeypatch):
    from daedalus.saved_session_recovery import _store
    directory = tmp_path / "private"
    root = tmp_path / "keys"
    root.mkdir()
    (root / "daedalus-store-key").write_bytes(b"f"*32)
    monkeypatch.setenv("DAEDALUS_PROTECTED_STORE_DIR", str(directory))
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(root))
    selected = _store(None)
    assert isinstance(selected, SystemdCredentialStore)
    selected.set_password(SERVICE, USER, "nonsecret-test-string")
    assert _store(None).get_password(SERVICE, USER) == "nonsecret-test-string"
    monkeypatch.delenv("CREDENTIALS_DIRECTORY")
    with pytest.raises(Exception, match="Systemd encrypted credential was not loaded"):
        _store(None)
