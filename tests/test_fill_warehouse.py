"""Offline warehouse-fill review and guard tests; never contact a game."""
import json
from unittest.mock import Mock

import pytest
from ikabot.function import fillCityWarehouse as worker

from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.fill_warehouse_review import draft_fill, validate_fill
from daedalus.recovery_reconcile import restart_class_for

DRAFT = {"destination_city": 103, "resource": "marble", "useFreighters": False}
NAMES = {101: "Athens", 102: "Sparta", 103: "Corinth"}
CITIES = {cid: {"id": str(cid), "islandId": "8", "availableResources": [0, 0, stock, 0, 0],
                "freeSpaceForResources": [0, 0, space, 0, 0]}
          for cid, stock, space in ((101, 100, 400), (102, 200, 400), (103, 350, 150))}


@pytest.fixture
def offline(monkeypatch):
    session = Mock(username="Mine")
    monkeypatch.setattr(worker, "_owned", lambda _s: NAMES)
    monkeypatch.setattr(worker, "_city", lambda _s, cid: CITIES[cid])
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: 20)
    monkeypatch.setattr(worker.pedirInfo, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(worker, "getTotalShips", lambda _s: 3)
    monkeypatch.setattr(worker, "getAvailableShips", lambda _s: 2)
    monkeypatch.setattr(worker, "requireOwnCity", lambda _s, cid, _k: str(cid))
    monkeypatch.setattr(worker, "waitForArrival", lambda *_: 2)
    monkeypatch.setattr(worker, "setInfoSignal", Mock())
    monkeypatch.setattr(worker.time, "sleep", Mock())
    return session


def test_all_sources_share_one_capacity_budget(offline):
    o = worker.preview_fill(offline, DRAFT)
    assert o["budget"] == 130 and o["amount"] == 130
    assert [r["amount"] for r in o["sources"]] == [100, 30]
    assert validate_fill(draft_fill(DRAFT), o) == o
    with pytest.raises(ValueError):
        validate_fill(DRAFT, {**o, "amount": 300})
    with pytest.raises(ValueError):
        validate_fill(DRAFT, {**o, "sources": [o["sources"][0], {**o["sources"][1], "amount": 50}]})
    offline.post.assert_not_called()


def test_existing_cargo_can_consume_entire_capacity(offline, monkeypatch):
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: 160)
    o = worker.preview_fill(offline, DRAFT)
    assert o["amount"] == o["budget"] == 0
    assert all(r["amount"] == 0 for r in o["sources"])
    sender = Mock()
    monkeypatch.setattr(worker, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[])
    sender.assert_not_called()


def test_execution_stops_if_accepted_cargo_not_visible(offline, monkeypatch):
    sender = Mock(side_effect=lambda *args, **kwargs: kwargs["before_send"]())
    monkeypatch.setattr(worker, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[
        {"city_id": 101, "amount": 100}, {"city_id": 102, "amount": 30}])
    assert sender.call_count == 1
    assert sender.call_args.args[5] == [0, 0, 100, 0, 0]
    assert "unconfirmed" in offline.setStatus.call_args.args[0]
    assert restart_class_for("fillCityWarehouse", DRAFT) == "manual"


def test_execution_rechecks_capacity_before_each_load(offline, monkeypatch):
    pending = [20]
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: pending[0])
    sent = []

    def sender(*args, **kwargs):
        kwargs["before_send"]()
        sent.append(args[5][2])
        pending[0] += args[5][2]

    monkeypatch.setattr(worker, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[
        {"city_id": 101, "amount": 100}, {"city_id": 102, "amount": 100}])
    assert sent == [100, 30]
    assert pending[0] == 150


def test_guard_rejects_storage_change_before_submission(offline, monkeypatch):
    pending = [20]
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: pending[0])
    sent = []

    def sender(*args, **kwargs):
        pending[0] = 150
        kwargs["before_send"]()
        sent.append(args[5][2])

    monkeypatch.setattr(worker, "sendGoods", sender)
    with pytest.raises(ValueError, match="Storage or ownership changed"):
        worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[{"city_id": 101, "amount": 100}])
    assert sent == []


def test_advisor_accounts_for_incoming_returning_and_unknown_cargo():
    session = Mock(username="Mine")
    movement = {"origin": {"name": "Athens", "avatarName": "Mine"},
                "target": {"name": "Corinth", "avatarName": "Mine"},
                "event": {"isFleetReturning": False},
                "resources": [{"cssClass": "resource marble", "amount": "12,345"}]}
    returned = {**movement, "origin": movement["target"], "target": movement["origin"],
                "event": {"isFleetReturning": True}}
    other = {**movement, "target": {"name": "Sparta", "avatarName": None}, "resources": None}

    def respond(rows):
        session.post.return_value = json.dumps([None, [None, [None, None,
            {"viewScriptParams": {"militaryAndFleetMovements": rows}}]]])

    respond([movement, returned, other])
    assert worker.incoming_amount(session, 103, "Corinth", 2) == 24690
    respond([{**movement, "target": {"name": "Corinth", "avatarName": None}}])
    assert worker.incoming_amount(session, 103, "Corinth", 2) == 12345
    respond([{**movement, "resources": None}])
    with pytest.raises(ValueError, match="Incoming cargo unavailable"):
        worker.incoming_amount(session, 103, "Corinth", 2)


def test_ipc_rejects_missing_or_foreign_source(offline, monkeypatch):
    ipc = ControlledIPCClient()
    account = Account("alpha", "s1-en", "Mine", "Mine", True)
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": i} for i in NAMES])
    o = worker.preview_fill(offline, DRAFT)
    exchange = Mock(return_value={"world": "s1-en", "username": "Mine", "result": o})
    monkeypatch.setattr(ipc, "_exchange", exchange)
    assert ipc.fill_preview(account, DRAFT) == o
    exchange.return_value = {"world": "s1-en", "username": "Other", "result": o}
    with pytest.raises(EngineIPCUnavailable):
        ipc.fill_preview(account, DRAFT)
    exchange.return_value = {"world": "s1-en", "username": "Mine", "result": {**o,
        "sources": o["sources"][:1], "amount": 100}}
    with pytest.raises(EngineIPCUnavailable):
        ipc.fill_preview(account, DRAFT)

def test_overfull_destination_is_safe_noop(offline, monkeypatch):
    original = CITIES[103]
    monkeypatch.setitem(CITIES, 103, {**original, "freeSpaceForResources": [0,0,-20,0,0]})
    result = worker.preview_fill(offline, DRAFT)
    assert result["free_space"] == result["budget"] == result["amount"] == 0
    assert validate_fill(DRAFT, result) == result


def test_incoming_failure_never_exposes_raw_exception(offline, monkeypatch):
    def unreadable(*_args):
        raise ValueError("synthetic private payload")
    monkeypatch.setattr(worker, "incoming_amount", unreadable)
    with pytest.raises(worker.FillPreviewError, match="^fill_incoming_unavailable$"):
        worker.preview_fill(offline, DRAFT)


def test_safe_preview_error_contract():
    from daedalus.engine_ipc import FillPreviewUnavailable
    from daedalus.fill_warehouse_review import FILL_PREVIEW_MESSAGES

    assert str(FillPreviewUnavailable("fill_incoming_unavailable")) == FILL_PREVIEW_MESSAGES["fill_incoming_unavailable"]
    with pytest.raises(EngineIPCUnavailable, match="Invalid warehouse preview failure"):
        FillPreviewUnavailable("synthetic private payload")


def test_fill_preview_actual_worker_handler_to_controller_api(offline, monkeypatch, tmp_path):
    """Exercise the production routing, socket and API, with only game reads mocked."""
    from fastapi.testclient import TestClient
    from ikabot.helpers.ipc import IPCServer
    from test_engine_ipc import fake_worker

    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.api import create_app
    from daedalus.daily_distribution_review import validate_ticket
    from daedalus.fill_warehouse_review import FILL_PREVIEW_MESSAGES
    from daedalus.recovery_runtime import RoutedAccountIPC
    from daedalus.task_control import TaskController

    offline.logged = True
    offline.mundo, offline.servidor, offline.mail = "1", "en", ""
    cities = {str(cid): {"name": name, "coords": "[1:2]", "tradegood": "2"}
              for cid, name in NAMES.items()}
    monkeypatch.setattr(worker.pedirInfo, "getIdsOfCities", lambda _s: (list(cities), cities))
    server = IPCServer(default_session=offline)
    config = tmp_path / "synthetic.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Mine"\n')
    accounts = load_accounts(config)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    with fake_worker(tmp_path, responder=server.handle_request) as (_, requests, descriptor):
        router = RoutedAccountIPC(ControlledIPCClient(tmp_path / "no-fallback.json"))
        router.use("alpha", descriptor)
        controller = TaskController(accounts, owner, router, ledger_path=tmp_path / "ledger.sqlite")
        try:
            client = TestClient(create_app(accounts_path=config, api_token="x"*48,
                                           session_coordinator=owner, ipc_client=router,
                                           task_controller=controller))
            path = "/api/v1/accounts/alpha/reward-distribution-plan"
            headers = {"Authorization": "Bearer " + "x"*48}
            payload = {"task": "fillCityWarehouse", "draft": DRAFT}
            result = client.post(path, headers=headers, json=payload)
            assert result.status_code == 200, result.text
            assert validate_ticket(result.json(), "alpha", "fillCityWarehouse", DRAFT)["observation"]["amount"] == 130
            assert [r["action"] for r in requests] == [
                "task_preflight_existing", "list_sessions", "list_cities_existing", "preview_fill_existing",
            ]

            def bad_source(_s, cid):
                if cid == 102:
                    raise ValueError("synthetic private detail")
                return CITIES[cid]
            monkeypatch.setattr(worker, "_city", bad_source)
            failed = client.post(path, headers=headers, json=payload)
            assert failed.status_code == 503
            assert failed.json() == {"detail": FILL_PREVIEW_MESSAGES["fill_source_unavailable"]}
            offline.logged = False
            failed = client.post(path, headers=headers, json=payload)
            assert failed.status_code == 503
            assert failed.json() == {"detail": FILL_PREVIEW_MESSAGES["fill_session_unavailable"]}
            assert all(r["action"] != "start_task_existing" for r in requests)
        finally:
            controller.close()


def test_cookie_only_advisor_uses_protected_get_and_never_legacy_post():
    session = Mock(username="Mine")
    session._daedalus_cookies_only = True
    session.post.side_effect = AssertionError("legacy POST is not a cookie-only read")
    movement = {"origin": {"name": "Athens", "avatarName": "Mine"},
                "target": {"name": "Corinth", "avatarName": "Mine"},
                "event": {"isFleetReturning": False},
                "resources": [{"cssClass": "resource_icon wood", "amount": "12,345"}]}
    data = [None, [None, [None, None, {"viewScriptParams": {"militaryAndFleetMovements": [movement]}}]]]
    session.get.return_value = "ajax.Responder, " + json.dumps(data) + ");"
    assert worker.incoming_amount(session, 103, "Corinth", 0) == 12345
    session.get.assert_called_once_with("view=militaryAdvisor&currentCityId=103")
    session.post.assert_not_called()
    session.get.return_value = "missing advisor"
    with pytest.raises(ValueError, match="Advisor response unavailable"):
        worker.incoming_amount(session, 103, "Corinth", 0)
    session.post.assert_not_called()


def test_legacy_session_exit_is_stage_specific_and_fails_closed(offline, monkeypatch):
    def rotated(*_args):
        raise SystemExit(1)
    monkeypatch.setattr(worker, "incoming_amount", rotated)
    with pytest.raises(worker.FillPreviewError, match="^fill_incoming_unavailable$"):
        worker.preview_fill(offline, DRAFT)


def test_managed_fill_reports_ambiguous_observation_as_failure(offline, monkeypatch):
    offline._daedalus_managed_fill = True
    sender = Mock(side_effect=lambda *args, **kwargs: kwargs["before_send"]())
    monkeypatch.setattr(worker, "sendGoods", sender)
    with pytest.raises(RuntimeError, match="cargo unconfirmed"):
        worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[
            {"city_id": 101, "amount": 100}, {"city_id": 102, "amount": 30}])
    assert sender.call_count == 1
