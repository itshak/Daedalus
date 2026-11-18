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
    assert result["engine_cli_available"] is True


def test_help(capsys):
    assert main([]) == 0
    assert "doctor" in capsys.readouterr().out


def test_engine_inventory_json_is_offline(capsys):
    assert main(["engine", "inventory"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["source"] == "public-ikabot"
    assert data["structured_cli_available"] is True
    capabilities = {item["name"]: item for item in data["capabilities"]}
    assert capabilities["getStatus"]["kind"] == "interactive_menu"
    assert capabilities["getStatus"]["menu_codes"] == [4]
    assert capabilities["constructionList"]["kind"] == "background_task"
    assert capabilities["constructionList"]["menu_codes"] == [1]
    assert capabilities["resourceTransportManager"]["kind"] == "background_task"
    assert capabilities["distributeResources"]["parameters"]


def test_account_editing_is_exclusive_with_task_dispatch(capsys):
    import pytest

    with pytest.raises(SystemExit) as error:
        main(["serve", "--connect-existing-ipc", "--enable-task-control",
              "--enable-account-editing"])
    assert error.value.code == 2
    assert "incompatible with --enable-task-control" in capsys.readouterr().err
