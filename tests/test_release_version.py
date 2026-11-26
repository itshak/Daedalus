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
