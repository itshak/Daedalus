"""Account-bound aggregate map reports; never publish upstream identifying dumps."""
import hashlib
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from ikabot.helpers import sessionStorage

MAX_ROWS = 10201
MAX_REPORTS = 20
MAX_BYTES = 1024 * 1024
_ID = re.compile(r"[a-f0-9]{24}\Z")


def _integer(value, maximum, minimum=0):
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,12}", value):
        value = int(value)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid map observation")
    return value


def _private_directory(path):
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or
            (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077))):
        raise ValueError("Protected report directory unavailable")


def _directory(session):
    identity = f"s{session.mundo}-{session.servidor}".casefold() + "\0" + session.username.casefold()
    root = Path(sessionStorage.get_ikabot_dir())
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ValueError("Protected report directory unavailable")
    parent = root / "world-reports"
    _private_directory(parent)
    directory = parent / hashlib.sha256(identity.encode("utf-8")).hexdigest()
    _private_directory(directory)
    return directory


def _files(directory):
    return [p for p in directory.iterdir() if _ID.fullmatch(p.stem) and p.suffix == ".json"]


def ensure_capacity(session):
    if len(_files(_directory(session))) >= MAX_REPORTS:
        raise ValueError("Report storage limit reached; reconcile locally")


def project_world(world, report_id, completed_at):
    if (not isinstance(report_id, str) or not _ID.fullmatch(report_id)
            or type(world.get("shallow")) is not bool or type(world.get("partial")) is not bool
            or not isinstance(world.get("islands"), list) or len(world["islands"]) > 11000
            or type(completed_at) is not int or completed_at <= 0):
        raise ValueError("Invalid map report")
    rows = {}
    for item in world["islands"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid map observation")
        if world["shallow"]:
            resource, wonder, wood, luxury, occupied = (
                item["resource_type"], item["miracle_type"], item["wood_lvl"], None, item["players"])
        else:
            cities = item["cities"]
            if not isinstance(cities, list) or len(cities) > 100 or any(
                    not isinstance(c, dict) or not isinstance(c.get("type"), str) for c in cities):
                raise ValueError("Invalid island occupancy")
            resource, wonder, wood, luxury, occupied = (
                item["tradegood"], item["wonder"], item["resourceLevel"], item["tradegoodLevel"],
                sum(c["type"] != "empty" for c in cities))
        row = [_integer(item["x"], 100), _integer(item["y"], 100),
               _integer(item["id"], 10**12-1, 1), _integer(resource, 4),
               _integer(wonder, 8), _integer(wood, 150),
               None if luxury is None else _integer(luxury, 150), _integer(occupied, 100)]
        key = tuple(row[:2])
        if key in rows and rows[key] != row:
            raise ValueError("Conflicting map observations")
        rows[key] = row
    if len(rows) > MAX_ROWS or len({r[2] for r in rows.values()}) != len(rows):
        raise ValueError("Invalid map report")
    return {"report_id": report_id, "completed_at": completed_at,
            "shallow": world["shallow"], "partial": world["partial"],
            "rows": [rows[key] for key in sorted(rows)]}


def save_report(session, report_id, world):
    report = project_world(world, report_id, int(time.time()))
    data = json.dumps(report, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(data) > MAX_BYTES:
        raise ValueError("Report too large")
    with sessionStorage.session_data_lock():
        directory = _directory(session)
        destination = directory / (report_id + ".json")
        if destination.exists() or destination.is_symlink() or len(_files(directory)) >= MAX_REPORTS:
            raise ValueError("Report destination unavailable")
        fd, name = tempfile.mkstemp(prefix=".report-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def _read(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES or
            (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077))):
        raise ValueError("Protected report unavailable")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("Report changed")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Report too large")
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {"report_id", "completed_at", "shallow", "partial", "rows"}
            or value["report_id"] != path.stem or type(value["completed_at"]) is not int
            or value["completed_at"] <= 0 or type(value["shallow"]) is not bool
            or type(value["partial"]) is not bool or not isinstance(value["rows"], list)
            or len(value["rows"]) > MAX_ROWS):
        raise ValueError("Invalid stored report")
    seen = set()
    ids = set()
    for row in value["rows"]:
        if (not isinstance(row, list) or len(row) != 8
                or any(type(n) is not int or not lo <= n <= hi
                       for n, lo, hi in zip(row[:6], (0,0,1,0,0,0), (100,100,10**12-1,4,8,150)))
                or (row[6] is not None and (type(row[6]) is not int or not 0 <= row[6] <= 150))
                or (value["shallow"] and row[6] is not None)
                or type(row[7]) is not int or not 0 <= row[7] <= 100
                or tuple(row[:2]) in seen or row[2] in ids):
            raise ValueError("Invalid stored map observation")
        seen.add(tuple(row[:2]))
        ids.add(row[2])
    return value


def _metadata(report):
    return {k: report[k] for k in ("report_id", "completed_at", "shallow", "partial")} | {"island_count": len(report["rows"])}


def list_reports(session):
    files = _files(_directory(session))
    if len(files) > MAX_REPORTS:
        raise ValueError("Report storage limit reached")
    return sorted((_metadata(_read(path)) for path in files),
                  key=lambda r: (r["completed_at"], r["report_id"]), reverse=True)


def read_report(session, report_id, offset):
    if not isinstance(report_id, str) or not _ID.fullmatch(report_id) or type(offset) is not int or not 0 <= offset <= MAX_ROWS:
        raise ValueError("Invalid report request")
    value = _read(_directory(session) / (report_id + ".json"))
    if offset > len(value["rows"]):
        raise ValueError("Invalid report offset")
    rows = value["rows"][offset:offset+1000]
    end = offset + len(rows)
    return {**_metadata(value), "offset": offset, "rows": rows,
            "next_offset": end if end < len(value["rows"]) else None}
