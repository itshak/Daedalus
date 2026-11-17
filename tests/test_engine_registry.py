"""Inspect public engine capabilities without importing any network/session modules."""

from pathlib import Path

import pytest

from daedalus.engine_registry import (
    EngineNotFoundError,
    inspect_engine,
    locate_engine_source,
    supports_structured_cli,
)


def test_local_source_is_detectable():
    path = locate_engine_source()
    assert path.name == "ikabot"
    assert (path / "function" / "constructionList.py").is_file()


def test_manifest_includes_native_and_menu_only_functions():
    all_capabilities = inspect_engine()
    assert len(all_capabilities) >= 30
    names = [item.name for item in all_capabilities]
    assert names == sorted(names, key=str.casefold)
    tasks = {item.name: item for item in all_capabilities}
    assert tasks["constructionList"].kind == "background_task"
    assert tasks["constructionList"].module.endswith("constructionList")
    assert "city_id" in tasks["constructionList"].parameters
    assert tasks["getStatus"].kind == "interactive_menu"
    assert tasks["webServer"].structured_cli is False
    assert all(item.structured_cli is False for item in all_capabilities)


def test_explicit_empty_source_fails(tmp_path: Path):
    with pytest.raises(EngineNotFoundError):
        inspect_engine(tmp_path)


def test_upstream_ipc_presence_detected_without_imports():
    assert supports_structured_cli() is True
    ipc_path = locate_engine_source() / "helpers" / "ipc.py"
    assert ipc_path.is_file()
    assert "authkey" in ipc_path.read_text(encoding="utf-8")
