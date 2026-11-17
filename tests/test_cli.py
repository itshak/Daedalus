"""Offline tests for Daedalus CLI and diagnostic inventory."""

import json

from daedalus import __version__
from daedalus.cli import main


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert __version__ in capsys.readouterr().out


def test_doctor_is_offline_and_honest(capsys):
    assert main(["doctor"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["stage"] == "read-only-controller"
    assert result["engine_integrated"] is False
    assert result["live_accounts_configured"] is False
    assert result["server_implemented"] is True
    assert result["server_mode"] == "read_only"
    assert result["engine_source_available"] is True
    assert result["engine_capabilities_found"] >= 30


def test_help(capsys):
    assert main([]) == 0
    assert "doctor" in capsys.readouterr().out


def test_engine_inventory_json_is_offline(capsys):
    assert main(["engine", "inventory"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["source"] == "public-ikabot"
    assert data["structured_cli_available"] is False
    capabilities = {item["name"]: item for item in data["capabilities"]}
    assert capabilities["getStatus"]["kind"] == "interactive_menu"
    assert capabilities["getStatus"]["menu_codes"] == [4]
    assert capabilities["constructionList"]["kind"] == "background_task"
    assert capabilities["constructionList"]["menu_codes"] == [1]
    assert capabilities["resourceTransportManager"]["kind"] == "background_task"
    assert capabilities["distributeResources"]["parameters"]
