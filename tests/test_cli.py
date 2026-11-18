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
    assert result["stage"] == "existing-session-preview"
    assert result["engine_integrated"] is True
    assert result["live_accounts_configured"] is None
    assert result["server_implemented"] is True
    assert result["server_mode"] == "read_only_by_default"
    assert result["desktop_implemented"] is True
    assert result["new_worker_bootstrap_implemented"] is False
    assert result["automatic_browser_authentication_implemented"] is False
    assert result["production_ready"] is False
    assert result["network_requests_performed"] == 0
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



def test_doctor_offline_synthetic_api_smoke(capsys, monkeypatch):
    import socket

    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("No real network connections in doctor")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    assert main(["doctor", "--smoke"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["offline_smoke"] == {
        "status": "passed",
        "scope": "synthetic_in_process_only",
        "authenticated_routes": True,
        "demo_accounts": 2,
        "warehouse_reporting": True,
        "game_network_requests": 0,
    }
    assert report["production_ready"] is False
    assert report["live_accounts_configured"] is None


def test_doctor_smoke_missing_optional_dependencies_are_sanitized(capsys, monkeypatch):
    from daedalus import readiness

    def unavailable():
        raise readiness.OfflineSmokeError("Install optional dependencies for synthetic smoke")

    monkeypatch.setattr(readiness, "synthetic_smoke", unavailable)
    assert main(["doctor", "--smoke"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["offline_smoke"]["status"] == "failed"
    assert report["production_ready"] is False


def test_doctor_does_not_access_real_account_config_or_keyring(capsys, monkeypatch):
    import socket

    import daedalus.accounts as account_module

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Doctor must not inspect private state or network")

    monkeypatch.setattr(account_module, "load_accounts", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert main(["doctor"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["live_accounts_configured"] is None
    assert "token" not in report
    assert "password" not in report
