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
    assert result["new_worker_bootstrap_implemented"] is True
    assert result["new_worker_bootstrap_scope"] == "explicit_single_account_saved_cookies_only"
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


def test_cookie_only_worker_requires_separate_explicit_consents(capsys):
    import pytest

    base = ["serve", "--restore-saved-account", "alpha"]
    for args in (
        base,
        [*base, "--accounts-file", "/synthetic/accounts.toml"],
        [*base, "--accounts-file", "/synthetic/accounts.toml", "--connect-existing-ipc"],
        [*base, "--accounts-file", "/synthetic/accounts.toml",
         "--connect-existing-ipc", "--confirm-read-only-network", "--demo"],
        [*base, "--accounts-file", "/synthetic/accounts.toml",
         "--connect-existing-ipc", "--confirm-read-only-network", "--ipc-descriptor", "bad"],
    ):
        with pytest.raises(SystemExit) as error:
            main(args)
        assert error.value.code == 2
    output = capsys.readouterr().err
    assert "Cookie-only worker" in output


def test_cookie_only_cli_bootstraps_only_selected_worker_offline(monkeypatch):
    import daedalus.api as api_module
    import daedalus.cli as cli_module
    import daedalus.saved_worker as worker_module
    from daedalus.accounts import Account

    fake = Account("alpha", "s301-en", "ExamplePlayer", "Test", True)
    events = []
    sentinel = object()

    class FakeWorker:
        def __init__(self, account, coordinator):
            assert account == fake
            assert coordinator.account_ids == frozenset({"alpha"})
            events.append("new-worker")

        def start(self, *, confirmed):
            assert confirmed is True
            events.append("confirmed-cookie-only-restore")

        def close(self):
            events.append("closed-worker")

    monkeypatch.setattr(cli_module, "load_accounts", lambda *_: [fake])
    monkeypatch.setattr(worker_module, "SavedCookieWorker", FakeWorker)
    monkeypatch.setattr(api_module, "create_app", lambda **kwargs: (
        events.append(("api", kwargs["accounts_path"], kwargs["task_controller"])),
        sentinel,
    )[1])
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: (
        events.append(("serve", app, kwargs["host"], kwargs["port"]))
    ))
    assert main([
        "serve", "--accounts-file", "/synthetic/private.toml",
        "--connect-existing-ipc", "--restore-saved-account", "alpha",
        "--confirm-read-only-network",
    ]) == 0
    assert events == [
        "new-worker", "confirmed-cookie-only-restore",
        ("api", "/synthetic/private.toml", None),
        ("serve", sentinel, "127.0.0.1", 8765), "closed-worker",
    ]
