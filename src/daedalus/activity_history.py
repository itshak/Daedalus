"""Bounded, nonsecret durable task-receipt history contract."""
from __future__ import annotations

import math
import re

ACTIVITY_STATUSES = ("dispatching", "started", "rejected", "unconfirmed", "operator_reconciled")


def validate_activity_query(before: object, limit: object, status: object) -> None:
    if (before is not None and (type(before) is not int or not 1 <= before <= 2**53-1)
            or type(limit) is not int or not 1 <= limit <= 100
            or status not in ("all", *ACTIVITY_STATUSES)):
        raise ValueError("Invalid activity query")


def validate_activity_page(data: object, account_id: str, before: int | None,
                           limit: int, status: str) -> dict[str, object]:
    validate_activity_query(before, limit, status)
    if (not isinstance(data, dict) or data.get("account_id") != account_id
            or not isinstance(data.get("events"), list) or len(data["events"]) > limit):
        raise ValueError("Invalid activity page")
    cursor = data.get("next_before")
    if cursor is not None and (type(cursor) is not int or not 1 <= cursor <= 2**53-1
                               or (before is not None and cursor >= before)):
        raise ValueError("Invalid activity cursor")
    seen = set()
    for row in data["events"]:
        if (not isinstance(row, dict) or set(row) != {"request_id", "task", "status", "created_at", "updated_at"}
                or not isinstance(row["request_id"], str)
                or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", row["request_id"])
                or row["request_id"] in seen
                or not isinstance(row["task"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", row["task"])
                or row["status"] not in ACTIVITY_STATUSES or (status != "all" and row["status"] != status)
                or any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)
                                          or not 0 <= v <= 253402300799)
                       for v in (row["created_at"], row["updated_at"]))):
            raise ValueError("Invalid activity event")
        seen.add(row["request_id"])
    return {"account_id": account_id, "events": data["events"], "next_before": cursor}
