"""End-to-end synthetic military read contracts and Mac dashboard.

No live account, login, Gameforge HTTP or task mutation is used.
"""
from __future__ import annotations

import os

import httpx
import pytest
from fastapi.testclient import TestClient
from test_engine_ipc import ALPHA, fake_worker

from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.client import APIConnectionError, DaedalusClient
from daedalus.engine_ipc import EngineIPCUnavailable


def response(message, *, world="s301-en", city_id=42):
    action = message["action"]
    if action == "list_sessions":
        return {"status": "ok", "sessions": [{"world": "s301-en", "player": "ExamplePlayer"}]}
    if action == "list_cities_existing":
        return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                "cities": [{"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}]}
    if action == "military_overview_existing":
        return {"status": "ok", "world": world, "username": "ExamplePlayer",
                "observed_at": 1795160000, "cities": [
                    {"city_id": city_id, "city_name": "Athens",
                     "troops": [{"unit": "Swordsman", "amount": 17}],
                     "fleet": [{"unit": "Ballista Ship", "amount": 3}]}
                ]}
    if action == "ship_movements_existing":
        return {"status": "ok", "world": world, "username": "ExamplePlayer",
                "observed_at": 1795160000, "movements": [
                    {"origin": "Athens", "destination": "Sparta",
                     "origin_player": "ExamplePlayer", "destination_player": "Other",
                     "mission": "Transport", "seconds_remaining": 600,
                     "troops": 0, "ships": 8, "hostile": False, "returning": False},
                ]}
    raise AssertionError(f"Unexpected military test action: {action}")


def test_verified_military_and_movements_are_read_only(tmp_path):
    with fake_worker(tmp_path, responder=response) as (ipc, seen, _):
        army = ipc.military_overview(ALPHA)
        movements = ipc.ship_movements(ALPHA)
    assert army["cities"][0]["troops"][0]["amount"] == 17
    assert army["cities"][0]["fleet"][0]["amount"] == 3
    assert movements["movements"][0]["seconds_remaining"] == 600
    assert {item["action"] for item in seen} <= {
        "list_sessions", "list_cities_existing",
        "military_overview_existing", "ship_movements_existing",
    }
    assert all("email" not in entry and "cookie" not in entry for entry in seen)


@pytest.mark.parametrize("action", ["military_overview", "ship_movements"])
def test_no_existing_account_session_fails_before_military_read(tmp_path, action):
    wrong = Account("other", "s999-en", "OtherPlayer", "Other", True)
    with (
        fake_worker(tmp_path, responder=response) as (ipc, seen, _),
        pytest.raises(EngineIPCUnavailable, match="No unique"),
    ):
        getattr(ipc, action)(wrong)
    assert [entry["action"] for entry in seen] == ["list_sessions"]


@pytest.mark.parametrize("action", ["military_overview", "ship_movements"])
def test_military_wrong_world_rejected(tmp_path, action):
    def mismatched(request):
        return response(request, world="s302-en")
    with (
        fake_worker(tmp_path, responder=mismatched) as (ipc, _, _),
        pytest.raises(EngineIPCUnavailable, match="another account"),
    ):
        getattr(ipc, action)(ALPHA)


def test_unowned_military_city_rejected_without_display(tmp_path):
    def unowned(request):
        return response(request, city_id=999)
    with (
        fake_worker(tmp_path, responder=unowned) as (ipc, _, _),
        pytest.raises(EngineIPCUnavailable, match="not verified"),
    ):
        ipc.military_overview(ALPHA)


def test_malformed_movement_cannot_be_used_as_gui_data(tmp_path):
    def malformed(request):
        obj = response(request)
        if request["action"] == "ship_movements_existing":
            obj["movements"][0]["ships"] = "8"
        return obj
    with (
        fake_worker(tmp_path, responder=malformed) as (ipc, _, _),
        pytest.raises(EngineIPCUnavailable, match="Invalid movement count"),
    ):
        ipc.ship_movements(ALPHA)


def test_api_military_requires_auth_and_returns_sanitized_scoped_rows(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid="alpha"\nworld="s301-en"\n'
                      'player="ExamplePlayer"\n', encoding="utf-8")
    class IPCStub:
        def military_overview(self, account):
            assert account.id == "alpha"
            return {"cities": [{"city_id": 42, "city_name": "Athens",
                                 "troops": [], "fleet": []}], "observed_at": 1795160000}
        def ship_movements(self, account):
            assert account.id == "alpha"
            return {"movements": [], "observed_at": 1795160000}
    client = TestClient(create_app(
        accounts_path=config, api_token="x"*48, ipc_client=IPCStub(),
    ))
    for endpoint in ("military", "ship-movements"):
        path = "/api/v1/accounts/alpha/" + endpoint
        assert client.get(path).status_code == 401
        assert client.get("/api/v1/accounts/unknown/" + endpoint,
                          headers={"Authorization": "Bearer " + "x"*48}).status_code == 404
        reply = client.get(path, headers={"Authorization": "Bearer " + "x"*48})
        assert reply.status_code == 200
        assert reply.json()["account_id"] == "alpha"
        assert "cookie" not in reply.text


def test_api_military_unavailable_without_session(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid="alpha"\nworld="s301-en"\n'
                      'player="ExamplePlayer"\n', encoding="utf-8")
    client = TestClient(create_app(accounts_path=config, api_token="x"*48))
    headers = {"Authorization": "Bearer " + "x"*48}
    for endpoint in ("military", "ship-movements"):
        assert client.get("/api/v1/accounts/alpha/" + endpoint,
                          headers=headers).status_code == 503


def test_http_client_rejects_wrong_account_and_malformed_responses():
    def handler(request):
        if request.url.path.endswith("/military"):
            return httpx.Response(200, json={
                "account_id": "beta", "cities": [], "observed_at": 1795160000,
            })
        return httpx.Response(200, json={
            "account_id": "alpha", "movements": {}, "observed_at": 1795160000,
        })
    client = DaedalusClient(
        "http://127.0.0.1:8765", "x"*48, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIConnectionError):
        client.military_overview("alpha")
    with pytest.raises(APIConnectionError):
        client.ship_movements("alpha")
    with pytest.raises(ValueError):
        client.military_overview("../alpha")
    client.close()


def test_native_military_page_all_accounts_is_read_only_and_context_isolated():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    pytest.importorskip("qfluentwidgets")
    from PySide6.QtWidgets import QApplication

    from daedalus.desktop.military_page import MilitaryPage

    app = QApplication.instance() or QApplication([])
    page = MilitaryPage()
    try:
        page.set_accounts([
            {"id": "alpha", "label": "Imported IkaBot account 01", "player": "Athena", "world": "s301-en", "enabled": True},
            {"id": "beta", "label": "Imported IkaBot account 02", "player": "Boreas", "world": "s302-en", "enabled": True},
        ])
        assert page.account_combo.itemText(1) == "Athena · s301-en"
        assert page.account_combo.itemText(2) == "Boreas · s302-en"
        scopes = []
        page.refresh_requested.connect(lambda ids, kind: scopes.append((ids, kind)))
        assert page.selected_account_ids() == ["alpha", "beta"]
        page.refresh()
        assert scopes == [(["alpha", "beta"], "military_overview")]
        assert page.tables[0].rowCount() == 0
        page.set_result("alpha", "military_overview", {
            "account_id": "alpha", "observed_at": 1795160000,
            "cities": [{"city_id": 42, "city_name": "Athens",
                        "troops": [{"unit": "Swordsman", "amount": 17}], "fleet": []}],
        })
        assert page.tables[0].rowCount() == 1
        assert page.tables[0].item(0, 0).text() == "Athena"
        assert "1/2" in page.status.text()
        assert "Boreas" not in page.tables[0].item(0, 0).text()
        page.set_unavailable("beta", "military_overview")
        assert "unavailable" in page.status.text()
        page.tabs.widget("fleet").click()
        assert page.stack.currentIndex() == 1
        page.tabs.widget("movements").click()
        assert page.stack.currentIndex() == 2
        assert page.tabs.currentRouteKey() == "movements"
        page.refresh()
        assert scopes[-1] == (["alpha", "beta"], "military_movements")
        assert page.tables[2].rowCount() == 0
        page.set_result("alpha", "military_movements", {
            "account_id": "beta", "movements": [], "observed_at": 1795160000,
        })
        assert page.tables[2].rowCount() == 0  # wrong account ignored
        page.set_accounts([
            {"id": "gamma", "label": "New Server", "world": "s303-en", "enabled": True},
        ])
        assert page.selected_account_ids() == ["gamma"]
        assert page.tables[2].rowCount() == 0
        assert "0/1" not in page.status.text()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
