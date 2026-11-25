"""Strict encrypted provider configuration envelope; never plain REST secrets."""
from __future__ import annotations

import base64
import json
import re
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROVIDERS = frozenset({"telegram", "discord"})
TICKET = re.compile(r"[A-Za-z0-9_-]{43}")


def _encoded(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decoded(value, minimum, maximum):
    if not isinstance(value, str) or not 0 < len(value) <= 4096 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid encrypted provider data")
    try:
        raw = base64.urlsafe_b64decode(value + "="*(-len(value)%4))
    except (ValueError, base64.binascii.Error):
        raise ValueError("Invalid encrypted provider data") from None
    if not minimum <= len(raw) <= maximum or _encoded(raw) != value:
        raise ValueError("Invalid encrypted provider data")
    return raw


def validate_challenge(value, account, provider):
    if (not isinstance(value, dict)
            or set(value) != {"account_id", "provider", "ticket_id", "public_key", "expires_in", "scope", "version"}
            or value["account_id"] != account or value["provider"] != provider or provider not in PROVIDERS
            or value["scope"] != "worker_global" or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["ticket_id"], str) or not TICKET.fullmatch(value["ticket_id"])
            or type(value["expires_in"]) is not int or not 1 <= value["expires_in"] <= 120):
        raise ValueError("Invalid provider configuration challenge")
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _decoded(value["public_key"], 65, 65))
    return value


def validate_envelope(value):
    if (not isinstance(value, dict)
            or set(value) != {"ticket_id", "version", "confirmed_global", "client_key", "nonce", "ciphertext"}
            or type(value["version"]) is not int or value["version"] != 1 or value["confirmed_global"] is not True
            or not isinstance(value["ticket_id"], str) or not TICKET.fullmatch(value["ticket_id"])):
        raise ValueError("Invalid encrypted provider configuration")
    _decoded(value["client_key"], 65, 65)
    _decoded(value["nonce"], 12, 12)
    _decoded(value["ciphertext"], 17, 2048)
    return value


def validate_receipt(value, account, provider):
    if (not isinstance(value, dict) or set(value) != {"account_id", "provider", "scope", "result"}
            or value["account_id"] != account or value["provider"] != provider
            or value["scope"] != "worker_global" or value["result"] not in ("configured", "cleared")):
        raise ValueError("Invalid provider configuration receipt")
    return value


def seal_notification_settings(challenge, account, provider, settings):
    validate_challenge(challenge, account, provider)
    private = ec.generate_private_key(ec.SECP256R1())
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _decoded(challenge["public_key"], 65, 65))
    aad = ("daedalus-notification-v1:"+challenge["ticket_id"]+":"+account+":"+provider).encode("ascii")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=aad).derive(private.exchange(ec.ECDH(), peer))
    nonce = secrets.token_bytes(12)
    payload = json.dumps(settings, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(payload) > 2000:
        raise ValueError("Provider configuration too large")
    return {"ticket_id": challenge["ticket_id"], "version": 1, "confirmed_global": True,
            "client_key": _encoded(private.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)),
            "nonce": _encoded(nonce), "ciphertext": _encoded(AESGCM(key).encrypt(nonce, payload, aad))}
