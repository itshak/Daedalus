"""Synthetic independent recurring-policy review; no game or provider network."""
from unittest.mock import Mock

import pytest

from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.native_policy_review import observe_policy, policy_draft, policy_summary
from daedalus.recurring_review import validate_recurring
from daedalus.reviewed_batch import BATCH_REVIEW_TASKS

ACCOUNT = Account("alpha", "s1-en", "Mine", "Mine", True)
DRAFT = {"limits": [0, -1, 100, -1, -1], "sourceCityIds": [101],
         "destinationCityId": 102, "intervalInHours": 2, "shipType": 1}
ROWS = [{"id": i, "name": name, "coords": "10:20", "stock": [1000]*5, "space": [2000]*5}
        for i, name in ((101, "Athens"), (102, "Sparta"))]
OBS = {"cities": ROWS, "fleets": {"trade": {"capacity": 100, "free": 2, "total": 3}}, "external": None}


def test_consolidation_scope_and_stock():
    d = policy_draft("consolidateResources", {**DRAFT, "sourceCityIds": ["101"]})
    assert d == DRAFT
    ipc = Mock()
    ipc.recurring_preview.return_value = OBS
    assert observe_policy(ipc, ACCOUNT, "consolidateResources", d) == OBS
    assert "Athens → Sparta" in policy_summary("consolidateResources", d, OBS)
    for bad in ({**OBS, "cities": [ROWS[0], {**ROWS[1], "id": 999}]},
                {**OBS, "fleets": {"freighter": OBS["fleets"]["trade"]}},
                {**OBS, "cities": [{**ROWS[0], "stock": [True]*5}, ROWS[1]]}):
        with pytest.raises(ValueError):
            validate_recurring("consolidateResources", d, bad)
    assert "consolidateResources" in BATCH_REVIEW_TASKS


def test_engine_identity_and_foreign_origin_rejected(monkeypatch):
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id": 101}, {"id": 102}])
    exchange = Mock(return_value={"world": "s1-en", "username": "Other", "result": OBS})
    monkeypatch.setattr(ipc, "_exchange", exchange)
    with pytest.raises(EngineIPCUnavailable):
        ipc.recurring_preview(ACCOUNT, "consolidateResources", DRAFT)
    exchange.reset_mock()
    with pytest.raises(ValueError):
        ipc.recurring_preview(ACCOUNT, "consolidateResources", {**DRAFT, "sourceCityIds": [999]})
    exchange.assert_not_called()


def test_worker_previews_existing_engine_inventory(monkeypatch):
    from ikabot.function import consolidateResources
    from ikabot.helpers import nativePolicyReview as worker
    from ikabot.helpers import naval

    session = Mock()
    cities = {str(r["id"]): {"name": r["name"], "coords": "[10:20]"} for r in ROWS}
    monkeypatch.setattr(worker.pedirInfo, "getIdsOfCities", lambda _s: (list(cities), cities))
    monkeypatch.setattr(consolidateResources, "requireOwnCity", lambda _s, c, _k: str(c))
    monkeypatch.setattr(worker, "getCityById", lambda _s, c: {"id": c, "availableResources": [1000]*5, "freeSpaceForResources": [2000]*5})
    monkeypatch.setattr(worker.pedirInfo, "getShipCapacity", lambda _s: (100, 1000))
    monkeypatch.setattr(naval, "getAvailableShips", lambda _s: 2)
    monkeypatch.setattr(naval, "getTotalShips", lambda _s: 3)
    assert worker.preview_recurring(session, "consolidateResources", DRAFT) == OBS
    session.post.assert_not_called()


def test_external_recipient_scope_and_scan_drafts():
    d = policy_draft("resourceTransportManager", {"mode": "consolidate", "origin_cities": [101],
        "destination_city": 999, "island": 20, "recipient": 30, "interval_hours": 0,
        "resource_config": [5, None, None, None, None], "useFreighters": False, "notify": "none", "send_mode": "send"})
    o = {**OBS, "cities": [ROWS[0]], "external": {"id": 999, "island": 20, "recipient": 30, "name": "Town", "owner": "Other"}}
    assert validate_recurring("resourceTransportManager", d, o) == o
    with pytest.raises(ValueError):
        validate_recurring("resourceTransportManager", d, {**o, "external": {**o["external"], "recipient": 31}})
    for task, draft in [
        ("searchForIslandSpaces", {"time": 5, "fights": False, "islandList": ["10:20"]}),
        ("dumpWorld", {"waiting_time": 2, "shallow": False, "non_empty_islands": True}),
        ("donationBot", {"cities_dict": {"101": {"donation_type": "both", "percentage": 10}}, "waiting_time": 60, "donate_method": 2}),
    ]:
        assert policy_draft(task, draft)
        assert task in BATCH_REVIEW_TASKS
    with pytest.raises(ValueError):
        policy_draft("searchForIslandSpaces", {"time": 5, "fights": False, "islandList": ["123"]})


def test_piracy_review_requires_existing_human_stop():
    d = policy_draft("autoPirate", {"pirateCount": 1, "pirateSchedule": False, "pirateMissionChoice": 1,
        "pirateMissionDayChoice": None, "pirateMissionNightChoice": None, "dayStart": None, "dayEnd": None,
        "nightStart": None, "nightEnd": None, "autoConvert": "n", "convertPerMission": 0,
        "maxRandomWaitingTime": 0, "piracyCities": [{"id": 101}]})
    r = {"city_id": 101, "city_name": "Athens", "fortress_level": 1, "missions": [{"number": 1, "duration_seconds": 150}]}
    ipc = Mock()
    ipc.pirate_fortresses.return_value = {"fortresses": [r]}
    assert observe_policy(ipc, ACCOUNT, "autoPirate", d) == {"fortress": r, "human_challenge": "stop"}
    with pytest.raises(ValueError):
        policy_draft("autoPirate", {**d, "manual_challenge": False})
