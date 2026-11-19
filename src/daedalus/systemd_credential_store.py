"""Host-persistent, authenticated encrypted secrets using systemd credentials.

The systemd host-bound key is stored root-only as an encrypted credential and
materialized transiently for the service in CREDENTIALS_DIRECTORY. This is an
opt-in alternative to the host's volatile Secret Service session collection.
No plaintext Gameforge data or encryption key is stored in ordinary config.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = b"DAEDALUS-SYSTEMD-AESGCM-v1\n"
_MAX_VALUE = 8192
_CREDENTIAL = "daedalus-store-key"


class ProtectedStoreUnavailable(RuntimeError):
    """Sanitized error; never include a secret or plaintext payload."""


class SystemdCredentialStore:
    """Encrypted, account-bound storage implementing keyring's three methods."""

    def __init__(self, directory: str | Path, *, key_file: str | Path) -> None:
        directory = Path(directory).expanduser()
        path = Path(key_file)
        try:
            if (not directory.is_absolute() or directory.is_symlink()
                    or (directory.exists() and not directory.is_dir())):
                raise ProtectedStoreUnavailable("Unsafe encrypted credential directory")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            mode = directory.stat().st_mode
            if os.name != "nt" and mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise ProtectedStoreUnavailable("Encrypted credential directory is not private")
            if path.is_symlink() or not path.is_file():
                raise ProtectedStoreUnavailable("Protected systemd encryption key is unavailable")
            key = path.read_bytes()
            if len(key) != 32:
                raise ProtectedStoreUnavailable("Protected systemd key has invalid length")
            self._aead = AESGCM(key)
            self._directory = directory
        except OSError as exc:
            raise ProtectedStoreUnavailable("Protected systemd credential store is unavailable") from exc

    @staticmethod
    def _identity(service: str, username: str) -> bytes:
        if (not isinstance(service, str) or not service.startswith("io.github.itshak.daedalus.")
                or not isinstance(username, str) or len(username) != 64
                or not all(char in "0123456789abcdef" for char in username)):
            raise ProtectedStoreUnavailable("Invalid encrypted credential identity")
        return (service + "\x00" + username).encode("utf-8")

    def _path(self, identity: bytes) -> Path:
        return self._directory / (hashlib.sha256(identity).hexdigest() + ".secret")

    def set_password(self, service: str, username: str, password: str) -> None:
        identity = self._identity(service, username)
        if not isinstance(password, str):
            raise ProtectedStoreUnavailable("Invalid encrypted credential value")
        value = password.encode("utf-8")
        if len(value) > _MAX_VALUE:
            raise ProtectedStoreUnavailable("Encrypted credential value exceeds the limit")
        destination = self._path(identity)
        try:
            if destination.is_symlink():
                raise ProtectedStoreUnavailable("Unsafe encrypted credential path")
            nonce = secrets.token_bytes(12)
            ciphertext = _MAGIC + nonce + self._aead.encrypt(nonce, value, identity)
            fd, temp = tempfile.mkstemp(prefix=".daedalus-", dir=self._directory)
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(ciphertext)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, destination)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        except OSError as exc:
            raise ProtectedStoreUnavailable("Encrypted credential could not be saved") from exc

    def get_password(self, service: str, username: str) -> str | None:
        identity = self._identity(service, username)
        destination = self._path(identity)
        try:
            if destination.is_symlink():
                raise ProtectedStoreUnavailable("Unsafe encrypted credential path")
            if not destination.exists():
                return None
            if (not destination.is_file() or destination.stat().st_size > _MAX_VALUE + 256):
                raise ProtectedStoreUnavailable("Encrypted credential file is invalid")
            mode = destination.stat().st_mode
            if os.name != "nt" and mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise ProtectedStoreUnavailable("Encrypted credential file permissions are unsafe")
            raw = destination.read_bytes()
            if not raw.startswith(_MAGIC) or len(raw) < len(_MAGIC) + 12 + 16:
                raise ProtectedStoreUnavailable("Encrypted credential file is invalid")
            tail = raw[len(_MAGIC):]
            return self._aead.decrypt(tail[:12], tail[12:], identity).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise ProtectedStoreUnavailable("Encrypted credential authentication failed") from exc
        except OSError as exc:
            raise ProtectedStoreUnavailable("Encrypted credential cannot be read") from exc

    def delete_password(self, service: str, username: str) -> None:
        destination = self._path(self._identity(service, username))
        if destination.is_symlink():
            raise ProtectedStoreUnavailable("Unsafe encrypted credential path")
        try:
            destination.unlink(missing_ok=True)
        except OSError as exc:
            raise ProtectedStoreUnavailable("Encrypted credential cannot be deleted") from exc


def store_from_systemd_environment() -> SystemdCredentialStore | None:
    """Explicit selection; missing key must never fall back to volatile storage."""
    directory = os.environ.get("DAEDALUS_PROTECTED_STORE_DIR")
    if not directory:
        return None
    credential_directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not credential_directory:
        raise ProtectedStoreUnavailable("Systemd encrypted credential was not loaded")
    return SystemdCredentialStore(
        directory, key_file=Path(credential_directory) / _CREDENTIAL,
    )
