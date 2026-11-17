"""Offline tests for the bootstrap package."""

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
    assert result["stage"] == "bootstrap"
    assert result["engine_integrated"] is False
    assert result["live_accounts_configured"] is False


def test_help(capsys):
    assert main([]) == 0
    assert "doctor" in capsys.readouterr().out
