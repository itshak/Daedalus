"""Opt-in, secret-free account metadata editor with optimistic atomic writes.

This module never opens a game session or reads account credentials. Only the
public TOML account metadata format is accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from daedalus.accounts import Account, AccountConfigError, default_accounts_path, parse_accounts

_REVISION = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = frozenset({"id", "world", "player", "label", "enabled"})


class AccountEditConflict(RuntimeError):
    """The stored generation changed or an authenticated worker holds a lease."""


class AccountEditUnavailable(RuntimeError):
    """Metadata storage is not safe for writes."""


def _serialize(rows: object) -> tuple[bytes, list[Account]]:
    if not isinstance(rows, list) or len(rows) > 256:
        raise AccountConfigError("Expected at most 256 account metadata records")
    chunks = ["schema = 1", ""]
    for idx, record in enumerate(rows, 1):
        if not isinstance(record, dict) or record.keys() != _FIELDS:
            raise AccountConfigError(f"Account #{idx} must have exactly the five allowed fields")
        if any(type(record[field]) is not (bool if field == "enabled" else str) for field in _FIELDS):
            raise AccountConfigError(f"Account #{idx} has an invalid field type")
        chunks.append("[[accounts]]")
        for key in ("id", "world", "player", "label"):
            chunks.append(f"{key} = {json.dumps(record[key], ensure_ascii=True)}")
        chunks.append("enabled = true" if record["enabled"] else "enabled = false")
        chunks.append("")
    data = ("\n".join(chunks) + "\n").encode("utf-8")
    if len(data) > 128 * 1024:
        raise AccountConfigError("Account configuration is too large")
    parsed = parse_accounts(data.decode("utf-8"))
    return data, parsed


class AccountMetadataStore:
    """Owns the private configuration path; no mutations outside explicit opt-in."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser().absolute() if path is not None else default_accounts_path()
        root = Path(__file__).resolve().parents[2]
        if self.path.resolve().is_relative_to(root):
            raise AccountEditUnavailable("Account editing inside the project checkout is forbidden")
        self._lock_path = self.path.with_name(self.path.name + ".edit.lock")
        # Do not create any path until the operator actually requests an edit.
        self._expected_server_revision = self._read()[0]

    def _validate_path(self, *, create_parent: bool = False) -> None:
        parent = self.path.parent
        if any(directory.is_symlink() for directory in (parent, *parent.parents)):
            raise AccountEditUnavailable("Metadata directory must not be a symlink")
        if create_parent:
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent.is_dir() or self.path.is_symlink() or self._lock_path.is_symlink():
            raise AccountEditUnavailable("Metadata path must be a real file in a private directory")
        if os.name != "nt":
            info = parent.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise AccountEditUnavailable("Metadata directory must be owned by the user and mode 0700")
            for item in (self.path, self._lock_path):
                if item.exists():
                    st = item.stat()
                    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                        raise AccountEditUnavailable("Metadata files must be private owner-only regular files")

    def _read(self) -> tuple[str, list[Account]]:
        if not self.path.exists():
            if self.path.is_symlink():
                raise AccountEditUnavailable("Configuration may not be a symlink")
            return hashlib.sha256(b"").hexdigest(), []
        self._validate_path()
        try:
            data = self.path.read_bytes()
            if len(data) > 128 * 1024:
                raise AccountEditUnavailable("Metadata file is too large")
            return hashlib.sha256(data).hexdigest(), parse_accounts(data.decode("utf-8"))
        except (OSError, UnicodeError) as exc:
            raise AccountEditUnavailable("Cannot safely read account metadata") from exc

    def snapshot(self) -> dict[str, object]:
        revision, accounts = self._read()
        return {
            "enabled": True,
            "revision": revision,
            "accounts": [
                {"id": a.id, "world": a.world, "player": a.player,
                 "label": a.label, "enabled": a.enabled}
                for a in accounts
            ],
        }

    def update(self, revision: object, rows: object, coordinator: Any) -> dict[str, object]:
        if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
            raise AccountConfigError("A valid account configuration revision is required")
        data, accounts = _serialize(rows)
        self._validate_path(create_parent=True)
        lock = FileLock(str(self._lock_path))
        try:
            lock.acquire(timeout=0)
        except Timeout as exc:
            raise AccountEditConflict("Another editor is currently changing accounts") from exc
        try:
            if os.name != "nt":
                os.chmod(self._lock_path, 0o600)
            self._validate_path()
            actual_revision, current = self._read()
            if revision != actual_revision or actual_revision != self._expected_server_revision:
                raise AccountEditConflict("Account configuration changed; reload or restart the backend")
            if not coordinator.matches_accounts(current):
                raise AccountEditConflict("Controller account identities do not match the saved metadata")
            with coordinator.metadata_change_guard(accounts):
                self._atomic_write(data)
                coordinator.replace_accounts(accounts)
                self._expected_server_revision = hashlib.sha256(data).hexdigest()
            return self.snapshot()
        finally:
            lock.release()

    def _atomic_write(self, data: bytes) -> None:
        fd = -1
        temp: str | None = None
        try:
            fd, temp = tempfile.mkstemp(prefix=".accounts-", suffix=".tmp", dir=self.path.parent)
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            if os.name != "nt":
                parent_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
        finally:
            if fd != -1:
                os.close(fd)
            if temp is not None and os.path.exists(temp):
                os.unlink(temp)
