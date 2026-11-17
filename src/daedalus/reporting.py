"""Warehouse report formatting extracted from the legacy desktop workflow.

The API differentiates unknown (None) from genuine zero. Filtering uses only
known unsecured values, so a partially loaded city is never overrepresented.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence

RESOURCES = ("wood", "wine", "marble", "glass", "sulfur")
_COLUMNS = ("account", "city", "world", *RESOURCES, "capacity", "captured_at", "incomplete")


def rows_for_warehouse(
    account: Mapping[str, object],
    snapshots: Sequence[Mapping[str, object]],
    *,
    only_220k: bool = False,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for city in snapshots:
        resource_block = city.get("resources")
        resources = resource_block if isinstance(resource_block, dict) else {}
        unsecured = resources.get("unsecured")
        quantities = unsecured if isinstance(unsecured, dict) else {}
        values = {
            name: amount if isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0 else None
            for name in RESOURCES
            for amount in (quantities.get(name),)
        }
        total_known = sum(amount for amount in values.values() if amount is not None)
        if only_220k and total_known < 220_000:
            continue
        capacity = resources.get("capacity")
        row: dict[str, object] = {
            "account": account.get("label") or account.get("player") or account.get("id") or "",
            "city": city.get("city_name") or "",
            "world": account.get("world") or "",
            **values,
            "capacity": capacity if isinstance(capacity, int) and not isinstance(capacity, bool) and capacity >= 0 else None,
            "captured_at": city.get("captured_at") or "",
            "incomplete": any(value is None for value in values.values()),
        }
        rows.append(row)
    return rows


def report_csv(rows: Sequence[Mapping[str, object]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if row.get(key) is None else row.get(key, "") for key in _COLUMNS})
    return output.getvalue()


def report_json(rows: Sequence[Mapping[str, object]]) -> str:
    return json.dumps(list(rows), ensure_ascii=False, indent=2)
