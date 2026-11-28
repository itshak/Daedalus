"""One app-owned macOS Keychain key; authenticated, scoped local records.

The original Keychain ACL is respected. Only the supervised local helper pipe
may carry the in-memory master between trusted Daedalus processes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import stat
import sys
import tempfile
import threading
from pathlib import Path

_MASTER_SERVICE = "io.github.itshak.daedalus.credentials.v2"
_MASTER_SLOT = "Daedalus application credential vault"
_MAX_RECORD = 32768
_lock = threading.RLock()
_master: bytes | bool | None = None
_observer = None


class SharedKeychainError(RuntimeError):
    """Sanitized local vault failure."""


def enabled() -> bool:
    return sys.platform == "darwin"


def _directory() -> Path:
    return Path.home() / "Library" / "Application Support" / "Daedalus" / "credential-vault-v2"


def _private_directory() -> Path:
    root = _directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SharedKeychainError("Unsafe local credential vault directory")
    return root


def _native_provider():
    # Never select a plaintext/third-party fallback for the master.
    from keyring.backends.macOS import Keyring
    return Keyring()


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    result = base64.b64decode(value, validate=True)
    if len(result) != 32:
        raise SharedKeychainError("Invalid credential vault key")
    return result


def pipe_state() -> str | bool | None:
    """Private pipe payload only; never log or emit a Qt signal with this value."""
    with _lock:
        return _encode(_master) if isinstance(_master, bytes) else _master


def accept_pipe_state(value: object) -> None:
    """Accept only a private parent/child unlock result, never a server value."""
    global _master
    if value is None:
        return
    if value is False:
        incoming = False
    elif isinstance(value, str):
        incoming = _decode(value)
    else:
        raise SharedKeychainError("Invalid credential vault unlock state")
    with _lock:
        if _master is not None and _master != incoming:
            raise SharedKeychainError("Conflicting credential vault unlock state")
        _master = incoming


def observe_unlock(callback) -> None:
    global _observer
    _observer = callback


def _key() -> bytes:
    from filelock import FileLock

    global _master
    with _lock:
        if _master is False:
            raise SharedKeychainError("Credential vault unavailable; restart to retry")
        if isinstance(_master, bytes):
            return _master
        root = _private_directory()
        try:
            # Serializes first creation across separate app instances. The
            # lock contains no secret and lives in the private vault directory.
            with FileLock(str(root / ".initialize.lock"), timeout=15):
                provider = _native_provider()
                stored = provider.get_password(_MASTER_SERVICE, _MASTER_SLOT)
                if stored is None:
                    if any(root.glob("*.sealed")):
                        raise SharedKeychainError("Credential vault key is missing")
                    key = secrets.token_bytes(32)
                    provider.set_password(_MASTER_SERVICE, _MASTER_SLOT, _encode(key))
                else:
                    key = _decode(stored)
            _master = key
        except Exception as exc:
            _master = False
            if _observer is not None:
                _observer(False)
            raise SharedKeychainError("Unable to unlock macOS credential vault") from exc
        if _observer is not None:
            _observer(_encode(key))
        return key


def _binding(service: str, slot: str) -> bytes:
    return b"Daedalus local credential record v2\x00" + json.dumps(
        [service, slot], ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")


def _read(root: Path, binding: bytes, key: bytes) -> tuple[bool, str | None]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    target = root / (hashlib.sha256(binding).hexdigest() + ".sealed")
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False, None
    try:
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_size > _MAX_RECORD):
                raise SharedKeychainError("Unsafe credential record")
            data = handle.read(_MAX_RECORD + 1)
        if len(data) > _MAX_RECORD or len(data) < 29 or data[0] != 2:
            raise SharedKeychainError("Invalid credential record")
        value = json.loads(AESGCM(key).decrypt(data[1:13], data[13:], binding))
        if value is not None and not isinstance(value, str):
            raise SharedKeychainError("Invalid credential record")
        return True, value
    except Exception as exc:
        raise SharedKeychainError("Unable to open encrypted credential record") from exc


def _write(root: Path, binding: bytes, key: bytes, value: str | None) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    target = root / (hashlib.sha256(binding).hexdigest() + ".sealed")
    nonce = secrets.token_bytes(12)
    data = b"\x02" + nonce + AESGCM(key).encrypt(
        nonce, json.dumps(value, ensure_ascii=True).encode("ascii"), binding,
    )
    if len(data) > _MAX_RECORD:
        raise SharedKeychainError("Credential record too large")
    fd, temp = tempfile.mkstemp(prefix=".record-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class _SharedProvider:
    def __init__(self, legacy):
        self._legacy = legacy

    def get_password(self, service: str, slot: str) -> str | None:
        key = _key()
        root, binding = _private_directory(), _binding(service, slot)
        exists, value = _read(root, binding, key)
        if exists:
            return value
        # One-time migration; never try a legacy item after an encrypted
        # record fails integrity validation or after explicit forgetting.
        value = self._legacy.get_password(service, slot)
        _write(root, binding, key, value)
        return value

    def set_password(self, service: str, slot: str, value: str) -> None:
        if not isinstance(value, str):
            raise SharedKeychainError("Invalid credential value")
        key = _key()
        root, binding = _private_directory(), _binding(service, slot)
        _read(root, binding, key)  # Do not silently replace corrupt storage.
        _write(root, binding, key, value)

    def delete_password(self, service: str, slot: str) -> None:
        key = _key()
        root, binding = _private_directory(), _binding(service, slot)
        _read(root, binding, key)
        # Explicit forget also removes any old item; a tombstone prevents
        # fallback to legacy storage. No deletion occurs during migration.
        if self._legacy.get_password(service, slot) is not None:
            self._legacy.delete_password(service, slot)
        _write(root, binding, key, None)


def provider(legacy):
    return _SharedProvider(_native_provider()) if enabled() else legacy
