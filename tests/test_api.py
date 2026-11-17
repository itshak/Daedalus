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


def test_coordinator_state_is_readable_but_cannot_trigger_login(account_file, tmp_path):
    from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
    from daedalus.accounts import load_accounts

    manager = AccountSessionCoordinator(load_accounts(account_file), state_dir=tmp_path / "leases")
    client = TestClient(
        create_app(accounts_path=account_file, api_token=TOKEN, session_coordinator=manager)
    )
    headers = {"Authorization": f"Bearer {TOKEN}"}
    endpoint = "/api/v1/accounts/alpha/session"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=headers).json() == {
        "account_id": "alpha", "session_status": "not_connected"
    }
    assert client.get("/api/v1/accounts/unknown/session", headers=headers).status_code == 404
    with manager.acquire("alpha") as owned:
        assert client.get(endpoint, headers=headers).json()["session_status"] == "validating_session"
        assert client.get("/api/v1/accounts", headers=headers).json()["accounts"][0][
            "session_status"
        ] == "validating_session"
        owned.transition(SessionPhase.NEEDS_ASSISTANCE)
        assert client.get(endpoint, headers=headers).json()["session_status"] == "needs_assistance"
        assert client.get("/api/v1/health").json()["authenticated_workers"] == 0
        owned.transition(SessionPhase.ASSISTED_LOGIN)
        owned.transition(SessionPhase.VALIDATING_HANDOFF)
        owned.transition(SessionPhase.AUTHENTICATED)
        assert client.get("/api/v1/health").json()["authenticated_workers"] == 1
        assert client.get(endpoint, headers=headers).json()["session_status"] == "authenticated"
    assert client.get(endpoint, headers=headers).json()["session_status"] == "not_connected"
    assert client.get("/api/v1/health").json()["authenticated_workers"] == 0
    # These endpoints are strictly GET-only; none can launch authentication.
    assert client.post(endpoint, headers=headers).status_code == 405


def test_mismatched_coordinator_rejected(account_file, tmp_path):
    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import Account

    manager = AccountSessionCoordinator(
        [Account(id="different", world="s302-en", player="Fake", label="Fake", enabled=True)],
        state_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="same accounts"):
        create_app(accounts_path=account_file, api_token=TOKEN, session_coordinator=manager)


def test_same_id_but_different_player_coordinator_rejected(account_file, tmp_path):
    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import Account

    mismatched = AccountSessionCoordinator(
        [Account(id="alpha", world="s301-en", player="DifferentPlayer", label="ExamplePlayer", enabled=True)],
        state_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="same accounts"):
        create_app(accounts_path=account_file, api_token=TOKEN, session_coordinator=mismatched)


def test_existing_ipc_bridge_accounts_and_cities_are_authenticated(account_file):
    class FakeIPC:
        def __init__(self):
            self.calls = []

        def list_sessions(self):
            self.calls.append("list_sessions")
            return [
                {"world": "s301-en", "player": "ExamplePlayer"},
                {"world": "s999-en", "player": "OtherUnconfigured"},
            ]

        def cities(self, account):
            self.calls.append((account.id, account.world, account.player))
            return [{"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}]

    connector = FakeIPC()
    app = create_app(accounts_path=account_file, api_token=TOKEN, ipc_client=connector)
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get("/api/v1/engine/connected-accounts").status_code == 401
    assert client.get("/api/v1/accounts/alpha/cities").status_code == 401
    assert connector.calls == []
    response = client.get("/api/v1/engine/connected-accounts", headers=auth)
    assert response.json() == {
        "connected_account_ids": ["alpha"], "engine_mode": "existing_session_only"
    }
    assert "OtherUnconfigured" not in response.text
    result = client.get("/api/v1/accounts/alpha/cities", headers=auth)
    assert result.status_code == 200
    assert result.json()["cities"][0]["id"] == 42
    assert connector.calls == ["list_sessions", ("alpha", "s301-en", "ExamplePlayer")]
    assert client.post("/api/v1/accounts/alpha/cities", headers=auth).status_code == 405
    assert client.get("/api/v1/accounts/not-configured/cities", headers=auth).status_code == 404


def test_existing_ipc_failure_is_generic_without_secrets(account_file):
    from daedalus.engine_ipc import EngineIPCUnavailable

    class BrokenIPC:
        def list_sessions(self):
            raise EngineIPCUnavailable("private-token-from-game")

        def cities(self, _account):
            raise EngineIPCUnavailable("private-cookie-from-game")

    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN,
                                  ipc_client=BrokenIPC()))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    for endpoint in ("/api/v1/engine/connected-accounts", "/api/v1/accounts/alpha/cities"):
        response = client.get(endpoint, headers=auth)
        assert response.status_code == 503
        assert "private-" not in response.text


def test_ipc_disabled_by_default_even_with_configured_account(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    assert client.get("/api/v1/accounts/alpha/cities", headers=auth).status_code == 503
    assert client.get("/api/v1/engine/connected-accounts", headers=auth).status_code == 503


def test_readonly_warehouse_provider_uses_existing_ipc_if_explicitly_attached(account_file):
    from daedalus.warehouse import CityWarehouseSnapshot, WarehouseResources

    class MockExisting:
        def warehouses(self, account):
            assert account.id == "alpha"
            return [CityWarehouseSnapshot(
                account_id="alpha", city_id=42, city_name="Athens",
                captured_at="2026-11-18T10:00:00+00:00",
                resources=WarehouseResources(unsecured={"wood": 100, "wine": 0,
                    "marble": None, "glass": None, "sulfur": None}, capacity=50000),
            )]

    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN,
                                   ipc_client=MockExisting()))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    response = client.get("/api/v1/warehouses/alpha", headers=auth)
    assert response.status_code == 200
    assert response.json()["cities"][0]["resources"]["unsecured"]["wood"] == 100
    assert response.json()["cities"][0]["resources"]["unsecured"]["marble"] is None
