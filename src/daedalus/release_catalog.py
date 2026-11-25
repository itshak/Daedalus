"""Bounded public release metadata, never an automatic updater.

Only the project's fixed public GitHub repository is queried, on explicit
operator request. No user credentials, arbitrary URL, process execution,
downloaded code or private deployment configuration enters this adapter.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time
from datetime import datetime

from daedalus import __version__

_REPO = "itshak/Daedalus"
_RELEASES = "https://github.com/" + _REPO + "/releases"
_TAG = re.compile(r"desktop-preview-[0-9a-f]{12}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_VERSION = re.compile(r"[0-9][0-9a-z.]{0,30}\Z")
_DMG = "Daedalus-macos-preview.dmg"
_CHECKSUM = _DMG + ".sha256"
_MAX_BYTES = 1024 * 1024
_LOCK = threading.Lock()
_cached = None
_frozen_revision: str | None = None


class ReleaseCatalogUnavailable(RuntimeError):
    """Sanitized release catalog failure."""


def set_frozen_build_revision(value: str):
    """Called only by the generated packaged application launcher."""
    global _frozen_revision
    _frozen_revision = value if _SHA.fullmatch(value) else None


def build_revision():
    """Optional deployment-supplied revision, not a cryptographic attestation."""
    raw = _frozen_revision or os.environ.get("DAEDALUS_BUILD_SHA", "")
    return raw if _SHA.fullmatch(raw) else None


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Invalid release date")
    return datetime.fromisoformat(value)


def parse_releases(records):
    """Select the newest published project preview with both exact assets."""
    if not isinstance(records, list) or len(records) > 30:
        raise ValueError("Invalid release catalog")
    candidates = []
    for row in records:
        if not isinstance(row, dict) or row.get("draft") is not False or row.get("prerelease") is not True:
            continue
        tag = row.get("tag_name")
        if not isinstance(tag, str) or not _TAG.fullmatch(tag):
            continue
        try:
            published = _timestamp(row.get("published_at"))
        except ValueError:
            continue
        assets = row.get("assets")
        if not isinstance(assets, list) or len(assets) > 100:
            continue
        verified = {}
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("name") not in (_DMG, _CHECKSUM):
                continue
            name = asset["name"]
            expected = _RELEASES + "/download/" + tag + "/" + name
            if (name in verified or asset.get("state") != "uploaded"
                    or type(asset.get("size")) is not int or not 0 < asset["size"] <= 2**32
                    or asset.get("browser_download_url") != expected):
                verified = {}
                break
            verified[name] = expected
        if set(verified) != {_DMG, _CHECKSUM}:
            continue
        candidates.append((published, tag, {
            "tag": tag, "revision_prefix": tag[-12:],
            "published_at": row["published_at"],
            "release_url": _RELEASES + "/tag/" + tag,
            "dmg_url": verified[_DMG], "checksum_url": verified[_CHECKSUM],
            "notarization": "unnotarized_preview",
        }))
    return max(candidates, key=lambda row: (row[0], row[1]))[2] if candidates else None


def _public_catalog():
    conn = http.client.HTTPSConnection("api.github.com", timeout=6)
    try:
        conn.request("GET", "/repos/" + _REPO + "/releases?per_page=10",
                     headers={"Accept": "application/vnd.github+json",
                              "User-Agent": "Daedalus-release-catalog",
                              "X-GitHub-Api-Version": "2022-11-28"})
        response = conn.getresponse()
        if response.status != 200:
            raise ReleaseCatalogUnavailable("Public release catalog unavailable")
        raw = response.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ReleaseCatalogUnavailable("Public release catalog unavailable")
        return parse_releases(json.loads(raw))
    except (OSError, ValueError, http.client.HTTPException):
        raise ReleaseCatalogUnavailable("Public release catalog unavailable") from None
    finally:
        conn.close()


def release_status(*, offline=False):
    global _cached
    observed = None
    status = "offline" if offline else "unavailable"
    if not offline:
        with _LOCK:
            now = time.monotonic()
            if _cached is None or now - _cached[0] >= 300:
                try:
                    result = _public_catalog()
                    _cached = (now, "available" if result else "no_preview", result)
                except ReleaseCatalogUnavailable:
                    _cached = (now, "unavailable", None)
            _, status, observed = _cached
    return {"controller_version": __version__, "controller_revision": build_revision(),
            "catalog_status": status, "preview": observed}


def validate_release_status(value):
    if (not isinstance(value, dict)
            or set(value) != {"controller_version", "controller_revision", "catalog_status", "preview"}
            or not isinstance(value["controller_version"], str)
            or not _VERSION.fullmatch(value["controller_version"])
            or (value["controller_revision"] is not None and (
                not isinstance(value["controller_revision"], str) or not _SHA.fullmatch(value["controller_revision"])))
            or value["catalog_status"] not in ("offline", "unavailable", "no_preview", "available")):
        raise ValueError("Invalid release status")
    preview = value["preview"]
    if value["catalog_status"] != "available":
        if preview is not None:
            raise ValueError("Unexpected release preview")
        return value
    if (not isinstance(preview, dict) or set(preview) != {
            "tag", "revision_prefix", "published_at", "release_url", "dmg_url", "checksum_url", "notarization"}
            or not isinstance(preview["tag"], str) or not _TAG.fullmatch(preview["tag"])):
        raise ValueError("Invalid release preview")
    tag = preview["tag"]
    _timestamp(preview["published_at"])
    if (preview["revision_prefix"] != tag[-12:] or preview["notarization"] != "unnotarized_preview"
            or preview["release_url"] != _RELEASES + "/tag/" + tag
            or preview["dmg_url"] != _RELEASES + "/download/" + tag + "/" + _DMG
            or preview["checksum_url"] != _RELEASES + "/download/" + tag + "/" + _CHECKSUM):
        raise ValueError("Invalid release links")
    return value
