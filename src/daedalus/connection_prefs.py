"""Opt-in, owner-private backend preferences; bearer secrets only in OS keyring.

No runtime Gameforge credentials, cookies, or IkaBot saved sessions are read.
A keyring backend is never required for the default ephemeral API client.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from daedalus.client import _validated_url

_SERVICE = "io.github.itshak.daedalus.controller"


class PreferenceError(RuntimeError):
    """A sanitized local preference/secure-credential error."""


def default_connection_path() -> Path:
    parent = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    return parent / "daedalus" / "connection.json"


def _path(path: str | Path | None) -> Path:
    return Path(path).expanduser() if path is not None else default_connection_path()


def load_connection_url(path: str | Path | None = None) -> str | None:
    """Read only a strictly validated URL; never deserialize arbitrary settings."""
    target = _path(path)
    if not target.exists() and not target.is_symlink():
        return None
    if target.is_symlink() or target.parent.is_symlink() or not target.is_file():
        raise PreferenceError("Unsafe connection preferences file")
    try:
        stat = target.stat()
        if os.name != "nt" and stat.st_mode & 0o077:
            raise PreferenceError("Connection preferences must be owner-only")
        if stat.st_size > 2048:
            raise PreferenceError("Connection preferences are oversized")
        document = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"version", "server_url"}:
            raise ValueError("Unexpected connection preferences")
        if document["version"] != 1 or not isinstance(document["server_url"], str):
            raise ValueError("Invalid connection preference version")
        return _validated_url(document["server_url"])
    except PreferenceError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise PreferenceError("Stored connection URL is invalid") from exc


def _save_url(url: str, *, path: str | Path | None = None) -> None:
    target = _path(path)
    parent = target.parent
    if parent.is_symlink() or target.is_symlink():
        raise PreferenceError("Connection preferences must not use symlinks")
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if parent.is_symlink() or not parent.is_dir():
            raise PreferenceError("Connection preferences folder is unsafe")
        if os.name != "nt":
            os.chmod(parent, 0o700)
        # Atomic replace prevents interrupted writes from corrupting settings.
        fd, temporary = tempfile.mkstemp(prefix=".connection-", suffix=".json", dir=parent)
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "server_url": url}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except (OSError, ValueError) as exc:
        raise PreferenceError("Unable to store secure connection preferences") from exc


def _keyring():
    try:
        import keyring
    except ImportError as exc:
        raise PreferenceError("OS keyring support is unavailable") from exc
    return keyring


def remember_connection(url: str, token: str, *, path: str | Path | None = None) -> None:
    """Save URL and OS-keyring token only after an explicit user opt-in."""
    try:
        validated = _validated_url(url)
    except ValueError as exc:
        raise PreferenceError("The backend URL is invalid") from exc
    if not isinstance(token, str) or len(token) < 32 or any(c in token for c in "\r\n\x00"):
        raise PreferenceError("A valid bearer token is required")
    try:
        _keyring().set_password(_SERVICE, validated, token)
    except Exception as exc:
        raise PreferenceError("Unable to save token in the OS keyring") from exc
    try:
        _save_url(validated, path=path)
    except PreferenceError:
        try:
            _keyring().delete_password(_SERVICE, validated)
        except Exception as exc:
            raise PreferenceError(
                "Unable to roll back a saved OS keyring token after settings failure"
            ) from exc
        raise


def saved_connection(path: str | Path | None = None) -> tuple[str, str] | None:
    """On explicit reconnect, obtain the credential from OS keyring only."""
    url = load_connection_url(path)
    if url is None:
        return None
    try:
        token = _keyring().get_password(_SERVICE, url)
    except Exception as exc:
        raise PreferenceError("Unable to read saved token from OS keyring") from exc
    if not isinstance(token, str) or len(token) < 32:
        raise PreferenceError("No saved OS-keyring token for this backend")
    return url, token


def forget_connection(path: str | Path | None = None) -> None:
    target = _path(path)
    url = load_connection_url(path)
    if url is not None:
        try:
            provider = _keyring()
            if provider.get_password(_SERVICE, url) is not None:
                provider.delete_password(_SERVICE, url)
        except Exception as exc:
            # Do not silently claim that credentials were removed.
            raise PreferenceError("Unable to remove saved token from OS keyring") from exc
    if target.exists():
        try:
            target.unlink()
        except OSError as exc:
            raise PreferenceError("Unable to remove saved connection URL") from exc
