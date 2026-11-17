"""Secret-free local multi-account configuration for Daedalus.

Passwords, Gameforge tokens, and session cookies are deliberately not supported
in this file. A future credential store provides those separately.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_WORLD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,63}\Z")
_ALLOWED_ACCOUNT = frozenset({"id", "world", "player", "label", "enabled"})
_ALLOWED_ROOT = frozenset({"schema", "accounts"})


class AccountConfigError(ValueError):
    """Invalid account metadata; this file must never contain secrets."""


@dataclass(frozen=True)
class Account:
    id: str
    world: str
    player: str
    label: str
    enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "session_status": "not_connected"}


def default_accounts_path() -> Path:
    """Read platform-compatible XDG location; do not create files in the repo."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "daedalus" / "accounts.toml"


def parse_accounts(text: str) -> list[Account]:
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise AccountConfigError("Invalid accounts.toml syntax") from exc
    unknown_root = document.keys() - _ALLOWED_ROOT
    if unknown_root:
        raise AccountConfigError("Unsupported top-level fields: " + ", ".join(sorted(unknown_root)))
    if type(document.get("schema")) is not int or document["schema"] != 1:
        raise AccountConfigError("accounts.toml must declare schema = 1")
    entries: Any = document.get("accounts")
    if not isinstance(entries, list):
        raise AccountConfigError("accounts.toml must contain [[accounts]] entries")
    accounts: list[Account] = []
    ids: set[str] = set()
    identities: set[tuple[str, str]] = set()
    for idx, item in enumerate(entries, 1):
        if not isinstance(item, dict):
            raise AccountConfigError(f"Account #{idx} must be a table")
        unknown = item.keys() - _ALLOWED_ACCOUNT
        if unknown:
            raise AccountConfigError(
                f"Account #{idx}: unsupported fields {', '.join(sorted(unknown))}; "
                "put credentials in protected storage, not accounts.toml"
            )
        account_id = item.get("id")
        world = item.get("world")
        player = item.get("player")
        label = item.get("label", player)
        enabled = item.get("enabled", True)
        if not isinstance(account_id, str) or not _ID.fullmatch(account_id):
            raise AccountConfigError(f"Account #{idx}: invalid id (lowercase letters, digits, - or _)")
        if not isinstance(world, str) or not _WORLD.fullmatch(world):
            raise AccountConfigError(f"Account {account_id}: invalid world")
        if not isinstance(player, str) or not player or len(player) > 80 or not player.isprintable():
            raise AccountConfigError(f"Account {account_id}: invalid player")
        if not isinstance(label, str) or not label or len(label) > 120 or not label.isprintable():
            raise AccountConfigError(f"Account {account_id}: invalid label")
        if type(enabled) is not bool:
            raise AccountConfigError(f"Account {account_id}: enabled must be true or false")
        identity = (world.casefold(), player.casefold())
        if account_id in ids:
            raise AccountConfigError(f"Duplicate account id: {account_id}")
        if identity in identities:
            raise AccountConfigError(f"Duplicate world/player: {world} / {player}")
        accounts.append(Account(account_id, world, player, label, enabled))
        ids.add(account_id)
        identities.add(identity)
    return accounts


def load_accounts(path: str | Path | None = None) -> list[Account]:
    target = Path(path).expanduser() if path is not None else default_accounts_path()
    if path is None and not target.exists():
        return []
    try:
        contents = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise AccountConfigError("Unable to read accounts configuration") from exc
    return parse_accounts(contents)
