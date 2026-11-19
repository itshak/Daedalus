"""Original IkaBot token validation and cookie normalization, without its
insecure plaintext TokenStore. Daedalus provides a Keychain-backed store.
"""
from __future__ import annotations

import time
from typing import Any

_COOKIE_KEYS = ("name", "value", "path", "domain", "secure", "httpOnly")

def sanitize_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {key: cookie[key] for key in _COOKIE_KEYS if key in cookie}
    expiry = cookie.get("expiry")
    if expiry is not None:
        result["expiry"] = int(expiry)
    same_site = cookie.get("sameSite")
    if same_site in ("Strict", "Lax", "None"):
        result["sameSite"] = same_site
    return result

def token_expired(token: dict) -> bool:
    expiries: list[int] = []
    for cookie in token.get("cookies", []):
        expiry = cookie.get("expiry")
        if expiry is None:
            return False
        expiries.append(int(expiry))
    return bool(expiries) and max(expiries) <= time.time()
