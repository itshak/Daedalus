"""Strict redacted account profile contracts; no arbitrary network addresses."""
import re

_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_REVISION = re.compile(r"[a-f0-9]{64}\Z")


def validate_proxy_draft(value):
    if (not isinstance(value, dict) or set(value) != {"action", "profile", "revision", "confirmed"}
            or value["action"] not in ("test", "save")
            or (value["profile"] is not None and (not isinstance(value["profile"], str) or not _ID.fullmatch(value["profile"]) or value["profile"] == "legacy"))
            or not isinstance(value["revision"], str) or not _REVISION.fullmatch(value["revision"])
            or value["confirmed"] is not True):
        raise ValueError("Invalid network profile review")
    return value


def validate_proxy_status(value, account):
    if (not isinstance(value, dict) or set(value) != {"account_id", "revision", "enabled", "current",
                "allow_direct", "busy", "profiles", "result"}
            or value["account_id"] != account
            or not isinstance(value["revision"], str) or not _REVISION.fullmatch(value["revision"])
            or any(type(value[k]) is not bool for k in ("enabled", "allow_direct", "busy"))
            or value["result"] not in ("observed", "tested", "saved")
            or not isinstance(value["profiles"], list) or len(value["profiles"]) > 16):
        raise ValueError("Invalid network profile status")
    ids = set()
    for row in value["profiles"]:
        if (not isinstance(row, dict) or set(row) != {"id", "label", "protocol"}
                or not isinstance(row["id"], str) or not _ID.fullmatch(row["id"]) or row["id"] == "legacy"
                or row["id"] in ids or not isinstance(row["label"], str)
                or not re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", row["label"])
                or row["protocol"] not in ("http", "https", "socks4", "socks5", "socks5h")):
            raise ValueError("Invalid approved network profile")
        ids.add(row["id"])
    if (value["enabled"] and (not isinstance(value["current"], str) or
                             value["current"] not in ids | {"legacy"})) or (
            not value["enabled"] and value["current"] is not None):
        raise ValueError("Invalid current network profile")
    return value


def validate_proxy_result(value, account, draft=None):
    value = validate_proxy_status(value, account)
    expected = "observed" if draft is None else "tested" if draft["action"] == "test" else "saved"
    if value["result"] != expected:
        raise ValueError("Network profile result unconfirmed")
    if draft is not None:
        if draft["action"] == "test" and value["revision"] != draft["revision"]:
            raise ValueError("Network profile changed")
        if draft["action"] == "save" and (value["current"] != draft["profile"]
                or value["enabled"] is not (draft["profile"] is not None)):
            raise ValueError("Network profile save unconfirmed")
    return value
