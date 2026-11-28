"""Keep beta version identifiers aligned across package formats."""
import json
import re
import tomllib
from pathlib import Path

from daedalus import __version__


def test_project_web_and_runtime_versions_match():
    root=Path(__file__).resolve().parents[1]
    project=tomllib.loads((root/"pyproject.toml").read_text(encoding="utf-8"))["project"]
    web=json.loads((root/"apps/web/package.json").read_text(encoding="utf-8"))
    lock=json.loads((root/"apps/web/package-lock.json").read_text(encoding="utf-8"))
    assert __version__==project["version"]
    expected=re.sub(r"b(\d+)$",r"-beta.\1",__version__)
    assert web["version"]==expected==lock["version"]==lock["packages"][""]["version"]


def test_beta_release_checks_exact_revision_and_checksum(tmp_path):
    import hashlib
    import runpy

    import pytest

    root = Path(__file__).resolve().parents[1]
    module = runpy.run_path(str(root / "scripts/prepare_beta_release.py"))
    sha = "a" * 40
    runs = [{"name": name, "headSha": sha, "status": "completed", "conclusion": "success"}
            for name in module["WORKFLOWS"]]
    module["require_green"](runs, sha)
    with pytest.raises(ValueError):
        module["require_green"](runs[:-1], sha)
    with pytest.raises(ValueError):
        module["require_green"](runs, "b" * 40)
    with pytest.raises(ValueError):
        module["require_green"]([{**runs[0], "conclusion": "failure"}, *runs], sha)
    dmg = tmp_path / module["DMG"]
    dmg.write_bytes(b"synthetic-package")
    digest = hashlib.sha256(dmg.read_bytes()).hexdigest()
    checksum = tmp_path / (dmg.name + ".sha256")
    checksum.write_text(f"{digest}  {dmg.name}\n", encoding="ascii")
    assert module["verify_checksum"](dmg, checksum) == digest
    dmg.write_bytes(b"changed-package")
    with pytest.raises(ValueError, match="mismatch"):
        module["verify_checksum"](dmg, checksum)


def test_server_install_includes_offline_smoke_client():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert any(req.startswith("httpx>=") for req in project["optional-dependencies"]["server"])


def test_beta_refresh_rejects_published_releases_and_existing_tags():
    import runpy

    import pytest

    root = Path(__file__).resolve().parents[1]
    check = runpy.run_path(str(root / "scripts/prepare_beta_release.py"))["require_refreshable_draft"]
    tag = "v0.1.0"
    draft = {"tagName": tag, "isDraft": True, "isPrerelease": True}
    check(draft, tag, "")
    for invalid in ({**draft, "isDraft": False}, {**draft, "isPrerelease": False}, {**draft, "tagName": "v0.2.0"}):
        with pytest.raises(ValueError):
            check(invalid, tag, "")
    with pytest.raises(ValueError):
        check(draft, tag, "existing tag")

def test_stage_later_beta_only_with_matching_metadata(tmp_path):
    import runpy

    import pytest

    root = Path(__file__).resolve().parents[1]
    check = runpy.run_path(str(root / "scripts/prepare_beta_release.py"))["release_version"]
    (tmp_path / "apps/web").mkdir(parents=True)
    (tmp_path / "src/daedalus").mkdir(parents=True)
    def stage(py, web, *, runtime=None, lock_version=None):
        (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{py}"\n')
        (tmp_path / "src/daedalus/__init__.py").write_text(f'__version__ = "{runtime or py}"\n')
        (tmp_path / "apps/web/package.json").write_text(json.dumps({"version": web}))
        (tmp_path / "apps/web/package-lock.json").write_text(json.dumps({
            "version": web, "packages": {"": {"version": lock_version or web}}}))
    stage("0.1.1", "0.1.1")
    assert check(tmp_path) == "0.1.1"
    stage("0.2.0b1", "0.2.0-beta.1")
    assert check(tmp_path) == "0.2.0-beta.1"
    for py, web in (("1.0.0", "1.0.0"), ("0.1.0", "0.1.1"), ("0.1.01", "0.1.01")):
        stage(py, web)
        with pytest.raises(ValueError):
            check(tmp_path)
    stage("0.1.1", "0.1.1", runtime="0.1.0")
    with pytest.raises(ValueError):
        check(tmp_path)
    stage("0.1.1", "0.1.1", lock_version="0.1.0")
    with pytest.raises(ValueError):
        check(tmp_path)
