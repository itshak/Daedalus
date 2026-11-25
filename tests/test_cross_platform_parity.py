"""Ensure the parity proposal accounts for every vendored operation."""
import json
import re
from pathlib import Path

from daedalus.engine_registry import inspect_engine
from daedalus.operation_manifest import AUXILIARY_OPERATIONS, coverage_manifest


def test_cross_platform_matrix_covers_engine_registry():
    root = Path(__file__).resolve().parents[1]
    change = root / "openspec/changes/complete-cross-platform-automation-parity"
    if not change.exists():
        archived = sorted((root / "openspec/changes/archive").glob(
            "*-complete-cross-platform-automation-parity"
        ))
        assert archived, "Missing parity change and archive"
        change = archived[-1]
    matrix = (change / "capability-matrix.md").read_text(encoding="utf-8")
    names = re.findall(r"^\| (\w+) \| (?:D|E|R|P|P0|S|M) \|", matrix, re.MULTILINE)
    assert len(names) == len(set(names)), "Duplicate operation in parity matrix"
    actual = {item.name for item in inspect_engine()}
    assert actual <= set(names), f"Missing upstream operations: {sorted(actual - set(names))}"


def test_versioned_coverage_manifest_matches_source_and_committed_matrix():
    root = Path(__file__).resolve().parents[1]
    change = root / "openspec/changes/complete-cross-platform-automation-parity"
    if not change.exists():
        change = max((root / "openspec/changes/archive").glob(
            "*-complete-cross-platform-automation-parity"
        ))
    manifest = coverage_manifest()
    assert json.loads((change / "capability-matrix.json").read_text()) == manifest
    assert set(manifest["operations"]) == {item.name for item in inspect_engine()} | AUXILIARY_OPERATIONS
    for operation in manifest["operations"].values():
        assert operation["live_accepted"] is False
        assert operation["desktop"] in {"native", "existing_view", "protected_local", "pending"}
        assert operation["web"] in {"native", "existing_view", "protected_local", "pending"}


def test_generated_web_launch_contract_matches_python():
    import runpy

    root = Path(__file__).resolve().parents[1]
    generator = runpy.run_path(str(root / "scripts/generate_operation_contract.py"))
    expected = generator["render"]()
    assert (root / "apps/web/lib/generated-operation-contract.ts").read_text() == expected
