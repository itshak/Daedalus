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
