"""One-time encrypted native-Mac browser cookie exchange, no automated login.

The client obtains an ephemeral Curve25519 public key from the same TLS
origin that it authenticated with its Daedalus API bearer. The encrypted
world cookie is never returned, printed, saved in desktop preferences or
included in a plaintext REST field. An owned worker, if present, independently
verifies player identity and retains its lease before replacing its session.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.auth_assistance import AssistanceConflict
from daedalus.saved_session_recovery import (
    CredentialStore,
    SavedSessionUnavailable,
    _email_binding,
    _validated_world_cookie,
    bind_saved_email,
    bind_world_cookie,
    stage_world_cookie,
    unbind_saved_email,
)
from daedalus.session_monitor import ExistingSessionRecoveryMonitor, MonitoringUnavailable

_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\Z")
_SAFE_B64 = re.compile(r"[A-Za-z0-9_-]+={0,2}\Z")
_INFO = b"Daedalus Mac browser handoff v1"


class NativeHandoffUnavailable(RuntimeError):
    """Audited error text only; never expose crypto or Gameforge details."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: object, *, limit: int) -> bytes:
    if not isinstance(value, str) or len(value) > limit or not _SAFE_B64.fullmatch(value):
        raise NativeHandoffUnavailable("Invalid encrypted handoff envelope")
    try:
        result = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise NativeHandoffUnavailable("Invalid encrypted handoff envelope") from exc
    if _encode(result) != value.rstrip("="):
        raise NativeHandoffUnavailable("Noncanonical encrypted handoff envelope")
    return result


def _aad(ticket_id: str, account: Account) -> bytes:
    return json.dumps(
        ["daedalus-mac-browser-v1", ticket_id, account.id,
         account.world.casefold(), account.player.casefold()],
        separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def _session_key(private: x25519.X25519PrivateKey, peer: bytes, aad: bytes) -> bytes:
    if len(peer) != 32:
        raise NativeHandoffUnavailable("Invalid encrypted handoff public key")
    try:
        shared = private.exchange(x25519.X25519PublicKey.from_public_bytes(peer))
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=_INFO + aad).derive(shared)
    except (ValueError, TypeError) as exc:
        raise NativeHandoffUnavailable("Invalid encrypted handoff public key") from exc


def encrypt_mac_world_session(
    challenge: dict[str, object], account: Account, cookie: str, *, email: str = "",
) -> dict[str, object]:
    """Mac only: opaque envelope, no plaintext cookie or email in JSON/HTTP.

    Caller must use a TLS-validated Daedalus API connection and retain this
    value in memory only until the one-time POST completes.
    """
    ticket = challenge.get("ticket_id")
    try:
        valid_ticket = isinstance(ticket, str) and str(uuid.UUID(ticket)) == ticket
    except (TypeError, ValueError, AttributeError):
        valid_ticket = False
    if (challenge.get("account_id") != account.id or
            challenge.get("world") != account.world or not valid_ticket):
        raise NativeHandoffUnavailable("Handoff is not bound to the selected account")
    _validated_world_cookie(cookie)
    if not isinstance(email, str) or len(email) > 320:
        raise NativeHandoffUnavailable("Invalid optional Gameforge email")
    aad = _aad(ticket, account)
    public = _decode(challenge.get("public_key"), limit=60)
    private = x25519.X25519PrivateKey.generate()
    key = _session_key(private, public, aad)
    nonce = secrets.token_bytes(12)
    payload = json.dumps({"cookie": cookie, "email": email},
                         separators=(",", ":")).encode("utf-8")
    if len(payload) > 5000:
        raise NativeHandoffUnavailable("World session is too large")
    encrypted = AESGCM(key).encrypt(nonce, payload, aad)
    return {
        "confirmed": True,
        "client_key": _encode(private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )),
        "nonce": _encode(nonce),
        "ciphertext": _encode(encrypted),
    }


@dataclass
class _Pending:
    account: Account
    private: x25519.X25519PrivateKey
    deadline: float
    recovery_ticket: str | None


class NativeBrowserHandoff:
    """Opt-in backend exchange bound to exact configured account and owner.

    An incoming envelope can stage only an UNVERIFIED cookie for the owned
    worker, or verify and bind under a fresh lease when no worker owns the
    account. It cannot start a worker or a background task by itself.
    """

    def __init__(
        self, accounts: list[Account], coordinator: AccountSessionCoordinator, *,
        monitor: ExistingSessionRecoveryMonitor | None = None,
        dedicated_worker: object | None = None,
        credential_store: CredentialStore | None = None,
        restore: Callable | None = None,
        clock: Callable[[], float] = time.monotonic,
        ttl_seconds: int = 600,
    ) -> None:
        if not 60 <= ttl_seconds <= 900:
            raise ValueError("Browser handoff timeout must be between 60 and 900 seconds")
        if not coordinator.matches_accounts(accounts):
            raise ValueError("Native handoff accounts do not match the session owner")
        if (monitor is None) != (dedicated_worker is None):
            raise ValueError("Owned worker recovery requires a matching monitor")
        if dedicated_worker is not None and (
            dedicated_worker.account.id not in coordinator.account_ids
            or dedicated_worker.coordinator is not coordinator
            or monitor._dedicated_worker is not dedicated_worker
        ):
            raise ValueError("Native handoff cannot attach to a foreign worker")
        self.accounts = {a.id: a for a in accounts}
        self.owner = coordinator
        self.monitor = monitor
        self.worker = dedicated_worker
        self.credentials = credential_store
        self.restore = restore
        self.clock = clock
        self.ttl = ttl_seconds
        self._lock = threading.RLock()
        self._pending: dict[str, _Pending] = {}

    def _cleanup(self) -> None:
        for tid in tuple(self._pending):
            if self.clock() >= self._pending[tid].deadline:
                del self._pending[tid]

    def start(self, account_id: str, *, confirmed: bool) -> dict[str, object]:
        if confirmed is not True:
            raise NativeHandoffUnavailable("Explicit Mac browser-login approval is required")
        account = self.accounts.get(account_id)
        if account is None or not account.enabled or _WORLD.fullmatch(account.world.casefold()) is None:
            raise NativeHandoffUnavailable("An enabled exact game account is required")
        with self._lock:
            self._cleanup()
            if any(p.account.id == account_id for p in self._pending.values()):
                raise NativeHandoffUnavailable("A native login is already pending for this account")
            if len(self._pending) >= 8:
                raise NativeHandoffUnavailable("Too many pending browser logins")
            recovery_ticket = None
            if self.worker is not None and self.worker.account.id == account_id:
                try:
                    existing = self.monitor.broker.snapshot(account_id).get("ticket")
                    if isinstance(existing, dict) and existing.get("state") == "waiting_operator":
                        # A cancelled Mac browser can retry while the same
                        # worker lease remains intentionally paused. Recheck
                        # idempotency and existing engine operations before
                        # permitting even this non-mutating retry.
                        state = self.monitor.controller.list_tasks(account_id)
                        if (any(t.get("status") in {"running", "stopping"}
                                for t in state["engine_tasks"])
                                or any(t.get("status") in {"dispatching", "unconfirmed"}
                                       for t in state["requests"])):
                            raise NativeHandoffUnavailable(
                                "Running or uncertain tasks must be reconciled before login"
                            )
                        recovery_ticket = existing["ticket_id"]
                    else:
                        result = self.monitor.prepare_dedicated_recovery(
                            account_id, confirmed=True,
                        )
                        recovery_ticket = result["ticket"]["ticket_id"]
                except (MonitoringUnavailable, AssistanceConflict, ValueError) as exc:
                    raise NativeHandoffUnavailable(
                        "This worker is busy or has an uncertain task; reconcile it before login"
                    ) from exc
            elif self.owner.status(account_id) != "not_connected":
                raise NativeHandoffUnavailable("Another worker owns this game account")
            ticket = str(uuid.uuid4())
            private = x25519.X25519PrivateKey.generate()
            self._pending[ticket] = _Pending(account, private, self.clock() + self.ttl,
                                             recovery_ticket)
            return {
                "status": "browser_login_ready", "account_id": account.id,
                "world": account.world, "ticket_id": ticket,
                "expires_in_seconds": self.ttl,
                "public_key": _encode(private.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )),
            }

    def cancel(self, account_id: str, ticket: str, *, confirmed: bool) -> dict[str, str]:
        if confirmed is not True:
            raise NativeHandoffUnavailable("Cancellation requires confirmation")
        with self._lock:
            found = self._pending.get(ticket)
            if found is None or found.account.id != account_id:
                raise NativeHandoffUnavailable("Browser login has expired")
            del self._pending[ticket]
            # A dedicated worker may remain paused; do not automatically resume
            # it or replay tasks after a cancelled human challenge.
            return {"account_id": account_id, "status": "browser_login_cancelled"}

    def complete(self, account_id: str, ticket: str, payload: dict[str, object]) -> dict[str, str]:
        if (type(payload) is not dict or set(payload) != {
            "confirmed", "client_key", "nonce", "ciphertext",
        } or payload["confirmed"] is not True):
            raise NativeHandoffUnavailable("Explicit encrypted login submission is required")
        with self._lock:
            # Burn the ticket *before* decryption or any game request. Even a
            # timeout or incorrect identity must never admit duplicate submits.
            pending = self._pending.get(ticket)
            if pending is None or pending.account.id != account_id:
                raise NativeHandoffUnavailable("Browser handoff is expired or already consumed")
            del self._pending[ticket]
            if self.clock() >= pending.deadline:
                raise NativeHandoffUnavailable("Browser handoff is expired or already consumed")
            account = pending.account
            aad = _aad(ticket, account)
            key = _session_key(pending.private,
                               _decode(payload["client_key"], limit=60), aad)
            nonce = _decode(payload["nonce"], limit=20)
            ciphertext = _decode(payload["ciphertext"], limit=7000)
            if len(nonce) != 12 or not 32 <= len(ciphertext) <= 5500:
                raise NativeHandoffUnavailable("Invalid encrypted handoff envelope")
            try:
                plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
                data = json.loads(plaintext)
                if not isinstance(data, dict) or set(data) != {"cookie", "email"}:
                    raise ValueError("Invalid payload")
                cookie = _validated_world_cookie(data["cookie"])
                email = data["email"]
                if not isinstance(email, str) or len(email) > 320:
                    raise ValueError("Invalid email")
            except Exception as exc:
                raise NativeHandoffUnavailable(
                    "Encrypted session is invalid or belongs to a different account"
                ) from exc
            # Avoid leaking any cookie or email to logs, responses or errors.
            new_email_binding = False
            try:
                try:
                    bound = _email_binding(account, self.credentials)
                except SavedSessionUnavailable:
                    if not email:
                        raise NativeHandoffUnavailable(
                            "A Gameforge email is required for first-time account binding"
                        ) from None
                    bind_saved_email(account, email, credential_store=self.credentials)
                    new_email_binding = True
                    bound = email
                if email and email.casefold() != bound.casefold():
                    raise NativeHandoffUnavailable(
                        "Gameforge email differs from the existing account binding"
                    )
                if pending.recovery_ticket is not None:
                    if self.worker is None or self.worker.account != account:
                        raise NativeHandoffUnavailable("Worker owner changed during login")
                    stage_world_cookie(account, cookie, confirmed=True,
                                       credential_store=self.credentials)
                    self.monitor.broker.approve(
                        account_id, pending.recovery_ticket, confirmed=True,
                    )
                    outcome = self.monitor.rebind_dedicated_worker(
                        account_id, pending.recovery_ticket, confirmed=True,
                    )
                    return {"account_id": account_id, "status": outcome["status"]}
                # No dedicated worker: never start one implicitly. Verify on the
                # server with exactly this account's fresh lease and game page.
                kwargs = {"restore": self.restore} if self.restore else {}
                result = bind_world_cookie(
                    account, self.owner, cookie, confirmed=True,
                    credential_store=self.credentials, **kwargs,
                )
                return {"account_id": account_id, "status": result["status"]}
            except Exception as exc:
                if new_email_binding:
                    try:
                        unbind_saved_email(account, credential_store=self.credentials)
                    except SavedSessionUnavailable:
                        pass  # Report safe failure; do not log account/email
                if isinstance(exc, NativeHandoffUnavailable):
                    raise
                raise NativeHandoffUnavailable(
                    "Server did not verify the exact game account; login was not accepted"
                ) from exc
