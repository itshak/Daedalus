"""Bounded nonsecret administrative status shared by controller and desktop."""
from __future__ import annotations

from daedalus.accounts import Account

FIELDS = frozenset({"telegram", "discord", "proxy_enabled", "proxy_protocol",
                    "proxy_port", "proxy_auth", "challenge_provider", "registered_extensions"})


def validate_admin_status(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("Invalid administrative status")
    if (any(value[k] not in ("configured", "unsupported", "not_configured")
            for k in ("telegram", "discord"))
            or type(value["proxy_enabled"]) is not bool
            or value["proxy_protocol"] not in (None, "http", "https", "socks4", "socks5", "socks5h")
            or (value["proxy_port"] is not None and
                (type(value["proxy_port"]) is not int or not 1 <= value["proxy_port"] <= 65535))
            or (value["proxy_auth"] is not None and type(value["proxy_auth"]) is not bool)
            or value["challenge_provider"] not in ("default", "custom", "9kw.eu", "telegram", "unknown")
            or (value["registered_extensions"] is not None and
                (type(value["registered_extensions"]) is not int or not 0 <= value["registered_extensions"] <= 1000))
            or (not value["proxy_enabled"] and any(value[k] is not None for k in
                ("proxy_protocol", "proxy_port", "proxy_auth")))):
        raise ValueError("Invalid administrative status")
    return dict(value)


def scoped_admin_status(account: Account, response: dict[str, object]) -> dict[str, object]:
    if (str(response.get("world", "")).casefold() != account.world.casefold()
            or str(response.get("username", "")).casefold() != account.player.casefold()):
        raise ValueError("Administrative status belongs to another account")
    return {"account_id": account.id, "settings": validate_admin_status(response.get("settings"))}
