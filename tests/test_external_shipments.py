"""External city discovery and recipient identity are account-scoped."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import sendResources as shipments

from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.recovery_reconcile import restart_class_for
from daedalus.recovery_runtime import RoutedAccountIPC
from daedalus.reviewed_operations import validate_island_destinations


def test_engine_lookup_and_recipient_validation(monkeypatch):
    session = Mock(username="Mine")
    session.get.return_value = """jsonData = '{"data":{"50":{"60":[4415]}}}';"""
    island = {"id": "4415", "x": 50, "y": 60, "cities": [
        {"type": "city", "state": "", "id": 9000, "Id": 700, "name": "Town", "Name": "Other"},
        {"type": "city", "state": "", "id": 1, "Id": 100, "name": "Home", "Name": "Mine"},
        {"type": "city", "state": "vacation", "id": 2, "Id": 200, "name": "Away", "Name": "Away"},
        {"type": "empty"},
    ]}
    monkeypatch.setattr(shipments, "get_island", lambda *_a: island)
    data = shipments.native_island_destinations(session, 50, 60)
    assert validate_island_destinations(50, 60, data) == [
        {"id": 9000, "recipient": 700, "island": 4415, "name": "Town", "owner": "Other"}
    ]
    assert not session.post.called
    route = {"from": 1, "to": 9000, "island": 4415, "recipient": 700, "resources": [10, 0, 0, 0, 0]}
    monkeypatch.setattr(shipments, "getIdsOfCities", lambda *_a: (["1"], {"1": {"name": "Home"}}))
    monkeypatch.setattr(shipments, "requireOwnCity", lambda *_a: "1")
    monkeypatch.setattr(shipments, "getCityById", lambda *_a: {"availableResources": [100] * 5})
    assert shipments.prepare_sendResources(session, [route])["routes"][0]["recipient"] == "700"
    assert restart_class_for("sendResources", {"routes": [route], "useFreighters": False}) == "manual"
    island["cities"][0]["Id"] = 701
    with pytest.raises(ValueError, match="destination changed"):
        shipments.prepare_sendResources(session, [route])
    with pytest.raises(ValueError, match="destination changed"):
        shipments._verify_recipient(session, route)
    island["x"] = 49
    with pytest.raises(ValueError, match="coordinates changed"):
        shipments.native_island_destinations(session, 50, 60)


def test_account_router_forwards_every_review_method_and_rejects_other_actions(monkeypatch):
    account = Account("a", "s1-en", "Mine", "Mine", True)
    client = ControlledIPCClient()
    router = RoutedAccountIPC(Mock())
    router._active[account.id] = client
    methods = ("vacation_preview", "attack_inventory", "attack_preview", "grind_preview",
               "station_preview", "build_options", "build_preview", "layout_preview",
               "worker_preview", "donation_preview", "island_destinations")
    for name in methods:
        fn = Mock(return_value=name)
        monkeypatch.setattr(client, name, fn)
        assert getattr(router, name)(account, 123) == name
        fn.assert_called_once_with(account, 123)
    with pytest.raises(AttributeError):
        router.request(account, "anything")


def test_external_inventory_endpoint_checks_account_and_coordinates(monkeypatch, tmp_path):
    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Mine"\n')
    ipc = ControlledIPCClient()
    answer = {"status": "ok", "world": "s1-en", "username": "Mine", "x": 50, "y": 60,
              "cities": [{"id": 9, "recipient": 7, "island": 44, "name": "Town", "owner": "Other"}]}
    monkeypatch.setattr(ipc, "_exchange", lambda *_a, **_kw: answer)
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token, ipc_client=ipc))
    path = "/api/v1/accounts/alpha/island-destinations"
    assert client.get(path + "?x=50&y=60", headers=auth).json()["cities"] == answer["cities"]
    assert client.get(path + "?x=101&y=60", headers=auth).status_code == 422
    assert client.get(path.replace("alpha", "unknown") + "?x=50&y=60", headers=auth).status_code == 404
    answer["username"] = "Other"
    with pytest.raises(EngineIPCUnavailable):
        ipc.island_destinations(Account("alpha", "s1-en", "Mine", "Mine", True), 50, 60)


def test_shipment_capacity_preview_is_read_only(monkeypatch):
    from daedalus.reviewed_operations import validate_shipment_plan, validated_shipment_draft

    session = Mock(username="Mine")
    cities = {
        "1": {"id": "1", "name": "Origin", "availableResources": [1000]*5},
        "2": {"id": "2", "name": "Target", "availableResources": [0]*5,
              "freeSpaceForResources": [50, 100, 100, 100, 100]},
    }
    monkeypatch.setattr(shipments, "getIdsOfCities", lambda *_a: (list(cities), cities))
    monkeypatch.setattr(shipments, "requireOwnCity", lambda _s, cid, _n: str(cid))
    monkeypatch.setattr(shipments, "getCityById", lambda _s, cid: cities[str(cid)])
    monkeypatch.setattr(shipments, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(shipments, "getAvailableShips", lambda _s: 1)
    monkeypatch.setattr(shipments, "getTotalShips", lambda _s: 3)
    draft = {"routes": [{"from": 1, "to": 2, "resources": [400, 50, 0, 0, 0]}],
             "useFreighters": False}
    plan = shipments.preview_native_shipments(session, **draft)
    assert validate_shipment_plan(validated_shipment_draft(draft), plan) == plan
    assert plan["routes"][0]["first_load_limit"] == 100
    assert plan["routes"][0]["minimum_loads"] == 2
    assert plan["ready"]
    assert not session.post.called
    cities["1"]["availableResources"][0] = 399
    with pytest.raises(ValueError):
        shipments.preview_native_shipments(session, **draft)


def test_shipment_ticket_scopes_launch_and_rejects_external_bypass(monkeypatch, tmp_path):
    import uuid

    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.task_control import TaskController

    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Mine"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 1}])
    draft = {"routes": [{"from": 1, "to": 9, "island": 44, "recipient": 7,
                         "resources": [450, 0, 0, 0, 0]}], "useFreighters": False}
    plan = {"routes": [{"from": 1, "to": 9, "origin_name": "Mine", "destination_name": "Other",
                        "resources": [450, 0, 0, 0, 0], "stock": [1000]*5,
                        "destination_space": None, "first_load_limit": 100, "minimum_loads": 2}],
            "useFreighters": False, "capacity": 100, "available_ships": 1, "total_ships": 3, "ready": True}
    monkeypatch.setattr(ipc, "_exchange", lambda p, **_kw: {
        "status": "ok", "world": p["world"], "username": p["player"], "plan": plan})
    monkeypatch.setattr(ipc, "preflight_task", lambda _a, task: {
        "task": task, "ready": True, "reason": "none", "notifications_required": False, "checked": []})
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    starts = []

    def start(account, task, config, rid):
        starts.append((account.id, task, config, rid))
        return {"task_id": "a"*24, "pid": 1234, "task": task, "status": "running"}

    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x"*48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=file, api_token=token, session_coordinator=owner,
                                   task_controller=controller, ipc_client=ipc))
    try:
        path = "/api/v1/accounts/alpha"
        response = client.post(path+"/shipment-plan", headers=auth, json=draft)
        assert response.status_code == 200, response.text
        ticket = response.json()["preview_id"]
        rid = str(uuid.uuid4())
        payload = {"preview_id": ticket, "request_id": rid, "confirmed": True}
        assert client.post(path.replace("alpha","beta")+"/tasks/shipment-start",
                           headers=auth, json=payload).status_code == 409
        assert client.post(path+"/tasks", headers=auth, json={
            "task": "sendResources", "config": draft, "request_id": rid,
            "confirmed": True}).status_code == 422
        assert not starts
        assert client.post(path+"/tasks/shipment-start", headers=auth, json=payload).status_code == 200
        assert starts[0][:3] == ("alpha", "sendResources", draft)
        assert client.post(path+"/tasks/shipment-start", headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
    finally:
        controller.close()


def test_recurring_external_route_checks_recipient_before_every_cargo(monkeypatch):
    from ikabot.function import resourceTransportManager as manager

    session = Mock(username="Mine")
    island = {"id": "44", "x": 50, "y": 60, "cities": [
        {"type": "city", "state": "", "id": 9, "Id": 7, "name": "Town", "Name": "Other"}
    ]}
    origin = {"id": "1", "name": "Home", "availableResources": [100]*5}
    monkeypatch.setattr(manager, "getIdsOfCities", lambda *_a: (["1"], {"1": origin}))
    monkeypatch.setattr(manager, "requireOwnCity", lambda _s, cid, _n: str(cid))
    monkeypatch.setattr(manager, "get_island", lambda *_a: island)
    monkeypatch.setattr(shipments, "get_island", lambda *_a: island)
    config = {"mode":"consolidate","origin_cities":[1],"destination_city":9,
              "island":44,"recipient":7,"interval_hours":2,"resource_config":[50,None,None,None,None],
              "useFreighters":False,"send_mode":"keep","notify":"none"}
    prepared = manager.prepare_resourceTransportManager(session, **config)
    assert prepared["recipient"] == "7"
    assert restart_class_for("resourceTransportManager", config) == "manual"
    monkeypatch.setattr(manager, "getCity", lambda *_a: origin)
    monkeypatch.setattr(manager, "getIsland", lambda *_a: island)
    monkeypatch.setattr(manager, "setInfoSignal", lambda *_a: None)
    monkeypatch.setattr(manager, "getAvailableShips", lambda *_a: 1)
    monkeypatch.setattr(manager, "acquire_shipping_lock", lambda *_a, **_kw: True)
    release = Mock()
    monkeypatch.setattr(manager, "release_shipping_lock", release)
    cargo = []

    def execute(_s, routes, _fleet, *, verify_recipient):
        verify_recipient(0)
        cargo.append(routes[0][3:])
        island["cities"][0]["Id"] = 8
        verify_recipient(0)

    monkeypatch.setattr(manager, "executeRoutes", execute)
    with pytest.raises(ValueError, match="destination changed"):
        manager.do_it_unified.__wrapped__(session, **prepared)
    assert cargo == [(50,0,0,0,0)]
    release.assert_called_once()
    with pytest.raises(ValueError, match="destination changed"):
        manager.prepare_resourceTransportManager(session, **config)
    with pytest.raises(ValueError):
        manager.prepare_resourceTransportManager(session, **{**config,"mode":"distribute"})
