"""Real loopback socket tests with a synthetic IPC worker, never Gameforge."""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import contextmanager

import pytest

from daedalus.accounts import Account
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient

SECRET = "a" * 64  # synthetic, low-entropy test-only marker
ALPHA = Account("alpha", "s301-en", "ExamplePlayer", "Alpha", True)


@contextmanager
def fake_worker(tmp_path, responder=None):
    descriptor = tmp_path / "ipc.json"
    listen = socket.socket()
    listen.bind(("127.0.0.1", 0))
    listen.listen(5)
    listen.settimeout(0.5)
    stop = threading.Event()
    requested = []

    def reply(msg):
        if responder is not None:
            return responder(msg)
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": "s301-en", "player": "ExamplePlayer"}]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}]}
        if msg["action"] == "preview_construction_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "city_id": msg["city_id"],
                    "plan": {"ready": True, "costs": [1000, 0, 100, 0, 0],
                             "missing": [0, 0, 0, 0, 0],
                             "available": [3000, 0, 500, 0, 0],
                             "estimated_seconds": 120,
                             "config": {
                                 "city_id": msg["city_id"], "city_name": "Athens",
                                 "buildings": [{
                                     "position": 1, "name": "Town Hall", "building": "townHall",
                                     "level": 11, "isBusy": False, "upgradeTo": 12,
                                     "constructionTime": 120, "constructionTimes": [120],
                                 }],
                                 "shipments": [], "expand_overall": True, "wait_resources": False,
                                 "construction_queue": [120], "total_time": 120,
                             }}}
        if msg["action"] == "list_buildings_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "city_id": msg["city_id"], "buildings": [
                        {"position": 1, "name": "Town Hall", "building": "townHall",
                         "level": 12, "busy": False, "can_upgrade": True},
                        {"position": 3, "name": "Academy", "building": "academy",
                         "level": 6, "busy": True, "can_upgrade": False},
                    ]}
        if msg["action"] == "list_workshop_upgrades_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "city_id": msg["city_id"], "workshop_level": 12,
                    "upgrades": [
                        {"unit_id": "101", "name": "Swordsman",
                         "upgrade_type": "offensive", "description": "Attack",
                         "current_level": 4, "max_level": 12},
                        {"unit_id": "101", "name": "Swordsman",
                         "upgrade_type": "defensive", "description": "Defense",
                         "current_level": 5, "max_level": 12},
                    ]}
        if msg["action"] == "list_trainables_existing":
            return {
                "status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                "city_id": msg["city_id"], "train_troops": msg["train_troops"],
                "city": {"id": str(msg["city_id"]), "cityName": "Athens", "pos": "3"},
                "units": [
                    {"unit_type_id": 301, "local_name": "Swordsman",
                     "identifier": "swordsman", "costs": {
                         "wood": 100, "sulfur": 50, "citizens": 1,
                     }},
                ],
                "available": [3000, 0, 500, 0, 1000], "free_citizens": 20,
            }
        if msg["action"] == "list_academies_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "academies": [{"city_id": 42, "city_name": "Athens", "position": 5,
                                   "crystal": 400000, "cooldown": False,
                                   "can_experiment_now": True}]}
        if msg["action"] == "market_quotes_existing":
            side = msg["market_side"]
            city = {"id": str(msg["city_id"]), "name": "Athens", "cityName": "Athens",
                    "pos": 4, "rango": 3, "availableResources": [5000, 500, 0, 0, 0]}
            offer = {"ciudadDestino": "Seller", "jugadorAComprar": "Trader",
                     "amountAvailable": 500, "tipo": "wood", "precio": 7,
                     "destinationCityId": "200", "cityId": str(msg["city_id"]),
                     "position": "4", "type": "444", "resource": "resource"}
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "city_id": msg["city_id"], "side": side,
                    "resource_type": msg["resource_type"], "city": city,
                    "offers": [offer] if side == "buy" else
                              [["Buyer", "Player", 500, 8, 3, 200]]
                              if side == "sell_to_offers" else [],
                    "price_min": 1 if side == "create_offer" else None,
                    "price_max": 30 if side == "create_offer" else None,
                    "sell_market_capacity": 2000 if side == "create_offer" else None,
                    "currently_on_sale": 0 if side == "create_offer" else None}
        if msg["action"] == "warehouse_snapshots_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer", "cities": [
                {"city_id": 42, "city_name": "Athens", "unsecured": {
                     "wood": "2,970,123", "wine": "0", "glass": "1.2K"}, "capacity": "1,000,000", "island": "8:20"}
            ]}
        return {"status": "ok", "pid": os.getpid()}

    def run():
        while not stop.is_set():
            try:
                conn, _ = listen.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    data = b""
                    while b"\n" not in data:
                        data += conn.recv(8192)
                    msg = json.loads(data)
                    requested.append({key: val for key, val in msg.items() if key != "authkey"})
                    assert msg["authkey"] == SECRET
                    conn.sendall((json.dumps(reply(msg)) + "\n").encode())
                except (OSError, ValueError):
                    break

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    descriptor.write_text(json.dumps({
        "pid": os.getpid(), "port": listen.getsockname()[1], "host": "127.0.0.1",
        "authkey": SECRET,
    }), encoding="utf-8")
    if os.name != "nt":
        descriptor.chmod(0o600)
    try:
        yield ExistingIPCClient(descriptor), requested, descriptor
    finally:
        stop.set()
        listen.close()
        thread.join(timeout=3)


def test_real_socket_reads_existing_accounts_and_cities(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        assert client.has_account(ALPHA)
        assert client.cities(ALPHA) == [
            {"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}
        ]
        assert [r["action"] for r in requests] == [
            "list_sessions", "list_sessions", "list_cities_existing"
        ]
        assert all(r.get("world") in (None, "s301-en") for r in requests)
        assert all("email" not in r for r in requests)


def test_no_engine_rpc_can_start_tasks_or_create_sessions(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        for action in ("start_task", "list_cities", "stop_task", "restore_session"):
            with pytest.raises(ValueError, match="read-only"):
                client.request(action)
        assert requests == []


def test_no_matching_session_refused_before_city_query(tmp_path):
    different = Account("beta", "s302-en", "Different", "Other", True)
    with fake_worker(tmp_path) as (client, requests, _):
        with pytest.raises(EngineIPCUnavailable, match="No unique"):
            client.cities(different)
        assert [x["action"] for x in requests] == ["list_sessions"]


def test_mismatched_identity_in_response_is_rejected(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": "s302-en", "username": ALPHA.player, "cities": []}

    with fake_worker(tmp_path, responder=responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="another account"
    ):
        client.cities(ALPHA)


def test_non_owner_file_mode_refused_before_connect(tmp_path):
    with fake_worker(tmp_path) as (client, requests, descriptor):
        if os.name == "nt":
            pytest.skip("POSIX file permissions")
        descriptor.chmod(0o644)
        with pytest.raises(EngineIPCUnavailable, match="owner-only"):
            client.list_sessions()
        assert requests == []


def test_symlink_descriptor_rejected(tmp_path):
    with fake_worker(tmp_path) as (_client, requests, path):
        link = tmp_path / "alias.json"
        try:
            link.symlink_to(path)
        except OSError:
            pytest.skip("Symlinks unavailable")
        with pytest.raises(EngineIPCUnavailable, match="symlink"):
            ExistingIPCClient(link).list_sessions()
        assert requests == []


@pytest.mark.parametrize("patch", [
    {"host": "192.0.2.1"}, {"port": 0}, {"pid": -3}, {"authkey": "short"}
])
def test_bad_descriptor_rejected_without_socket(tmp_path, patch):
    with fake_worker(tmp_path) as (client, requests, path):
        info = json.loads(path.read_text())
        info.update(patch)
        path.write_text(json.dumps(info))
        if os.name != "nt":
            path.chmod(0o600)
        with pytest.raises(EngineIPCUnavailable):
            client.list_sessions()
        assert requests == []


def test_missing_descriptor_rejected_without_creating_files(tmp_path):
    client = ExistingIPCClient(tmp_path / "does-not-exist" / "ipc.json")
    with pytest.raises(EngineIPCUnavailable):
        client.list_sessions()
    assert list(tmp_path.iterdir()) == []


def test_engine_error_contents_are_redacted(tmp_path):
    with fake_worker(
        tmp_path,
        responder=lambda _req: {"status": "error", "error": "game-secret-should-be-redacted"},
    ) as (client, _, _):
        with pytest.raises(EngineIPCUnavailable) as info:
            client.list_sessions()
        assert "game-secret" not in str(info.value)


def test_warehouse_resources_end_to_end_over_real_ipc_socket(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        snapshots = client.warehouses(ALPHA)
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert snapshot.city_id == 42
        assert snapshot.resources.unsecured["wood"] == 2_970_123
        assert snapshot.resources.unsecured["wine"] == 0
        assert snapshot.resources.unsecured["glass"] == 1200
        assert snapshot.resources.unsecured["marble"] is None
        assert snapshot.resources.capacity == 1_000_000
        assert snapshot.island == "8:20"
        assert [r["action"] for r in requests] == [
            "list_sessions", "warehouse_snapshots_existing"
        ]


def test_empty_or_bad_warehouse_ipc_data_refused(tmp_path):
    def bad_data(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                "cities": [{"city_id": 42, "city_name": "Athens", "unsecured": {
                    "wood": "raw-session-cookie-value"}, "capacity": None}]}

    with fake_worker(tmp_path, responder=bad_data) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="numeric"
    ):
        client.warehouses(ALPHA)


def test_current_task_transport_rejects_old_pid_action_names(tmp_path):
    """The legacy PID API is gone; only the ID-scoped control transport remains."""
    from daedalus.engine_ipc import ControlledIPCClient

    calls = []
    task_id = "f" * 24

    def respond(msg):
        calls.append(msg["action"])
        if msg["action"] == "start_task_existing":
            return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                    "task_id": task_id, "pid": 81001}
        if msg["action"] == "list_tasks_existing":
            return {"status": "ok", "world": ALPHA.world, "player": ALPHA.player,
                    "tasks": [{"task_id": task_id, "task": "alertAttacks",
                               "status": "running", "pid": 81001}]}
        if msg["action"] == "stop_task_existing":
            return {"status": "ok", "task_id": task_id, "task_status": "stopped"}
        return {"status": "error", "error": "unknown"}

    with fake_worker(tmp_path, responder=respond) as (readonly, _requests, descriptor):
        controller = ControlledIPCClient(descriptor)
        with pytest.raises(ValueError, match="read-only"):
            readonly.request("stop_managed_task")
        receipt = controller.start_managed_task(ALPHA, "alertAttacks", {"minutes": 10}, "12345678-1234-4123-8123-123456789abc")
        assert receipt["task_id"] == task_id
        assert controller.list_managed_tasks(ALPHA)[0]["task_id"] == task_id
        assert controller.stop_managed_task(ALPHA, task_id)["status"] == "stopped"
        with pytest.raises(ValueError):
            controller.stop_managed_task(ALPHA, "-1")
        assert calls == ["start_task_existing", "list_tasks_existing", "stop_task_existing"]


def test_warehouse_ipc_rejects_arbitrary_island_strings(tmp_path):
    def reply(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                "cities": [{"city_id": 42, "city_name": "Athens",
                            "unsecured": {"wood": "0"}, "capacity": None,
                            "island": "secret-token-example"}]}

    with (
        fake_worker(tmp_path, responder=reply) as (client, _, _),
        pytest.raises(EngineIPCUnavailable, match="island"),
    ):
        client.warehouses(ALPHA)


def test_active_validation_is_fixed_scope_and_nonsecret(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"},
            ]}
        if msg["action"] == "validate_session_existing":
            return {"status": "ok", "world": "s301-en",
                    "username": "ExamplePlayer", "session_valid": True,
                    "player_attested": True}
        return {"status": "error", "error": "Unexpected request"}

    with fake_worker(tmp_path, responder) as (client, requested, _):
        assert client.validate_account(ALPHA) is True
    assert [row["action"] for row in requested] == [
        "list_sessions", "validate_session_existing",
    ]
    assert requested[-1] == {
        "action": "validate_session_existing", "world": "s301-en",
        "player": "ExamplePlayer",
    }


@pytest.mark.parametrize("invalid", [
    {"status": "ok", "world": "s301-en", "username": "ExamplePlayer", "session_valid": True},
    {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
     "session_valid": True, "player_attested": False},
    {"status": "ok", "world": "s301-en", "username": "ExamplePlayer", "session_valid": "true"},
    {"status": "ok", "world": "s301-en", "username": "Other", "session_valid": True},
    {"status": "ok", "world": "s302-en", "username": "ExamplePlayer", "session_valid": True},
    {"status": "ok", "world": "s301-en", "username": "ExamplePlayer"},
])
def test_active_validation_refuses_malformed_or_cross_account_response(tmp_path, invalid):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"},
            ]}
        return invalid

    with fake_worker(tmp_path, responder) as (client, requested, _):
        with pytest.raises(EngineIPCUnavailable, match="validation reply"):
            client.validate_account(ALPHA)
        assert [row["action"] for row in requested] == [
            "list_sessions", "validate_session_existing",
        ]


def test_active_validation_refuses_missing_existing_session_without_get(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": []}
        pytest.fail("Should not issue an active validation request")

    with fake_worker(tmp_path, responder) as (client, requested, _):
        assert client.validate_account(ALPHA) is False
        assert [item["action"] for item in requested] == ["list_sessions"]


def test_building_inventory_uses_existing_session_and_owned_city(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        buildings = client.buildings(ALPHA, 42)
        assert [(row["position"], row["level"]) for row in buildings] == [(1, 12), (3, 6)]
        assert requests[-1] == {"action": "list_buildings_existing",
                                "world": "s301-en", "player": "ExamplePlayer", "city_id": 42}
        with pytest.raises(ValueError, match="belong"):
            client.buildings(ALPHA, 43)
        assert all(row["action"] != "start_task_existing" for row in requests)


def test_building_inventory_rejects_cross_account_ipc_data(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"}
            ]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wine"}]}
        if msg["action"] == "list_buildings_existing":
            return {"status": "ok", "world": "s302-en", "username": "OtherPlayer",
                    "city_id": 42, "buildings": []}
        raise AssertionError("No other IPC action expected")

    with fake_worker(tmp_path, responder) as (client, requests, _):
        with pytest.raises(EngineIPCUnavailable, match="another account"):
            client.buildings(ALPHA, 42)
        assert not any(row["action"].startswith("start_task") for row in requests)


def test_building_inventory_rejects_malformed_and_duplicate_positions(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"}]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wine"}]}
        return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                "city_id": 42, "buildings": [
                    {"position": 1, "level": 10, "name": "Town Hall",
                     "building": "townHall", "busy": False, "can_upgrade": True},
                    {"position": 1, "level": 20, "name": "Academy",
                     "building": "academy", "busy": False, "can_upgrade": True},
                ]}
    with fake_worker(tmp_path, responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="invalid building"
    ):
        client.buildings(ALPHA, 42)


def test_construction_preview_readonly_and_city_scoped(tmp_path):
    upgrades = [{"position": 1, "target_level": 12}]
    with fake_worker(tmp_path) as (client, requests, _):
        result = client.construction_preview(ALPHA, 42, upgrades)
        assert result["ready"] is True
        assert result["config"]["buildings"][0]["upgradeTo"] == 12
        assert result["costs"] == [1000, 0, 100, 0, 0]
        assert requests[-1] == {
            "action": "preview_construction_existing",
            "world": "s301-en", "player": "ExamplePlayer", "city_id": 42,
            "upgrades": upgrades,
        }
        with pytest.raises(ValueError, match="not owned"):
            client.construction_preview(ALPHA, 99, upgrades)
        with pytest.raises(ValueError, match="Invalid construction upgrade"):
            client.construction_preview(ALPHA, 42, [{"position": "x", "target_level": 10}])
        assert all("start_task" not in request["action"] for request in requests)


def test_construction_preview_rejects_wrong_account_identity(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"}]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wine"}]}
        return {"status": "ok", "world": "s302-en", "username": "WrongPlayer", "city_id": 42,
                "plan": {"ready": True}}
    with fake_worker(tmp_path, responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="different game account"
    ):
        client.construction_preview(ALPHA, 42, [{"position": 1, "target_level": 7}])


def test_workshop_upgrades_are_account_bound_and_never_start_game_tasks(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        data = client.workshop_upgrades(ALPHA, 42)
        assert data["workshop_level"] == 12
        assert [(row["unit_id"], row["upgrade_type"]) for row in data["upgrades"]] == [
            ("101", "offensive"), ("101", "defensive")
        ]
        assert requests[-1] == {
            "action": "list_workshop_upgrades_existing",
            "world": "s301-en", "player": "ExamplePlayer", "city_id": 42,
        }
        with pytest.raises(ValueError, match="not owned"):
            client.workshop_upgrades(ALPHA, 99)
        assert not any("start_task" in row["action"] for row in requests)


def test_workshop_malformed_engine_response_rejected_before_ui(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [
                {"world": "s301-en", "player": "ExamplePlayer"}]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wine"}]}
        return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                "city_id": 42, "workshop_level": 10, "upgrades": [{
                    "unit_id": "101", "name": "Sword", "upgrade_type": "offensive",
                    "description": "Attack", "current_level": 4, "max_level": 99,
                }]}
    with fake_worker(tmp_path, responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="Malformed workshop"
    ):
        client.workshop_upgrades(ALPHA, 42)


def test_readonly_training_catalog_is_source_scoped_and_contains_actual_costs(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        catalog = client.trainable_units(ALPHA, 42, train_troops=True)
        assert catalog["train_troops"] is True
        assert catalog["units"][0]["unit_type_id"] == 301
        assert catalog["units"][0]["costs"]["wood"] == 100
        assert requests[-1] == {
            "action": "list_trainables_existing",
            "world": "s301-en", "player": "ExamplePlayer",
            "city_id": 42, "train_troops": True,
        }
        with pytest.raises(ValueError, match="not owned"):
            client.trainable_units(ALPHA, 99, train_troops=True)
        with pytest.raises(ValueError, match="Invalid training selection"):
            client.trainable_units(ALPHA, 42, train_troops="yes")
        assert not any("start_task" in request["action"] for request in requests)


@pytest.mark.parametrize("side", ["buy", "sell_to_offers", "create_offer"])
def test_market_quotes_ipc_uses_authorized_city_and_never_starts_trade(tmp_path, side):
    with fake_worker(tmp_path) as (client, requests, _):
        data = client.market_quotes(ALPHA, 42, 0, side)
        assert data["city"]["id"] == "42"
        assert data["side"] == side
        assert requests[-1] == {
            "action": "market_quotes_existing", "world": "s301-en",
            "player": "ExamplePlayer", "city_id": 42,
            "resource_type": 0, "market_side": side,
        }
        with pytest.raises(ValueError, match="not owned"):
            client.market_quotes(ALPHA, 99, 0, side)
        with pytest.raises(ValueError, match="Invalid market selection"):
            client.market_quotes(ALPHA, 42, 5, side)
        assert not any("task" in item["action"] for item in requests)


def test_market_quote_response_from_wrong_world_rejected(tmp_path):
    def responder(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{
                "world": "s301-en", "player": "ExamplePlayer",
            }]}
        if request["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wood"}]}
        return {"status": "ok", "world": "s301-en", "username": "WrongPlayer",
                "city_id": 42, "resource_type": 0, "side": "buy",
                "city": {}, "offers": []}
    with fake_worker(tmp_path, responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable
    ):
        client.market_quotes(ALPHA, 42, 0, "buy")


def test_academy_research_ipc_lists_only_owned_and_real_game_stock(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        result = client.academies(ALPHA)
        assert result["account_id"] == "alpha"
        assert result["academies"] == [
            {"city_id": 42, "city_name": "Athens", "position": 5,
             "crystal": 400000, "cooldown": False, "can_experiment_now": True},
        ]
        assert requests[-1] == {
            "action": "list_academies_existing",
            "world": "s301-en", "player": "ExamplePlayer",
        }
        assert not any("task" in request["action"] for request in requests)


def test_academy_research_ipc_rejects_wrong_city_and_false_readiness(tmp_path):
    def responder(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{
                "world": "s301-en", "player": "ExamplePlayer",
            }]}
        if request["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2",
                                "tradegood": "wine"}]}
        return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                "academies": [{"city_id": 99, "city_name": "Other", "position": 2,
                               "crystal": 50, "cooldown": True,
                               "can_experiment_now": True}]}
    with fake_worker(tmp_path, responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="foreign academy"
    ):
        client.academies(ALPHA)
