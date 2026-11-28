"""Mac-owned Gameforge credential storage and explicit legacy warehouse migration.

Never persist Gameforge credentials in Daedalus JSON/TOML or submit them to
the Daedalus backend. OS Keychain entries are isolated by HTTPS backend origin,
exact account identifier and canonical game world. The legacy config.ini is
only inspected when the user explicitly chooses to reuse its existing login.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import os
from pathlib import Path

from daedalus.client import _validated_url
from daedalus.desktop.selenium_auth import GameforgeCredentials, SeleniumLoginUnavailable

_SERVICE = "io.github.itshak.daedalus.gameforge.selenium.v1"


class LoginCredentialError(RuntimeError):
    """Public, sanitized Keychain or legacy configuration error."""


def _slot(origin: str, account_id: str, world: str) -> str:

    # Reuse backend validation for exact trusted URL; auth records cannot
    # follow an SSH tunnel's ephemeral local forwarding port.
    try:
        url = _validated_url(origin)
    except ValueError as exc:
        raise LoginCredentialError("A trusted HTTPS server connection is required") from exc
    if not url.startswith("https://"):
        raise LoginCredentialError("Gameforge credentials require HTTPS backend binding")
    if not isinstance(account_id, str) or not account_id:
        raise LoginCredentialError("Choose a configured account")
    if not isinstance(world, str) or not world:
        raise LoginCredentialError("Choose an exact game world")
    value = json.dumps([url, account_id, world.casefold()], separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _keyring():
    try:
        import keyring
    except ImportError as exc:
        raise LoginCredentialError("macOS Keychain support is not installed") from exc
    from daedalus.shared_keychain import provider
    return provider(keyring)


def get_saved_login(origin: str, account_id: str, world: str) -> GameforgeCredentials | None:
    try:
        raw = _keyring().get_password(_SERVICE, _slot(origin, account_id, world))
    except LoginCredentialError:
        raise
    except Exception as exc:
        raise LoginCredentialError("Unable to read Gameforge login from macOS Keychain") from exc
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"email", "password"}:
            raise ValueError("Unexpected credential shape")
        return GameforgeCredentials(data["email"], data["password"])
    except (ValueError, TypeError, SeleniumLoginUnavailable) as exc:
        raise LoginCredentialError("Saved Gameforge credentials are invalid") from exc


def remember_login(
    origin: str, account_id: str, world: str, credentials: GameforgeCredentials
) -> None:
    if not isinstance(credentials, GameforgeCredentials):
        raise LoginCredentialError("A validated Gameforge login is required")
    slot = _slot(origin, account_id, world)
    try:
        _keyring().set_password(_SERVICE, slot, json.dumps({
            "email": credentials.email, "password": credentials.password,
        }, separators=(",", ":")))
    except Exception as exc:
        raise LoginCredentialError("Unable to save Gameforge login in macOS Keychain") from exc


def forget_login(origin: str, account_id: str, world: str) -> None:
    slot = _slot(origin, account_id, world)
    try:
        keyring = _keyring()
        if keyring.get_password(_SERVICE, slot) is not None:
            keyring.delete_password(_SERVICE, slot)
    except Exception as exc:
        raise LoginCredentialError("Unable to forget Gameforge login in macOS Keychain") from exc


def legacy_warehouse_login(
    account: dict[str, object], *, path: Path | None = None
) -> GameforgeCredentials | None:
    """Opt-in migration from previous local bot: ~/.ikabot/config.ini.

    Strict exact player/label/account-ID alias matching avoids associating
    another player with this Gameforge identity. Nothing is modified in the
    original file. Server-side player attestation remains mandatory.
    """
    target = path or (Path.home() / ".ikabot" / "config.ini")
    try:
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 131072:
            return None
        if os.name == "posix" and target.stat().st_uid != os.getuid():
            return None
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read(target, encoding="utf-8")
        if not parser.has_section("ACCOUNTS"):
            return None
        world = str(account.get("world") or "").casefold()
        legacy_world = parser.get("IKARIAM_LOGIN", "SERVER", fallback="").strip().casefold()
        if legacy_world.startswith("s") and "-" in legacy_world and legacy_world != world:
            return None
        names = {
            str(account.get(key) or "").strip().casefold()
            for key in ("id", "label", "player")
        } - {""}
        matches = [
            value for alias, value in parser.items("ACCOUNTS")
            if alias.strip().casefold() in names
        ]
        if len(matches) != 1:
            return None
        email, separator, password = matches[0].partition(":")
        if not separator or not password.strip():
            password = parser.get("IKARIAM_LOGIN", "PASSWORD", fallback="")
        return GameforgeCredentials(email.strip(), password.strip())
    except (OSError, UnicodeError, ValueError, configparser.Error,
            SeleniumLoginUnavailable):
        return None


def legacy_saved_session(
    email: str, world: str, *, path: Path | None = None
) -> tuple[str, list[dict[str, object]]] | None:
    """Read only a matching, unexpired old-bot session for headless RESTORE.

    Previous IkaBot stored per-email Gameforge cookies in tokens.json. Limit
    domains to exactly the chosen world or official Gameforge lobby, and never
    forward this file over Daedalus API or write another plaintext copy.
    """
    import time
    from urllib.parse import urlsplit

    target = path or (Path.home() / ".ikabot" / "tokens.json")
    try:
        if (target.is_symlink() or not target.is_file()
                or target.stat().st_size > 1_048_576
                or (os.name == "posix" and target.stat().st_uid != os.getuid())):
            return None
        if not isinstance(email, str) or not isinstance(world, str):
            return None
        host = f"{world.casefold()}.ikariam.gameforge.com"
        entry = json.loads(target.read_text(encoding="utf-8")).get(email)
        if not isinstance(entry, dict):
            return None
        url = entry.get("url")
        if (not isinstance(url, str) or len(url) > 2048
                or urlsplit(url).scheme != "https"
                or urlsplit(url).hostname != host):
            return None
        raw_cookies = entry.get("cookies")
        if not isinstance(raw_cookies, list) or len(raw_cookies) > 100:
            return None
        filtered: list[dict[str, object]] = []
        for cookie in raw_cookies:
            if not isinstance(cookie, dict):
                continue
            domain = str(cookie.get("domain") or "").lstrip(".").casefold()
            if domain not in {host, "lobby.ikariam.gameforge.com"}:
                continue
            expiry = cookie.get("expiry")
            if expiry is not None and (
                type(expiry) not in (int, float) or expiry <= time.time()
            ):
                continue
            if (not isinstance(cookie.get("name"), str)
                    or not isinstance(cookie.get("value"), str)
                    or not cookie["name"] or len(cookie["value"]) > 4096):
                continue
            filtered.append({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": domain,
                "path": str(cookie.get("path") or "/"),
                "secure": cookie.get("secure") is True,
                "httpOnly": cookie.get("httpOnly") is True,
            })
        matches = [
            c for c in filtered if c["name"] == "ikariam"
            and c["domain"] == host and c["secure"] is True
        ]
        return (url, filtered) if len(matches) == 1 else None
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return None
