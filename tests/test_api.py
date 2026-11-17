"""Read-only API contract tested without live credentials or game network access."""

import pytest
from fastapi.testclient import TestClient

from daedalus.api import create_app
from daedalus.warehouse import CityWarehouseSnapshot, WarehouseResources

TOKEN = "x" * 48
CONFIG = '''
schema = 1
[[accounts]]
id = "alpha"
world = "s301-en"
player = "ExamplePlayer"
'''


@pytest.fixture
def account_file(tmp_path):
    path = tmp_path / "accounts.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def test_requires_a_long_nonempty_api_token(account_file):
    with pytest.raises(ValueError, match="at least 32"):
        create_app(accounts_path=account_file, api_token="")
    with pytest.raises(ValueError, match="at least 32"):
        create_app(accounts_path=account_file, api_token="short")


def test_health_only_reports_readonly_status(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    result = client.get("/api/v1/health")
    assert result.status_code == 200
    assert result.json()["mode"] == "read_only"
    assert result.json()["authenticated_workers"] == 0


def test_account_metadata_requires_authorization(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    assert client.get("/api/v1/accounts").status_code == 401
    assert client.get("/api/v1/accounts", headers={"Authorization": "Bearer wrong"}).status_code == 401
    result = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200
    accounts = result.json()["accounts"]
    assert accounts[0]["id"] == "alpha"
    assert accounts[0]["session_status"] == "not_connected"
    assert "password" not in accounts[0]


def test_capabilities_are_readonly(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    result = client.get("/api/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200
    payload = result.json()
    assert payload["structured_engine_dispatch"] is False
    assert any(item["name"] == "constructionList" for item in payload["operations"])


def test_warehouse_snapshots_require_a_provider(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get("/api/v1/warehouses/alpha").status_code == 401
    assert client.get("/api/v1/warehouses/unknown", headers=auth).status_code == 404
    result = client.get("/api/v1/warehouses/alpha", headers=auth)
    assert result.status_code == 503
    assert "No authenticated" in result.json()["detail"]


def test_injected_mock_snapshot_provider(account_file):
    seen = []

    def fake_provider(account_id):
        seen.append(account_id)
        return [
            CityWarehouseSnapshot(
                account_id=account_id,
                city_id=42,
                city_name="Athens",
                captured_at="2026-11-17T00:00:00+00:00",
                resources=WarehouseResources(
                    unsecured={"wood": 100, "wine": 0, "marble": None,
                               "glass": None, "sulfur": None},
                    capacity=25000,
                ),
            )
        ]

    client = TestClient(create_app(
        accounts_path=account_file,
        api_token=TOKEN,
        snapshot_provider=fake_provider,
    ))
    result = client.get("/api/v1/warehouses/alpha", headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200
    assert seen == ["alpha"]
    data = result.json()
    assert data["cities"][0]["resources"]["unsecured"]["wood"] == 100
    assert data["cities"][0]["resources"]["unsecured"]["marble"] is None
    assert data["cities"][0]["resources"]["capacity"] == 25000


def test_snapshot_provider_errors_are_redacted(account_file):
    def fails(_account_id):
        raise RuntimeError("private-credential-should-not-appear")

    client = TestClient(create_app(
        accounts_path=account_file, api_token=TOKEN, snapshot_provider=fails,
    ))
    result = client.get(
        "/api/v1/warehouses/alpha", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert result.status_code == 503
    assert "private-credential" not in result.text
