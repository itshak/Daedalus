"""Warehouse report formatting extracted from the legacy desktop workflow.

The API differentiates unknown (None) from genuine zero. Filtering uses only
known unsecured values, so a partially loaded city is never overrepresented.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping, Sequence

from daedalus.account_display import account_display_name

RESOURCES = ("wood", "wine", "marble", "glass", "sulfur")
_COLUMNS = ("account", "city", "island", "world", *RESOURCES, "capacity", "captured_at", "incomplete")


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
        raw_island = city.get("island")
        island = raw_island if (
            isinstance(raw_island, str)
            and re.fullmatch(r"[0-9]{1,3}:[0-9]{1,3}", raw_island)
        ) else None
        row: dict[str, object] = {
            "account": account_display_name(account),
            "city": city.get("city_name") or "",
            "island": island,
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


def report_txt(rows: Sequence[Mapping[str, object]], *, group_by_island: bool = True) -> str:
    """Readable local report with unknown amounts represented distinctly from zero."""
    lines = ["Daedalus warehouse report"]
    if not group_by_island:
        ordered = [(None, row) for row in rows]
    else:
        ordered = sorted(
            ((str(row.get("island") or "Unknown"), row) for row in rows),
            key=lambda pair: (
                str(pair[1].get("world") or ""),
                pair[0] == "Unknown",
                pair[0],
                str(pair[1].get("city") or ""),
            ),
        )
    previous: tuple[str, str] | None = None
    for island, row in ordered:
        world = str(row.get("world") or "")
        heading = (world, island or "")
        if group_by_island and heading != previous:
            lines.extend(("", f"World {world or 'Unknown'} | Island {island}"))
            previous = heading
        quantities = ", ".join(
            f"{name}: {row.get(name) if row.get(name) is not None else '—'}"
            for name in RESOURCES
        )
        capacity = row.get("capacity")
        lines.append(
            f"- {row.get('city') or 'Unknown city'}"
            f" [{row.get('account') or 'Unknown account'}]: {quantities}; "
            f"capacity: {capacity if capacity is not None else '—'}"
        )
    return "\n".join(lines).rstrip() + "\n"
