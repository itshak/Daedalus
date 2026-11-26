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
