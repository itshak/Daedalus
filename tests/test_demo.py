"""Synthetic, explicit demo mode tests. No game or browser network calls."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from daedalus.api import create_app
from daedalus.client import DaedalusClient
from daedalus.demo import demo_accounts, demo_cities, demo_warehouses

TOKEN = "x" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_demo_contract_is_distinct_from_live_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent-config"))
    app = create_app(demo_mode=True, api_token=TOKEN)
    client = TestClient(app)
    assert client.get("/api/v1/health").json()["mode"] == "synthetic_demo"
    assert client.get("/api/v1/health").json()["authenticated_workers"] == 0
    assert client.get("/api/v1/accounts").status_code == 401
    response = client.get("/api/v1/accounts", headers=AUTH)
    assert response.status_code == 200
    accounts = response.json()["accounts"]
    assert [a["id"] for a in accounts] == ["demo_alpha", "demo_beta"]
    assert all(a["synthetic"] is True and "DEMO" in a["label"] for a in accounts)
    assert all(a["session_status"] == "not_connected" for a in accounts)
    assert not (tmp_path / "nonexistent-config").exists()

    capabilities = client.get("/api/v1/capabilities", headers=AUTH).json()
    assert capabilities["synthetic_demo"] is True
    assert capabilities["structured_engine_dispatch"] is False

    warehouse = client.get("/api/v1/warehouses/demo_alpha", headers=AUTH).json()
    assert warehouse["synthetic_demo"] is True
    assert len(warehouse["cities"]) == 2
    assert warehouse["cities"][0]["city_name"] == "DEMO Athens"
    amounts = warehouse["cities"][0]["resources"]["unsecured"]
    assert amounts["wood"] == 225_000
    assert amounts["glass"] is None
    assert amounts["sulfur"] == 0
    assert warehouse["cities"][0]["island"] == "1:2"

    second = client.get("/api/v1/warehouses/demo_beta", headers=AUTH).json()
    assert second["cities"][0]["city_name"] == "DEMO Miletus"
    assert client.get("/api/v1/accounts/demo_beta/cities", headers=AUTH).json() == {
        "account_id": "demo_beta", "cities": demo_cities("demo_beta"),
        "synthetic_demo": True,
    }
    assert client.get("/api/v1/warehouses/unknown", headers=AUTH).status_code == 404


def test_demo_never_executes_mutations_or_attaches_ipc():
    client = TestClient(create_app(demo_mode=True, api_token=TOKEN))
    assert client.get("/api/v1/task-control", headers=AUTH).json()["enabled"] is False
    assert client.get("/api/v1/account-config", headers=AUTH).json()["enabled"] is False
    assert client.post("/api/v1/account-config", headers=AUTH, json={}).status_code == 405
    assert client.put("/api/v1/account-config", headers=AUTH, json={
        "revision": "a" * 64, "accounts": [], "confirmed": True,
    }).status_code == 503
    assert client.post("/api/v1/accounts/demo_alpha/tasks", headers=AUTH, json={
        "task": "constructionList", "config": {},
        "request_id": "12345678-1234-4123-8123-123456789abc", "confirmed": True,
    }).status_code == 503
    assert client.get("/api/v1/engine/connected-accounts", headers=AUTH).status_code == 503
    assert client.get("/api/v1/accounts/demo_alpha/cities").status_code == 401
    assert client.get("/api/v1/warehouses/demo_alpha").status_code == 401


@pytest.mark.parametrize("kwargs", [
    {"accounts_path": "/private/real-accounts.toml"},
    {"snapshot_provider": lambda _id: []},
    {"session_coordinator": object()},
    {"ipc_client": object()},
    {"task_controller": object()},
    {"enable_account_editing": True},
])
def test_demo_refuses_any_real_data_source_or_engine_control(kwargs):
    with pytest.raises(ValueError, match="Synthetic demo"):
        create_app(demo_mode=True, api_token=TOKEN, **kwargs)


def test_demo_uses_only_synthetic_fixtures():
    assert all(a.id.startswith("demo_") for a in demo_accounts())
    for account in demo_accounts():
        cities = demo_warehouses(account.id)
        assert cities
        assert all(c.city_name.startswith("DEMO ") for c in cities)
        assert all(c.account_id == account.id for c in cities)
        assert all(c.resources.capacity is not None for c in cities)
    with pytest.raises(KeyError):
        demo_warehouses("production")


def test_cli_rejects_incompatible_demo_options(capsys):
    from daedalus.cli import main

    for extra in (
        ["--connect-existing-ipc"],
        ["--enable-task-control", "--connect-existing-ipc"],
        ["--enable-account-editing"],
        ["--accounts-file", "/tmp/private.toml"],
        ["--task-ledger", "/tmp/request-ledger.db", "--enable-task-control", "--connect-existing-ipc"],
    ):
        with pytest.raises(SystemExit) as exc:
            main(["serve", "--demo", *extra])
        assert exc.value.code == 2
        assert "demo" in capsys.readouterr().err.lower()


def test_cli_demo_starts_with_only_synthetic_api(monkeypatch, tmp_path):
    import uvicorn

    from daedalus.cli import main

    captured = []

    def fake_run(app, **options):
        captured.append((app, options))

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-never-created"))
    monkeypatch.setenv("DAEDALUS_API_TOKEN", TOKEN)
    monkeypatch.setattr(uvicorn, "run", fake_run)
    assert main(["serve", "--demo"]) == 0
    assert len(captured) == 1
    app, options = captured[0]
    assert options["host"] == "127.0.0.1"
    assert options["port"] == 8765
    response = TestClient(app).get("/api/v1/health")
    assert response.json()["synthetic_demo"] is True
    assert response.json()["mode"] == "synthetic_demo"
    assert not (tmp_path / "config-never-created").exists()


def test_demo_client_handles_health_and_synthetic_accounts():
    import httpx

    app = create_app(demo_mode=True, api_token=TOKEN)

    # Keep test completely in-process; no TCP server or Gameforge call.
    client = TestClient(app)
    health = client.get("/api/v1/health").json()
    assert health["synthetic_demo"] is True
    with DaedalusClient(
        "http://127.0.0.1:8765", TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status_code=client.request(
                    request.method, request.url.path,
                    headers={"Authorization": request.headers.get("authorization", "")},
                ).status_code,
                json=client.request(
                    request.method, request.url.path,
                    headers={"Authorization": request.headers.get("authorization", "")},
                ).json(),
            )
        ),
    ) as desktop:
        assert desktop.health()["mode"] == "synthetic_demo"
        assert desktop.accounts()[0]["synthetic"] is True
        assert desktop.warehouses("demo_alpha")[0]["city_name"].startswith("DEMO ")
