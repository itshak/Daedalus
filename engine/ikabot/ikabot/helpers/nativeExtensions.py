"""Host-approved extension registration; no file uploads, imports or execution.

Only fixed, locally installed files listed by ID and SHA-256 in the host's
approved-extensions directory can be registered. The remote UI never receives
file paths or source text. Registration changes the global default menu only.
"""
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from ikabot.helpers import sessionStorage
from ikabot.helpers.nativeNotificationSettings import _save_global

_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_MAX_SOURCE = 1024 * 1024


def _approved_directory():
    return Path(sessionStorage.get_ikabot_dir()) / "approved-extensions"


def _private(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        raise ValueError("Unapproved extension path")
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o022):
        raise ValueError("Unapproved extension permissions")
    return info


def _bounded_read(path, limit):
    info = _private(path)
    if info.st_size > limit:
        raise ValueError("Extension metadata too large")
    # O_NOFOLLOW is available on Unix; Windows lstat is checked above.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or (info.st_dev, info.st_ino) != (actual.st_dev, actual.st_ino):
            raise ValueError("Extension file changed")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Extension file too large")
    return raw


def _inventory():
    directory = _approved_directory()
    if not directory.exists():
        return {}
    _private(directory, directory=True)
    manifest = directory / "manifest.json"
    if not manifest.exists():
        return {}
    value = json.loads(_bounded_read(manifest, 65536))
    if (not isinstance(value, dict) or set(value) != {"version", "extensions"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["extensions"], list) or len(value["extensions"]) > 32):
        raise ValueError("Invalid host extension manifest")
    rows = {}
    for item in value["extensions"]:
        if (not isinstance(item, dict) or set(item) != {"id", "name", "sha256"}
                or not isinstance(item["id"], str) or not _ID.fullmatch(item["id"]) or item["id"] in rows
                or not isinstance(item["name"], str) or not re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", item["name"])
                or not isinstance(item["sha256"], str) or not _SHA.fullmatch(item["sha256"])):
            raise ValueError("Invalid approved extension")
        path = directory / (item["id"] + ".py")
        try:
            verified = hashlib.sha256(_bounded_read(path, _MAX_SOURCE)).hexdigest() == item["sha256"]
        except (OSError, ValueError):
            verified = False
        rows[item["id"]] = {**item, "verified": verified, "path": str(path)}
    return rows


def _registration(session):
    global_path = Path(sessionStorage.get_global_config_path())
    user_path = Path(sessionStorage.get_user_file_path(getattr(session, "mail", None) or ""))
    if global_path.is_symlink() or user_path.is_symlink():
        raise ValueError("Protected extension settings unavailable")
    data = json.loads(global_path.read_text(encoding="utf-8")) if global_path.exists() else {}
    user = json.loads(user_path.read_text(encoding="utf-8")) if user_path.exists() else {}
    if not isinstance(data, dict) or not isinstance(user, dict) or not isinstance(user.get("shared", {}), dict):
        raise ValueError("Protected extension settings unavailable")
    override = "customModules" in user.get("shared", {})
    registered = data.get("customModules", [])
    if (not isinstance(registered, list) or len(registered) > 1000
            or any(not isinstance(path, str) or not 0 < len(path) <= 4096 for path in registered)):
        raise ValueError("Invalid extension registration")
    return registered, override


def status(session):
    with sessionStorage.session_data_lock():
        entries = _inventory()
        registered, override = _registration(session)
        known = {row["path"] for row in entries.values()}
        return {"scope": "worker_global", "legacy_override": override,
                "unreviewed_count": sum(path not in known for path in registered),
                "extensions": [{k: row[k] for k in ("id", "name", "sha256", "verified")} |
                               {"registered": row["path"] in registered}
                               for row in entries.values()]}


def set_registration(session, draft):
    if (not isinstance(draft, dict) or set(draft) != {"id", "sha256", "registered", "expected_registered", "confirmed_global"}
            or not isinstance(draft["id"], str) or not _ID.fullmatch(draft["id"])
            or not isinstance(draft["sha256"], str) or not _SHA.fullmatch(draft["sha256"])
            or type(draft["registered"]) is not bool or type(draft["expected_registered"]) is not bool
            or draft["confirmed_global"] is not True):
        raise ValueError("Invalid extension request")
    with sessionStorage.session_data_lock():
        row = _inventory().get(draft["id"])
        registered, override = _registration(session)
        if (override or row is None or row["sha256"] != draft["sha256"]
                or (row["path"] in registered) is not draft["expected_registered"]
                or (draft["registered"] and not row["verified"])):
            raise ValueError("Extension registration changed or is not approved")
        if draft["registered"]:
            if row["path"] not in registered:
                registered.append(row["path"])
        else:
            registered = [path for path in registered if path != row["path"]]
        _save_global(session, "customModules", registered)
        return status(session)
