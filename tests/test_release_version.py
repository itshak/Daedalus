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
