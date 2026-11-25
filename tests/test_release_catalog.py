"""Release metadata is bounded, public, offline-testable and non-executable."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from daedalus import release_catalog as releases
from daedalus.api import create_app


def record(tag="desktop-preview-"+"a"*12, published="2026-11-24T00:00:00Z"):
    return {"tag_name": tag, "published_at": published, "draft": False,
            "prerelease": True, "assets": [
                {"name": name, "state": "uploaded", "size": 100,
                 "browser_download_url": "https://github.com/itshak/Daedalus/releases/download/"+tag+"/"+name}
                for name in ("Daedalus-macos-preview.dmg", "Daedalus-macos-preview.dmg.sha256")]}


def test_catalog_requires_exact_project_assets_and_selects_newest():
    old = record()
    newer = record("desktop-preview-"+"b"*12, "2026-11-25T00:00:00Z")
    bad = record("desktop-preview-"+"c"*12, "2026-11-26T00:00:00Z")
    bad["assets"][0]["browser_download_url"] = "https://example.invalid/dmg"
    assert releases.parse_releases([old,bad,newer])["revision_prefix"] == "b"*12
    assert releases.parse_releases([bad]) is None
    bad = record()
    bad["assets"].pop()
    assert releases.parse_releases([bad]) is None


def test_release_status_cache_and_no_secret_projection(monkeypatch):
    monkeypatch.setattr(releases, "_cached", None)
    fetch = Mock(return_value=releases.parse_releases([record()]))
    monkeypatch.setattr(releases, "_public_catalog", fetch)
    monkeypatch.setenv("DAEDALUS_BUILD_SHA", "not a commit")
    assert releases.release_status(offline=True)["catalog_status"] == "offline"
    fetch.assert_not_called()
    value = releases.release_status()
    assert releases.validate_release_status(value) == value
    assert releases.release_status() == value
    assert value["controller_revision"] is None
    fetch.assert_called_once()
    value = {**value, "preview": {**value["preview"], "dmg_url": "https://example.invalid/dmg"}}
    with pytest.raises(ValueError):
        releases.validate_release_status(value)


def test_demo_catalog_is_offline_and_requires_auth(monkeypatch):
    fetch = Mock(side_effect=AssertionError("demo may not connect to network"))
    monkeypatch.setattr(releases, "_public_catalog", fetch)
    token = "x"*48
    client = TestClient(create_app(demo_mode=True, api_token=token))
    assert client.get("/api/v1/release-status").status_code == 401
    assert client.get("/api/v1/release-status",headers={"Authorization":"Bearer "+token}).json()["catalog_status"] == "offline"
    assert client.post("/api/v1/release-status",headers={"Authorization":"Bearer "+token}).status_code == 405
    fetch.assert_not_called()
