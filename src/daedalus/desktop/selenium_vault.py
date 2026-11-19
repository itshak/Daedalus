"""Mac-only encryption for a server-persisted, unreadable Gameforge login.

Only the originating Mac Keychain stores the AES-256 key. HTTPS API responses
contain an opaque AEAD envelope, never plaintext email or password.
"""
from __future__ import annotations

import base64
import json
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from daedalus.desktop.selenium_auth import GameforgeCredentials, SeleniumLoginUnavailable
from daedalus.desktop.selenium_credentials import (
    LoginCredentialError,
    _keyring,
    _slot,
)
from daedalus.login_vault import LoginVaultUnavailable, _decoded, validate_login_vault

_KEY_SERVICE = "io.github.itshak.daedalus.gameforge.login-vault-key.v1"
_AAD_PREFIX = b"Daedalus Gameforge login vault v1\x00"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _vault_key(slot: str, *, create: bool) -> bytes | None:
    try:
        keyring = _keyring()
        stored = keyring.get_password(_KEY_SERVICE, slot)
        if stored is None:
            if not create:
                return None
            key = secrets.token_bytes(32)
            keyring.set_password(_KEY_SERVICE, slot, _encode(key))
            return key
        return _decoded(stored, minimum=32, maximum=32)
    except Exception as exc:
        raise LoginCredentialError("Unable to unlock this Mac's encrypted login vault") from exc


def seal_login(
    origin: str, account_id: str, world: str, credentials: GameforgeCredentials,
) -> dict[str, object]:
    if not isinstance(credentials, GameforgeCredentials):
        raise LoginCredentialError("A validated Gameforge login is required")
    slot = _slot(origin, account_id, world)
    key = _vault_key(slot, create=True)
    if key is None:
        raise LoginCredentialError("Mac Keychain vault key unavailable")
    nonce = secrets.token_bytes(12)
    payload = json.dumps(
        {"email": credentials.email, "password": credentials.password},
        separators=(",", ":"),
    ).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, payload, _AAD_PREFIX + slot.encode("ascii"))
    return {"version": 1, "nonce": _encode(nonce),
            "ciphertext": _encode(ciphertext), "confirmed": True}


def unseal_login(
    origin: str, account_id: str, world: str, envelope: object,
) -> GameforgeCredentials | None:
    slot = _slot(origin, account_id, world)
    key = _vault_key(slot, create=False)
    if key is None:
        return None
    try:
        valid = validate_login_vault(envelope)
        nonce = _decoded(valid["nonce"], minimum=12, maximum=12)
        ciphertext = _decoded(valid["ciphertext"], minimum=17, maximum=4096)
        clear = AESGCM(key).decrypt(
            nonce, ciphertext, _AAD_PREFIX + slot.encode("ascii"),
        )
        parsed = json.loads(clear)
        if not isinstance(parsed, dict) or set(parsed) != {"email", "password"}:
            raise ValueError("Invalid login content")
        return GameforgeCredentials(parsed["email"], parsed["password"])
    except (LoginVaultUnavailable, InvalidTag, ValueError, TypeError,
            SeleniumLoginUnavailable) as exc:
        raise LoginCredentialError("The saved server login cannot be decrypted on this Mac") from exc
