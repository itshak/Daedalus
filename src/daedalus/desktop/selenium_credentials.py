"""Per-account, exact-backend Gameforge credentials and session cache in OS Keychain.

Original IkaBot stores login data in config.ini and tokens.json; Daedalus
preserves restore-first Selenium behavior but never writes either plaintext
file. No backend API endpoint accepts these passwords or cached lobby cookies.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from daedalus.client import _validated_url
from daedalus.desktop.legacy_selenium.tokens import sanitize_cookie, token_expired

_SERVICE = "io.github.itshak.daedalus.gameforge"
_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z", re.IGNORECASE)
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+\Z")
_MAX_SESSION = 65_536


class GameforgeCredentialError(RuntimeError):
    """Sanitized local Keychain/configuration error, never contains a secret."""


@dataclass(frozen=True, repr=False)
class GameforgeCredentials:
    email: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.email, str) or len(self.email) > 320
            or not _EMAIL.fullmatch(self.email)
            or not isinstance(self.password, str)
            or not 1 <= len(self.password) <= 2048
            or any(c in self.password for c in "\x00\r\n")
        ):
            raise GameforgeCredentialError("A valid Gameforge email and password are required")


class GameforgeKeychain:
    """Only ever retrieves secrets bound to an exact backend/account/world/player."""

    def __init__(
        self, backend_url: str, account_id: str, world: str, player: str,
        *, provider: Any = None,
    ) -> None:
        try:
            origin = _validated_url(backend_url)
        except ValueError as exc:
            raise GameforgeCredentialError("Invalid Daedalus backend origin") from exc
        if (
            not origin.startswith("https://")
            or not isinstance(account_id, str) or not 1 <= len(account_id) <= 128
            or not isinstance(world, str) or _WORLD.fullmatch(world) is None
            or not isinstance(player, str) or not 1 <= len(player) <= 80
        ):
            raise GameforgeCredentialError("Exact HTTPS backend and account/world are required")
        # Never expose account/world/player or backend identity in keyring usernames.
        scope = json.dumps(
            [origin, account_id, world.casefold(), player.casefold()],
            ensure_ascii=True, separators=(",", ":"),
        )
        self._scope = hashlib.sha256(scope.encode("ascii")).hexdigest()
        self.world_host = f"{world.casefold()}.ikariam.gameforge.com"
        self._provider = provider

    def _keyring(self) -> Any:
        if self._provider is not None:
            return self._provider
        try:
            import keyring
        except ImportError as exc:
            raise GameforgeCredentialError("macOS Keychain integration is unavailable") from exc
        return keyring

    def _name(self, kind: str) -> str:
        return f"{kind}:{self._scope}"

    def _get(self, kind: str) -> str | None:
        try:
            return self._keyring().get_password(_SERVICE, self._name(kind))
        except Exception as exc:
            raise GameforgeCredentialError("Unable to read the saved Gameforge Keychain item") from exc

    def _put(self, kind: str, value: str) -> None:
        try:
            self._keyring().set_password(_SERVICE, self._name(kind), value)
        except Exception as exc:
            raise GameforgeCredentialError("Unable to store the Gameforge Keychain item") from exc

    def _delete(self, kind: str) -> None:
        try:
            provider = self._keyring()
            if provider.get_password(_SERVICE, self._name(kind)) is not None:
                provider.delete_password(_SERVICE, self._name(kind))
        except Exception as exc:
            raise GameforgeCredentialError("Unable to forget the Gameforge Keychain item") from exc

    def get_credentials(self) -> GameforgeCredentials | None:
        raw = self._get("login")
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if type(data) is not dict or set(data) != {"email", "password"}:
                raise ValueError("Unexpected stored login shape")
            return GameforgeCredentials(data["email"], data["password"])
        except (ValueError, TypeError, GameforgeCredentialError) as exc:
            raise GameforgeCredentialError("Saved Gameforge login is invalid") from exc

    def save_credentials(self, credentials: GameforgeCredentials) -> None:
        self._put(
            "login", json.dumps(
                {"email": credentials.email, "password": credentials.password},
                ensure_ascii=True, separators=(",", ":"),
            ),
        )

    def forget_credentials(self) -> None:
        self._delete("login")

    def _validated_session(self, url: str, cookies: object) -> dict[str, object]:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != self.world_host
            or parsed.username or parsed.password or parsed.port
            or not isinstance(cookies, list) or len(cookies) > 48
        ):
            raise GameforgeCredentialError("Saved world session does not match the account")
        normalized: list[dict[str, Any]] = []
        allowed = {self.world_host, "lobby.ikariam.gameforge.com"}
        for cookie in cookies:
            if type(cookie) is not dict:
                raise GameforgeCredentialError("Invalid saved Gameforge cookie")
            domain = str(cookie.get("domain", "")).lstrip(".").lower()
            value = cookie.get("value")
            if (
                domain not in allowed or cookie.get("secure") is not True
                or not isinstance(cookie.get("name"), str)
                or not isinstance(value, str) or len(value) > 4096
            ):
                # Skip unrelated tracking/third-party/unsafe cookies; never store them.
                continue
            try:
                normalized.append(sanitize_cookie(cookie))
            except (TypeError, ValueError, KeyError) as exc:
                raise GameforgeCredentialError("Invalid saved Gameforge cookie") from exc
        if not normalized:
            raise GameforgeCredentialError("No secure Gameforge world cookies available")
        document = {"url": url, "cookies": normalized}
        if len(json.dumps(document, ensure_ascii=True).encode("utf-8")) > _MAX_SESSION:
            raise GameforgeCredentialError("Gameforge session exceeds secure cache limits")
        return document

    def save_session(self, url: str, cookies: list[dict[str, object]]) -> None:
        document = self._validated_session(url, cookies)
        self._put("session", json.dumps(document, separators=(",", ":"), ensure_ascii=True))

    def get_session(self) -> dict[str, object] | None:
        raw = self._get("session")
        if raw is None:
            return None
        try:
            if len(raw.encode("utf-8")) > _MAX_SESSION:
                raise ValueError("Saved session too large")
            data = json.loads(raw)
            if type(data) is not dict or set(data) != {"url", "cookies"}:
                raise ValueError("Unknown stored session format")
            cleaned = self._validated_session(data["url"], data["cookies"])
            return None if token_expired(cleaned) else cleaned
        except (ValueError, TypeError, GameforgeCredentialError) as exc:
            raise GameforgeCredentialError("Saved Gameforge session is invalid") from exc

    def forget_session(self) -> None:
        self._delete("session")

    def forget_all(self) -> None:
        self._delete("login")
        self._delete("session")
