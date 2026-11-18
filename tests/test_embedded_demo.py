"""Real loopback synthetic API tests; no Gameforge or saved IkaBot data."""

from __future__ import annotations

import os
import socket

import httpx
import pytest

from daedalus.client import DaedalusClient
from daedalus.desktop.demo_backend import EmbeddedDemoServer, OfflineDemoUnavailable


def test_click_launches_bearer_protected_synthetic_backend_only(monkeypatch):
    from daedalus import api

    def prohibited(*_args, **_kwargs):
        pytest.fail("Synthetic demo must not read real account files")

    monkeypatch.setattr(api, "load_accounts", prohibited)
    original_env = os.environ.get("DAEDALUS_API_TOKEN")
    server = EmbeddedDemoServer()
    with server:
        assert server.running
        assert server.url.startswith("http://127.0.0.1:")
        port = int(server.url.rsplit(":", 1)[1])
        with httpx.Client(timeout=5, trust_env=False) as unauthenticated:
            assert unauthenticated.get(server.url + "/api/v1/accounts").status_code == 401
        with DaedalusClient(server.url, server.token) as client:
            assert client.health()["mode"] == "synthetic_demo"
            accounts_data = client.accounts()
            assert len(accounts_data) == 2
            assert all(acc["synthetic"] for acc in accounts_data)
            report = client.warehouses(accounts_data[0]["id"])
            assert report
            assert all("password" not in str(row) for row in report)
        assert server.start() is server
        assert server.running
        assert len(server.token) >= 32
        assert server.token not in server.url
    assert not server.running
    assert os.environ.get("DAEDALUS_API_TOKEN") == original_env
    with pytest.raises(OfflineDemoUnavailable, match="not running"):
        _ = server.token
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=0.15)


def test_demo_lifecycle_explicit_start_and_idempotent_stop():
    server = EmbeddedDemoServer()
    assert not server.running
    with pytest.raises(OfflineDemoUnavailable):
        _ = server.url
    server.stop()
    assert not server.running
    server.start()
    assert server.running
    old_token = server.token
    server.stop()
    server.stop()
    assert not server.running
    server.start()
    assert server.running
    assert server.token != old_token
    server.stop()


def test_missing_optional_server_dependency_fails_without_starting(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "uvicorn", None)
    server = EmbeddedDemoServer()
    with pytest.raises(OfflineDemoUnavailable, match="server dependency"):
        server.start()
    assert not server.running
