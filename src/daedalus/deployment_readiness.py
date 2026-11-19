"""Strictly read-only live-deployment preflight, no credential or game access.

This audit cannot authorize production: it exposes unsafe runtime prerequisites
without ever reading a saved cookie, password, email, private task payload,
secret-store item, Gameforge page, or real-game network endpoint.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path
from urllib.parse import quote

from daedalus.task_control import default_task_ledger_path


def _keyring_location() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "keyrings"


def _durable_keyring_evidence(directory: Path) -> str:
    """Files show possible durability, never prove an unlocked collection."""
    try:
        if directory.is_symlink() or not directory.is_dir():
            return "not_provisioned_or_unknown"
        for path in directory.glob("*.keyring"):
            if path.is_symlink():
                return "unsafe_keyring_file"
            if path.is_file():
                mode = path.stat().st_mode
                if os.name != "nt" and mode & (stat.S_IRWXG | stat.S_IRWXO):
                    return "unsafe_keyring_file"
                return "encrypted_collection_file_present_unverified"
    except OSError:
        return "not_provisioned_or_unknown"
    return "volatile_session_only_or_unprovisioned"


def _systemd_store_evidence(directory: Path) -> str:
    """Inspect encrypted file metadata; never read ciphertext or the key."""
    try:
        if directory.is_symlink() or not directory.is_dir():
            return "systemd_encrypted_store_unavailable"
        mode = directory.stat().st_mode
        if os.name != "nt" and mode & (stat.S_IRWXG | stat.S_IRWXO):
            return "unsafe_encrypted_store_permissions"
        items = list(directory.glob("*.secret"))
        if not items:
            return "systemd_encrypted_store_unavailable"
        for item in items:
            if item.is_symlink() or not item.is_file():
                return "unsafe_encrypted_store_permissions"
            if os.name != "nt" and item.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                return "unsafe_encrypted_store_permissions"
        return "host_encrypted_collection_present_unverified"
    except OSError:
        return "systemd_encrypted_store_unavailable"


def _ledger_evidence(path: Path) -> dict[str, object]:
    """Read-only SELECT, no sqlite journal, no file creation or identifiers."""
    if path.is_symlink() or path.parent.is_symlink():
        return {"status": "unsafe_path", "unresolved_requests": None}
    if not path.exists():
        return {"status": "absent", "unresolved_requests": None}
    try:
        if not path.is_file():
            return {"status": "invalid", "unresolved_requests": None}
        if os.name != "nt" and path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            return {"status": "unsafe_permissions", "unresolved_requests": None}
        uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1) as conn:
            conn.execute("PRAGMA query_only=ON")
            row = conn.execute(
                "SELECT COUNT(*) FROM requests WHERE status IN ('dispatching','unconfirmed')"
            ).fetchone()
            count = int(row[0])
        return {"status": "unresolved" if count else "clear",
                "unresolved_requests": count}
    except (OSError, sqlite3.Error, ValueError):
        return {"status": "unavailable", "unresolved_requests": None}


def deployment_preflight(*, ledger_path: str | Path | None = None,
                         keyring_directory: str | Path | None = None,
                         protected_store_directory: str | Path | None = None) -> dict[str, object]:
    """Only owner-local metadata; production approval always requires a human."""
    ledger = Path(ledger_path).expanduser() if ledger_path is not None else default_task_ledger_path()
    keyrings = (Path(keyring_directory).expanduser()
                if keyring_directory is not None else _keyring_location())
    receipt = _ledger_evidence(ledger)
    systemd_dir = (protected_store_directory if protected_store_directory is not None
                   else os.environ.get("DAEDALUS_PROTECTED_STORE_DIR"))
    keyring = (
        _systemd_store_evidence(Path(systemd_dir)) if systemd_dir
        else _durable_keyring_evidence(keyrings)
    )
    unsafe = (
        receipt["status"] != "clear"
        or keyring not in {
            "encrypted_collection_file_present_unverified",
            "host_encrypted_collection_present_unverified",
        }
    )
    return {
        "status": "blocked" if unsafe else "requires_owner_acceptance",
        "task_ledger": receipt,
        "keyring_durability": keyring,
        "native_mac_real_login": "owner_test_not_asserted",
        "real_worker_rebind": "owner_test_not_asserted",
        "real_task_side_effects": "owner_test_not_asserted",
        "keyring_after_reboot": "owner_test_not_asserted",
        "production_cutover_authorized": False,
        "network_requests_performed": 0,
        "credential_values_read": 0,
    }
