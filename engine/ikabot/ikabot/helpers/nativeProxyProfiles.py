"""Explicit owner-approved network profiles; no remote endpoint or credential input."""
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from pathlib import Path
from urllib.parse import urlsplit

import psutil
import requests
from ikabot.helpers import sessionStorage

_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_REVISION = re.compile(r"[a-f0-9]{64}\Z")
_PROTOCOLS = ("http", "https", "socks4", "socks5", "socks5h")
_KEY = secrets.token_bytes(32)
_TEST_URL = "https://example.com/"


def _scope(session):
    return f"s{session.mundo}-{session.servidor}".casefold() + "\0" + session.username.casefold()


def _approved_path(session):
    return Path(sessionStorage.get_ikabot_dir()) / "approved-proxies" / (hashlib.sha256(_scope(session).encode()).hexdigest() + ".json")


def _private(path, directory=False):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
        raise ValueError("Unapproved profile permissions")
    return info


def _inventory(session):
    path = _approved_path(session)
    if not path.parent.exists():
        return False, {}
    _private(path.parent, directory=True)
    if not path.exists() and not path.is_symlink():
        return False, {}
    info = _private(path)
    if info.st_size > 32768:
        raise ValueError("Approved profile inventory too large")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("Approved profile inventory changed")
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise ValueError("Approved profile inventory too large")
    data = json.loads(raw)
    if (not isinstance(data, dict) or set(data) != {"version", "allow_direct", "profiles"}
            or type(data["version"]) is not int or data["version"] != 1
            or type(data["allow_direct"]) is not bool
            or not isinstance(data["profiles"], list) or len(data["profiles"]) > 16):
        raise ValueError("Invalid approved profile inventory")
    profiles = {}
    for row in data["profiles"]:
        if (not isinstance(row, dict) or set(row) != {"id", "label", "url"}
                or not isinstance(row["id"], str) or not _ID.fullmatch(row["id"]) or row["id"] in profiles or row["id"] == "legacy"
                or not isinstance(row["label"], str) or not re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", row["label"])
                or not isinstance(row["url"], str) or not 0 < len(row["url"]) <= 300
                or any(ord(c) < 33 or ord(c) > 126 for c in row["url"])):
            raise ValueError("Invalid approved profile")
        parsed = urlsplit(row["url"])
        if (parsed.scheme not in _PROTOCOLS or not parsed.hostname or not parsed.port
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("Use a host-provisioned proxy without inline credentials")
        profiles[row["id"]] = {**row, "protocol": parsed.scheme}
    if len({r["url"] for r in profiles.values()}) != len(profiles):
        raise ValueError("Duplicate approved profile endpoint")
    return data["allow_direct"], profiles


def _busy(data):
    rows = data.get("processList", [])
    if not isinstance(rows, list) or len(rows) > 1000:
        return True
    for row in rows:
        if not isinstance(row, dict) or type(row.get("pid")) is not int or row["pid"] <= 0:
            return True
        if row["pid"] != os.getpid() and psutil.pid_exists(row["pid"]):
            return True
    return False


def _snapshot(session):
    data = session.getSessionData()
    if not isinstance(data, dict):
        raise ValueError("Account settings unavailable")
    allow_direct, profiles = _inventory(session)
    proxy = data.get("proxy")
    if proxy is not None and not isinstance(proxy, dict):
        raise ValueError("Invalid account network settings")
    active = isinstance(proxy, dict) and proxy.get("set") is True
    current = None
    if active:
        current = next((key for key, row in profiles.items()
                        if proxy.get("conf") == {"http": row["url"], "https": row["url"]}), "legacy")
    revision = hmac.new(_KEY, json.dumps([_scope(session), allow_direct, profiles, proxy],
                            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
                            hashlib.sha256).hexdigest()
    status = {"revision": revision, "enabled": active, "current": current,
              "allow_direct": allow_direct, "busy": _busy(data),
              "profiles": [{k: row[k] for k in ("id", "label", "protocol")} for row in profiles.values()]}
    return data, profiles, status


def status(session):
    with sessionStorage.session_data_lock():
        return {**_snapshot(session)[2], "result": "observed"}


def _check_connectivity(url):
    # Never use a game session, cookies, credentials, environment proxy or
    # caller-supplied destination. Do not follow redirects or read body content.
    with requests.Session() as connection:
        connection.trust_env = False
        if url is not None:
            connection.proxies = {"http": url, "https": url}
        with connection.get(_TEST_URL, timeout=(4, 5), verify=True, allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError("Connectivity not verified")


def configure(session, draft, *, managed_busy=False):
    if (not isinstance(draft, dict) or set(draft) != {"action", "profile", "revision", "confirmed"}
            or draft["action"] not in ("test", "save")
            or (draft["profile"] is not None and (not isinstance(draft["profile"], str)
                                                or not _ID.fullmatch(draft["profile"]) or draft["profile"] == "legacy"))
            or not isinstance(draft["revision"], str) or not _REVISION.fullmatch(draft["revision"])
            or draft["confirmed"] is not True):
        raise ValueError("Invalid network profile review")
    with sessionStorage.session_data_lock():
        _, profiles, observed = _snapshot(session)
        choice = draft["profile"]
        if (managed_busy or observed["busy"] or observed["revision"] != draft["revision"]
                or (choice is None and not observed["allow_direct"])
                or (choice is not None and choice not in profiles)):
            raise ValueError("Network profile review unavailable or changed")
        url = profiles[choice]["url"] if choice is not None else None
    _check_connectivity(url)
    with sessionStorage.session_data_lock():
        data, _, current = _snapshot(session)
        if current["busy"] or current["revision"] != observed["revision"]:
            raise ValueError("Network profile changed during connectivity test")
        if draft["action"] == "test":
            return {**current, "result": "tested"}
        # Account-local upstream setting only; existing sessions pick it up
        # via their normal proxy refresh. Never trigger reconnect or game I/O.
        updated = dict(data)
        updated.pop("shared", None)
        updated["proxy"] = {"set": False} if url is None else {"set": True, "conf": {"http": url, "https": url}}
        session.setSessionData(updated)
        result = _snapshot(session)[2]
        if result["current"] != choice or result["enabled"] is not (choice is not None):
            raise ValueError("Network profile save unconfirmed")
        return {**result, "result": "saved"}
