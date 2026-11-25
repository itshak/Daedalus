"""One-use encrypted, host-global provider configuration for the reviewed UI.

Only the authenticated worker decrypts credentials. Existing upstream global
notification persistence is used intentionally, with explicit global consent.
No provider response, credential, URL or exception is returned to the caller.
"""
import base64
import json
import re
import secrets
import threading
import time

from ikabot.helpers import sessionStorage

_PROVIDER = {"telegram", "discord"}
_ACCOUNT = re.compile(r"[a-z][a-z0-9_-]{0,47}")
_TICKET = re.compile(r"[A-Za-z0-9_-]{43}")
_LOCK = threading.Lock()
_PENDING = {}
_TTL = 120


def _encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value, maximum):
    if not isinstance(value, str) or not 0 < len(value) <= maximum or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid encrypted provider configuration")
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _encode(raw) != value:
        raise ValueError("Invalid encrypted provider configuration")
    return raw


def _identity(session, account, provider):
    if not isinstance(account, str) or not _ACCOUNT.fullmatch(account) or provider not in _PROVIDER:
        raise ValueError("Invalid provider configuration scope")
    return (f"s{session.mundo}-{session.servidor}".casefold(), session.username.casefold(), account, provider)


def _prune(now):
    for ticket in list(_PENDING):
        if _PENDING[ticket][2] <= now:
            del _PENDING[ticket]


def begin(session, account, provider):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    identity = _identity(session, account, provider)
    private = ec.generate_private_key(ec.SECP256R1())
    ticket = secrets.token_urlsafe(32)
    with _LOCK:
        _prune(time.monotonic())
        while len(_PENDING) >= 32:
            del _PENDING[next(iter(_PENDING))]
        _PENDING[ticket] = (identity, private, time.monotonic() + _TTL)
    return {"account_id": account, "provider": provider, "ticket_id": ticket,
            "public_key": _encode(private.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)),
            "expires_in": _TTL, "scope": "worker_global", "version": 1}


def _aad(ticket, account, provider):
    return ("daedalus-notification-v1:" + ticket + ":" + account + ":" + provider).encode("ascii")


def _provider_accepts(provider, url, body):
    # Avoid urllib3/requests URL debug logging: both provider URLs contain
    # credentials. This direct TLS connection has no redirect or proxy path.
    import http.client
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    allowed = {"api.telegram.org"} if provider == "telegram" else {"discord.com", "discordapp.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.netloc != parsed.hostname:
        raise ValueError("Invalid provider endpoint")
    conn = http.client.HTTPSConnection(parsed.hostname, timeout=10)
    try:
        conn.request("POST", parsed.path, body=json.dumps(body).encode("utf-8"),
                     headers={"Content-Type": "application/json"})
        reply = conn.getresponse()
        if provider == "telegram":
            raw = reply.read(16385)
            return reply.status == 200 and len(raw) <= 16384 and json.loads(raw).get("ok") is True
        return reply.status in (200, 204)
    finally:
        conn.close()


def _save_global(session, provider, value):
    # Upstream's shared settings are stored as a global default. Do not
    # touch other user files or accidentally claim to remove legacy overrides.
    import os
    import tempfile
    from pathlib import Path

    with sessionStorage.session_data_lock():
        path = Path(sessionStorage.get_global_config_path())
        user = Path(sessionStorage.get_user_file_path(getattr(session, "mail", None) or ""))
        if path.is_symlink() or user.is_symlink():
            raise RuntimeError("Protected provider settings path unavailable")
        if user.exists():
            existing = json.loads(user.read_text(encoding="utf-8"))
            if not isinstance(existing, dict) or not isinstance(existing.get("shared", {}), dict):
                raise RuntimeError("Protected provider settings unavailable")
            if provider in existing.get("shared", {}):
                raise RuntimeError("Legacy per-user override requires local reconciliation")
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(data, dict):
            raise RuntimeError("Protected provider settings unavailable")
        data[provider] = value
        fd, name = tempfile.mkstemp(prefix=".notification-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def _apply(session, provider, value):
    if not isinstance(value, dict):
        raise ValueError("Invalid provider configuration")
    if value == {"mode": "clear"}:
        _save_global(session, provider, {})
        return "cleared"
    if provider == "telegram":
        if set(value) != {"mode", "bot_token", "chat_id"} or value["mode"] != "replace":
            raise ValueError("Invalid Telegram configuration")
        token, chat = value["bot_token"], value["chat_id"]
        if (not isinstance(token, str) or not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}", token)
                or not isinstance(chat, str) or not re.fullmatch(r"-?[1-9][0-9]{0,19}", chat)):
            raise ValueError("Invalid Telegram configuration")
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        body = {"chat_id": chat, "text": "Daedalus notification setup test"}
        data = {"botToken": token, "chatId": chat}
    else:
        if set(value) != {"mode", "webhook_url"} or value["mode"] != "replace":
            raise ValueError("Invalid Discord configuration")
        url = value["webhook_url"]
        if not isinstance(url, str) or not re.fullmatch(
                r"https://(?:discord[.]com|discordapp[.]com)/api/webhooks/[0-9]{1,25}/[A-Za-z0-9_-]{10,200}", url):
            raise ValueError("Invalid Discord configuration")
        body = {"content": "Daedalus notification setup test"}
        data = {"webhookUrl": url}
    try:
        accepted = _provider_accepts(provider, url, body)
    except Exception:
        raise RuntimeError("Provider test outcome uncertain; configuration unchanged") from None
    if not accepted:
        raise RuntimeError("Provider test rejected; configuration unchanged")
    _save_global(session, provider, data)
    return "configured"


def complete(session, account, provider, envelope):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    identity = _identity(session, account, provider)
    if (not isinstance(envelope, dict)
            or set(envelope) != {"ticket_id", "version", "confirmed_global", "client_key", "nonce", "ciphertext"}
            or type(envelope["version"]) is not int or envelope["version"] != 1
            or envelope["confirmed_global"] is not True or not isinstance(envelope["ticket_id"], str)
            or not _TICKET.fullmatch(envelope["ticket_id"])):
        raise ValueError("Invalid encrypted provider configuration")
    ticket = envelope["ticket_id"]
    with _LOCK:
        _prune(time.monotonic())
        entry = _PENDING.get(ticket)
        if entry is None or entry[0] != identity:
            raise ValueError("Provider configuration ticket expired or mismatched")
        del _PENDING[ticket]
    try:
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _decode(envelope["client_key"], 100))
        nonce = _decode(envelope["nonce"], 16)
        ciphertext = _decode(envelope["ciphertext"], 4096)
        if len(nonce) != 12 or not 17 <= len(ciphertext) <= 2048:
            raise ValueError("Invalid encrypted provider configuration")
        aad = _aad(ticket, account, provider)
        shared = entry[1].exchange(ec.ECDH(), peer)
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=aad).derive(shared)
        value = json.loads(AESGCM(key).decrypt(nonce, ciphertext, aad))
    except Exception:
        raise ValueError("Invalid encrypted provider configuration") from None
    result = _apply(session, provider, value)
    return {"account_id": account, "provider": provider, "scope": "worker_global", "result": result}
