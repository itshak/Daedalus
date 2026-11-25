"""Fixed, nonsecret extension registration contract."""
import re

_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def validate_extension_draft(value):
    if (not isinstance(value, dict) or set(value) != {"id", "sha256", "registered", "expected_registered", "confirmed_global"}
            or not isinstance(value["id"], str) or not _ID.fullmatch(value["id"])
            or not isinstance(value["sha256"], str) or not _SHA.fullmatch(value["sha256"])
            or type(value["registered"]) is not bool or type(value["expected_registered"]) is not bool
            or value["confirmed_global"] is not True):
        raise ValueError("Invalid extension request")
    return value


def validate_extension_status(value, account):
    if (not isinstance(value, dict) or set(value) != {"account_id", "scope", "legacy_override", "unreviewed_count", "extensions"}
            or value["account_id"] != account or value["scope"] != "worker_global"
            or type(value["legacy_override"]) is not bool or type(value["unreviewed_count"]) is not int
            or not 0 <= value["unreviewed_count"] <= 1000
            or not isinstance(value["extensions"], list) or len(value["extensions"]) > 32):
        raise ValueError("Invalid extension status")
    seen = set()
    for row in value["extensions"]:
        if (not isinstance(row, dict) or set(row) != {"id", "name", "sha256", "verified", "registered"}
                or not isinstance(row["id"], str) or not _ID.fullmatch(row["id"]) or row["id"] in seen
                or not isinstance(row["name"], str) or not re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", row["name"])
                or not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])
                or type(row["verified"]) is not bool or type(row["registered"]) is not bool):
            raise ValueError("Invalid extension status")
        seen.add(row["id"])
    return value
