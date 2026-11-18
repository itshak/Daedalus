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


def test_native_task_field_metadata_covers_all_builtin_background_tasks():
    tasks = [cap for cap in inspect_engine() if cap.kind == "background_task"]
    assert len(tasks) >= 20
    for cap in tasks:
        assert tuple(field["name"] for field in cap.config_fields) == cap.parameters
        assert "session" not in cap.parameters
        assert all(field["type"] in {"boolean", "integer", "number", "text", "json"}
                   for field in cap.config_fields)
        assert all(type(field["required"]) is bool for field in cap.config_fields)
    alert = next(cap for cap in tasks if cap.name == "alertAttacks")
    assert alert.config_fields == ({
        "name": "minutes", "required": False, "default": 20, "type": "integer",
    },)
    fields = next(cap for cap in tasks if cap.name == "alertLowWine").config_fields
    assert fields[0] == {"name": "hours", "required": True, "type": "json"}
    assert fields[1]["type"] == "boolean"


def test_dynamic_default_expression_is_never_evaluated_during_ast_scan(tmp_path):
    source = tmp_path / "ikabot"
    fn = source / "function"
    fn.mkdir(parents=True)
    (source / "command_line.py").write_text("menu_actions = {}\n")
    (fn / "synthetic.py").write_text(
        '@task("synthetic")\n'
        'def do_it(session, duration=never_call_this_function()):\n'
        '    pass\n'
    )
    capability = inspect_engine(source)[0]
    assert capability.name == "synthetic"
    assert capability.config_fields[0]["name"] == "duration"
    assert capability.config_fields[0]["required"] is False
    assert "default" not in capability.config_fields[0]
