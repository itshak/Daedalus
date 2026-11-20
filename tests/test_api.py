"""Read-only API contract tested without live credentials or game network access."""

import pytest
from fastapi.testclient import TestClient

from daedalus.api import create_app
from daedalus.engine_ipc import EngineIPCUnavailable
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


def test_task_control_requires_explicit_enablement_and_authorization(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    body = {
        "task": "alertAttacks", "config": {"minutes": 10},
        "request_id": "12345678-1234-4123-8123-123456789abc", "confirmed": True,
    }
    assert client.get("/api/v1/task-control").status_code == 401
    assert client.get("/api/v1/task-control", headers=auth).json()["enabled"] is False
    assert client.post("/api/v1/accounts/alpha/tasks", json=body).status_code == 401
    assert client.post("/api/v1/accounts/alpha/tasks", json=body, headers=auth).status_code == 503
    assert client.get("/api/v1/accounts/alpha/tasks", headers=auth).status_code == 503
    assert client.post("/api/v1/accounts/alpha/tasks/" + "f"*24 + "/stop",
                       headers=auth).status_code == 503
    assert client.get("/api/v1/health").json()["mode"] == "read_only"


def test_new_task_contract_routes_keep_account_and_confirmation_scoped(account_file):
    task_id = "f"*24

    class MockTaskController:
        def __init__(self):
            self.calls = []

        def start(self, account_id, task, config, request_id, *, confirmed):
            self.calls.append(("start", account_id, task, config, request_id, confirmed))
            if not confirmed:
                raise ValueError("Explicit confirmation is required")
            return {"task_id": task_id, "status": "started", "request_id": request_id}

        def list_tasks(self, account_id):
            self.calls.append(("list", account_id))
            return {"account_id": account_id, "engine_tasks": [
                {"task_id": task_id, "task": "alertAttacks", "status": "running"}
            ], "requests": []}

        def stop(self, account_id, selected_task):
            self.calls.append(("stop", account_id, selected_task))
            return {"task_id": selected_task, "status": "stopped"}

        def acknowledge_uncertain_request(self, account_id, request_id, *, confirmed):
            self.calls.append(("ack", account_id, request_id, confirmed))
            return {"request_id": request_id, "status": "operator_reconciled"}

    mock = MockTaskController()
    client = TestClient(create_app(
        accounts_path=account_file, api_token=TOKEN, task_controller=mock,
    ))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    body = {
        "task": "alertAttacks", "config": {"minutes": 10},
        "request_id": "12345678-1234-4123-8123-123456789abc",
    }
    assert client.get("/api/v1/task-control", headers=auth).json()["enabled"] is True
    assert client.get("/api/v1/health").json()["mode"] == "task_control_opt_in"
    assert client.get("/api/v1/capabilities", headers=auth).json()["structured_engine_dispatch"]
    assert client.post("/api/v1/accounts/alpha/tasks", json=body,
                       headers=auth).status_code == 422
    assert client.post("/api/v1/accounts/unknown/tasks", json={**body, "confirmed": True},
                       headers=auth).status_code == 404
    started = client.post("/api/v1/accounts/alpha/tasks",
                          json={**body, "confirmed": True}, headers=auth)
    assert started.status_code == 200, started.text
    assert started.json()["task_id"] == task_id
    tasks = client.get("/api/v1/accounts/alpha/tasks", headers=auth)
    assert tasks.status_code == 200
    assert tasks.json()["engine_tasks"][0]["status"] == "running"
    stopped = client.post(f"/api/v1/accounts/alpha/tasks/{task_id}/stop", headers=auth)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert mock.calls[-1] == ("stop", "alpha", task_id)
    assert mock.calls[1] == ("start", "alpha", "alertAttacks", {"minutes": 10},
                            body["request_id"], True)


def test_api_responses_for_remote_https_never_cache_private_account_data(account_file):
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN))
    for path, headers, expected in (
        ("/api/v1/health", {}, 200),
        ("/api/v1/accounts", {}, 401),
        ("/api/v1/accounts", {"Authorization": f"Bearer {TOKEN}"}, 200),
        ("/api/v1/warehouses/alpha", {"Authorization": f"Bearer {TOKEN}"}, 503),
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == expected
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"


def test_building_inventory_api_authorizes_account_city_and_never_dispatches(account_file):
    from daedalus.engine_ipc import EngineIPCUnavailable

    class BuildingIPC:
        def __init__(self):
            self.calls = []

        def buildings(self, account, city_id):
            self.calls.append((account.id, account.world, account.player, city_id))
            if city_id != 42:
                raise ValueError("Different city")
            return [{"position": 1, "level": 8, "name": "Town Hall",
                     "building": "townHall", "busy": False, "can_upgrade": True}]

    ipc = BuildingIPC()
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN, ipc_client=ipc))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    url = "/api/v1/accounts/alpha/cities/42/buildings"
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/accounts/unknown/cities/42/buildings", headers=auth).status_code == 404
    assert client.get("/api/v1/accounts/alpha/cities/0/buildings", headers=auth).status_code == 422
    assert ipc.calls == []
    response = client.get(url, headers=auth)
    assert response.status_code == 200
    assert response.json()["buildings"][0]["name"] == "Town Hall"
    assert ipc.calls == [("alpha", "s301-en", "ExamplePlayer", 42)]
    assert client.get("/api/v1/accounts/alpha/cities/99/buildings", headers=auth).status_code == 404
    assert client.post(url, headers=auth).status_code == 405
    assert len(ipc.calls) == 2

    class BrokenIPC:
        def buildings(self, _account, _city_id):
            raise EngineIPCUnavailable("private-credential-value")

    broken = TestClient(create_app(accounts_path=account_file, api_token=TOKEN,
                                   ipc_client=BrokenIPC()))
    failed = broken.get(url, headers=auth)
    assert failed.status_code == 503
    assert "private-credential" not in failed.text


def test_readonly_construction_preview_requires_auth_and_does_not_start_tasks(account_file):
    class PlanningIPC:
        def __init__(self):
            self.calls = []

        def construction_preview(self, account, city_id, upgrades):
            self.calls.append((account.id, city_id, upgrades))
            return {"account_id": account.id, "city_id": city_id,
                    "ready": True, "costs": [1000, 0, 0, 0, 0],
                    "available": [2000, 0, 0, 0, 0],
                    "missing": [0] * 5, "estimated_seconds": 120,
                    "config": {"city_id": city_id, "city_name": "Athens",
                               "buildings": [], "shipments": [], "expand_overall": True,
                               "wait_resources": False, "construction_queue": [],
                               "total_time": 120}}

    ipc = PlanningIPC()
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN, ipc_client=ipc))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    path = "/api/v1/accounts/alpha/cities/42/construction-preview"
    upgrades = [{"position": 3, "target_level": 10}]
    assert client.post(path, json={"upgrades": upgrades}).status_code == 401
    assert client.post("/api/v1/accounts/unknown/cities/42/construction-preview",
                       json={"upgrades": upgrades}, headers=auth).status_code == 404
    assert client.post(path, json={"upgrades": [{"position": 2, "target_level": -1}]},
                       headers=auth).status_code == 422
    assert ipc.calls == []
    response = client.post(path, json={"upgrades": upgrades}, headers=auth)
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert ipc.calls == [("alpha", 42, upgrades)]
    assert client.get(path, headers=auth).status_code == 405


def test_construction_preview_sanitizes_engine_exceptions(account_file):
    from daedalus.engine_ipc import EngineIPCUnavailable

    class BrokenIPC:
        def construction_preview(self, _account, _city_id, _upgrades):
            raise EngineIPCUnavailable("private-game-cookie-string")

    client = TestClient(create_app(
        accounts_path=account_file, api_token=TOKEN, ipc_client=BrokenIPC(),
    ))
    result = client.post(
        "/api/v1/accounts/alpha/cities/42/construction-preview",
        json={"upgrades": [{"position": 3, "target_level": 6}]},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert result.status_code == 503
    assert "private-game-cookie" not in result.text


def test_readonly_trainable_catalog_requires_authorized_owned_city(account_file):
    class TrainableIPC:
        def __init__(self):
            self.calls = []

        def trainable_units(self, account, city_id, *, train_troops):
            self.calls.append((account.id, city_id, train_troops))
            return {
                "account_id": account.id, "city_id": city_id,
                "train_troops": train_troops,
                "city": {"id": str(city_id), "pos": "3", "cityName": "Athens"},
                "units": [{"unit_type_id": 301, "local_name": "Swordsman",
                           "costs": {"wood": 100, "citizens": 1}}],
                "available": [1000, 0, 0, 0, 0], "free_citizens": 12,
            }

    ipc = TrainableIPC()
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN, ipc_client=ipc))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    path = "/api/v1/accounts/alpha/cities/42/trainable-units?train_troops=false"
    assert client.get(path).status_code == 401
    assert client.get("/api/v1/accounts/unknown/cities/42/trainable-units",
                      headers=auth).status_code == 404
    assert client.get("/api/v1/accounts/alpha/cities/0/trainable-units",
                      headers=auth).status_code == 422
    assert not ipc.calls
    response = client.get(path, headers=auth)
    assert response.status_code == 200
    assert response.json()["train_troops"] is False
    assert ipc.calls == [("alpha", 42, False)]
    assert client.post(path, json={}, headers=auth).status_code == 405


def test_market_quotes_need_auth_and_are_read_only(account_file):
    class MarketIPC:
        def __init__(self):
            self.calls = []

        def market_quotes(self, account, city_id, resource_type, side):
            self.calls.append((account.id, city_id, resource_type, side))
            return {
                "account_id": account.id, "city_id": city_id,
                "resource_type": resource_type, "side": side,
                "city": {"id": str(city_id), "pos": 3, "rango": 4,
                         "name": "Athens", "cityName": "Athens",
                         "availableResources": [1000, 0, 0, 0, 0]},
                "offers": [], "price_min": None, "price_max": None,
                "sell_market_capacity": None, "currently_on_sale": None,
            }

    ipc = MarketIPC()
    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN, ipc_client=ipc))
    auth = {"Authorization": f"Bearer {TOKEN}"}
    path = ("/api/v1/accounts/alpha/cities/42/market-quotes"
            "?resource_type=0&side=buy")
    assert client.get(path).status_code == 401
    assert client.get(path.replace("/alpha/", "/unknown/"), headers=auth).status_code == 404
    assert client.get(path.replace("side=buy", "side=send"), headers=auth).status_code == 422
    assert client.get(path.replace("resource_type=0", "resource_type=9"), headers=auth).status_code == 422
    assert not ipc.calls
    resp = client.get(path, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["side"] == "buy"
    assert ipc.calls == [("alpha", 42, 0, "buy")]
    assert client.post(path, json={}, headers=auth).status_code == 405


def test_market_quote_service_errors_hide_game_session_data(account_file):
    class BadMarket:
        def market_quotes(self, _account, _city_id, _resource_type, _side):
            raise EngineIPCUnavailable("user-cookie-SECRET-do-not-leak")

    client = TestClient(create_app(accounts_path=account_file, api_token=TOKEN,
                                   ipc_client=BadMarket()))
    response = client.get(
        "/api/v1/accounts/alpha/cities/42/market-quotes?resource_type=0&side=buy",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 503
    assert "user-cookie" not in response.text
