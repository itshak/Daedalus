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
