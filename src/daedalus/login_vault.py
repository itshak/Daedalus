"""Server-side persistence of client-sealed Gameforge login material.

The backend never receives or reconstructs a plaintext Gameforge password.
Ciphertext is stored in the existing protected account-bound OS keyring and
can be decrypted only by the Mac that owns its separately stored vault key.
"""
from __future__ import annotations

import base64
import json
import re

from daedalus.accounts import Account
from daedalus.saved_session_recovery import (
    CredentialStore,
    SavedSessionUnavailable,
    _account_key,
    _email_binding,
    _store,
)

_VAULT_SERVICE = "io.github.itshak.daedalus.gameforge.login-vault.v1"
_B64 = re.compile(r"[A-Za-z0-9_-]+\Z")


class LoginVaultUnavailable(RuntimeError):
    """Sanitized, account-scoped secret store or payload failure."""


def _decoded(value: object, *, minimum: int, maximum: int) -> bytes:
    if not isinstance(value, str) or len(value) > 6000 or not _B64.fullmatch(value):
        raise LoginVaultUnavailable("Invalid sealed login material")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise LoginVaultUnavailable("Invalid sealed login material") from exc
    if not minimum <= len(raw) <= maximum:
        raise LoginVaultUnavailable("Invalid sealed login material")
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
        raise LoginVaultUnavailable("Invalid sealed login material")
    return raw


def validate_login_vault(value: object, *, confirmed: bool = False) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LoginVaultUnavailable("Invalid sealed login material")
    expected = {"version", "nonce", "ciphertext"}
    if confirmed:
        expected.add("confirmed")
    if set(value) != expected or type(value.get("version")) is not int or value["version"] != 1:
        raise LoginVaultUnavailable("Invalid sealed login material")
    if confirmed and value["confirmed"] is not True:
        raise LoginVaultUnavailable("Explicit saved-login consent is required")
    _decoded(value.get("nonce"), minimum=12, maximum=12)
    _decoded(value.get("ciphertext"), minimum=17, maximum=4096)
    return {k: value[k] for k in ("version", "nonce", "ciphertext")}


def read_login_vault(
    account: Account, *, credential_store: CredentialStore | None = None,
) -> dict[str, object] | None:
    try:
        raw = _store(credential_store).get_password(
            _VAULT_SERVICE, _account_key(account),
        )
        if raw is None:
            return None
        return validate_login_vault(json.loads(raw))
    except LoginVaultUnavailable:
        raise
    except Exception as exc:
        raise LoginVaultUnavailable("Sealed account login cannot be read") from exc


def write_login_vault(
    account: Account, value: object, *, credential_store: CredentialStore | None = None,
) -> None:
    if not account.enabled:
        raise LoginVaultUnavailable("Disabled account cannot save a login")
    material = validate_login_vault(value, confirmed=True)
    try:
        # Only an existing, protected and independently attested email binding
        # permits this account's sealed login record to be saved.
        _email_binding(account, credential_store)
        _store(credential_store).set_password(
            _VAULT_SERVICE, _account_key(account),
            json.dumps(material, separators=(",", ":")),
        )
    except SavedSessionUnavailable as exc:
        raise LoginVaultUnavailable("Verified account binding is unavailable") from exc
    except Exception as exc:
        raise LoginVaultUnavailable("Sealed account login cannot be saved") from exc
