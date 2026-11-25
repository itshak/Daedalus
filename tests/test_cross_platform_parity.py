"""Ensure the parity proposal accounts for every vendored operation."""
import re
from pathlib import Path

from daedalus.engine_registry import inspect_engine


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
