"""Bounded aggregate map report contracts and export assembly."""
import csv
import io
import re

REPORT_ID = re.compile(r"[a-f0-9]{24}\Z")
MAX_ROWS = 10201
COLUMNS = ("x", "y", "island_id", "resource_type", "miracle_type",
           "wood_level", "luxury_level", "occupied_slots")
_META = {"report_id", "completed_at", "shallow", "partial", "island_count"}


def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def validate_metadata(value):
    if (not isinstance(value, dict) or set(value) != _META
            or not isinstance(value["report_id"], str) or not REPORT_ID.fullmatch(value["report_id"])
            or not _integer(value["completed_at"], 1, 10**11)
            or type(value["shallow"]) is not bool or type(value["partial"]) is not bool
            or not _integer(value["island_count"], 0, MAX_ROWS)):
        raise ValueError("Invalid world report metadata")
    return value


def validate_world_reports(value, account):
    if (not isinstance(value, dict) or set(value) != {"account_id", "reports"}
            or value["account_id"] != account or not isinstance(value["reports"], list)
            or len(value["reports"]) > 20):
        raise ValueError("Invalid world report inventory")
    rows = [validate_metadata(row) for row in value["reports"]]
    if len({r["report_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate world report")
    return value


def validate_world_page(value, account, report_id, offset):
    if (not isinstance(value, dict) or set(value) != _META | {"account_id", "offset", "rows", "next_offset"}
            or value["account_id"] != account or value["report_id"] != report_id
            or type(value["offset"]) is not int or value["offset"] != offset
            or not _integer(offset, 0, MAX_ROWS)
            or not isinstance(value["rows"], list)):
        raise ValueError("Invalid world report scope")
    meta = validate_metadata({k: value[k] for k in _META})
    total = meta["island_count"]
    if offset > total or len(value["rows"]) != min(1000, total-offset):
        raise ValueError("Invalid world report page length")
    end = offset + len(value["rows"])
    expected_next = end if end < total else None
    if value["next_offset"] != expected_next or (expected_next is not None and type(value["next_offset"]) is not int):
        raise ValueError("Invalid report continuation")
    coords, ids = set(), set()
    for row in value["rows"]:
        if (not isinstance(row, list) or len(row) != 8
                or not all(_integer(n, lo, hi) for n,lo,hi in
                           zip(row[:6], (0,0,1,0,0,0), (100,100,10**12-1,4,8,150)))
                or (row[6] is not None and not _integer(row[6],0,150))
                or (meta["shallow"] and row[6] is not None)
                or not _integer(row[7],0,100) or tuple(row[:2]) in coords or row[2] in ids):
            raise ValueError("Invalid aggregate map row")
        coords.add(tuple(row[:2]))
        ids.add(row[2])
    return value


def collect_report(reader, account, report_id):
    offset, rows, metadata = 0, [], None
    for _ in range(11):
        page = validate_world_page(reader(offset), account, report_id, offset)
        current = {k: page[k] for k in _META}
        if metadata is not None and current != metadata:
            raise ValueError("Report changed during export")
        metadata = current
        rows.extend(page["rows"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    if (metadata is None or len(rows) != metadata["island_count"]
            or len({tuple(row[:2]) for row in rows}) != len(rows)
            or len({row[2] for row in rows}) != len(rows)):
        raise ValueError("Incomplete or inconsistent report")
    return {"account_id": account, **metadata, "rows": rows}


def report_csv(report):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerows(report["rows"])
    return out.getvalue()
