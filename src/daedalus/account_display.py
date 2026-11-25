"""Nonsecret display identity shared by desktop tables, account pickers and exports."""

from __future__ import annotations

import re
from collections.abc import Mapping

_IMPORTED = re.compile(r"Imported IkaBot (?:account|identity)(?: [0-9]+)?", re.IGNORECASE)


def account_display_name(account: Mapping[str, object]) -> str:
    """Prefer server-bound email, then meaningful label, then player / ID.

    A legacy importer placeholder is never a useful display identity. Never
    guess an email from account ID, or expose credential data.
    """
    email = account.get("email")
    if (isinstance(email, str) and "@" in email
            and len(email) <= 320
            and not any(char in email for char in "\x00\r\n")):
        return email
    label = account.get("label")
    if (isinstance(label, str) and label.strip()
            and not _IMPORTED.fullmatch(label.strip())):
        return label.strip()
    return str(account.get("player") or account.get("id") or "—")


def account_player_name(account: Mapping[str, object]) -> str:
    """Prefer the actual game player in automation contexts, not import labels."""
    player = account.get("player")
    if (isinstance(player, str) and player.strip()
            and not _IMPORTED.fullmatch(player.strip())):
        return player.strip()
    return account_display_name(account)


def account_player_names(accounts: list[dict[str, object]]) -> dict[str, str]:
    """Disambiguate identical player names without changing account IDs."""
    names = {str(row["id"]): account_player_name(row) for row in accounts}
    counts: dict[str, int] = {}
    for name in names.values():
        counts[name.casefold()] = counts.get(name.casefold(), 0) + 1
    for row in accounts:
        aid = str(row["id"])
        name = names[aid]
        if counts[name.casefold()] > 1:
            world = str(row.get("world") or "world unspecified")
            names[aid] = f"{name} · {world} ({aid})"
    return names
