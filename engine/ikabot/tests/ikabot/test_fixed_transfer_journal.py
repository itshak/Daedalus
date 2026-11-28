"""Synthetic transport checkpoint tests; never contact a game server."""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ikabot.helpers.fixedTransferJournal import (
    FixedTransferJournal,
    FixedTransferUnsafe,
    canonical_transfer,
)


@pytest.fixture()
def journal(tmp_path):
    path = tmp_path / "transfer.sqlite3"
    tid = str(uuid4())
    account = SimpleNamespace(mundo="53", servidor="ru", username="captain")
    routes = [
        {"from": 101, "to": 102, "resources": [100, 0, 0, 0, 0]},
        {"from": 101, "to": 103, "resources": [0, 20, 0, 0, 0]},
    ]
    intent = canonical_transfer(routes, False)
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE desired_jobs(
                logical_id TEXT PRIMARY KEY, task TEXT, restart_class TEXT,
                desired_state TEXT);
            CREATE TABLE fixed_transfers(
                transfer_id TEXT PRIMARY KEY, account_id TEXT, identity TEXT,
                world TEXT, player TEXT, intent_json TEXT, dispatched_json TEXT,
                status TEXT, updated_at REAL);
            CREATE TABLE fixed_transfer_chunks(
                chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transfer_id TEXT, route_index INTEGER, cargo_json TEXT,
                status TEXT, updated_at REAL);
        """)
        conn.execute("INSERT INTO desired_jobs VALUES(?, 'sendResources', 'fixed_transfer', 'running')", (tid,))
        conn.execute("""INSERT INTO fixed_transfers VALUES(
            ?, 'a','identity','s53-ru','captain',?,?,'prepared',1)""",
            (tid, json.dumps(intent, sort_keys=True, separators=(",", ":")),
             json.dumps([[0] * 5 for _ in routes])))
    path.chmod(0o600)
    return path, tid, account, routes


def open_journal(values):
    path, tid, account, routes = values
    return FixedTransferJournal(account, tid, routes, db_path=path)


def test_committed_partial_cargo_restarts_with_exact_remainder(journal):
    record = open_journal(journal)
    assert record.remaining(0, journal[3][0]["resources"]) == [100, 0, 0, 0, 0]
    chunk = record.reserve(0, [40, 0, 0, 0, 0])
    record.confirmed(chunk, [40, 0, 0, 0, 0])
    restarted = open_journal(journal)
    assert restarted.remaining(0, journal[3][0]["resources"]) == [60, 0, 0, 0, 0]
    second = restarted.reserve(0, [60, 0, 0, 0, 0])
    restarted.confirmed(second, [60, 0, 0, 0, 0])
    assert open_journal(journal).remaining(0, journal[3][0]["resources"]) == [0] * 5


def test_crash_after_post_reservation_never_replays_unknown_cargo(journal):
    record = open_journal(journal)
    record.reserve(0, [55, 0, 0, 0, 0])
    with pytest.raises(FixedTransferUnsafe, match="Uncertain"):
        open_journal(journal).remaining(0, journal[3][0]["resources"])
    with pytest.raises(FixedTransferUnsafe, match="previous"):
        open_journal(journal).reserve(0, [55, 0, 0, 0, 0])


def test_explicit_server_rejection_does_not_reduce_target(journal):
    record = open_journal(journal)
    chunk = record.reserve(0, [60, 0, 0, 0, 0])
    record.rejected(chunk, [60, 0, 0, 0, 0])
    assert record.remaining(0, journal[3][0]["resources"]) == [100, 0, 0, 0, 0]


def test_forged_recipient_or_identity_fails_closed(journal):
    path, tid, account, routes = journal
    wrong_routes = [dict(route) for route in routes]
    wrong_routes[0]["to"] = 999
    with pytest.raises(FixedTransferUnsafe):
        FixedTransferJournal(account, tid, wrong_routes, db_path=path)
    with pytest.raises(FixedTransferUnsafe):
        FixedTransferJournal(
            SimpleNamespace(mundo="53", servidor="ru", username="someone_else"),
            tid, routes, db_path=path,
        )


def test_checkpointed_execute_routes_subtracts_prior_dispatch(journal, monkeypatch):
    from ikabot.helpers import planRoutes

    record = open_journal(journal)
    chunk = record.reserve(0, [40, 0, 0, 0, 0])
    record.confirmed(chunk, [40, 0, 0, 0, 0])
    routes = [
        ({"id": "101", "name": "Source"}, {"id": "102", "name": "Target"},
         "44", 100, 0, 0, 0, 0),
    ]
    # The underlying game GETs and ship availability are synthetic.
    monkeypatch.setattr(planRoutes, "getShipCapacity", lambda session: (500, 500))
    monkeypatch.setattr(planRoutes, "waitForArrival", lambda session, use: 1)
    monkeypatch.setattr(planRoutes, "getCity", lambda raw: {
        "id": raw, "name": raw,
        "availableResources": [1000] * 5,
        "freeSpaceForResources": [1000] * 5,
    })
    monkeypatch.setattr(planRoutes.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(planRoutes.random, "randint", lambda a, b: a)
    quantities = []

    def fake_send(session, origin, target, island, ships, send, use,
                  checkpoint=None, route_index=None):
        quantities.append(list(send))
        receipt = checkpoint.reserve(route_index, send)
        checkpoint.confirmed(receipt, send)

    monkeypatch.setattr(planRoutes, "sendGoods", fake_send)
    session = SimpleNamespace(
        get=lambda key: str(key).split("=")[-1].split("/")[-1],
        setStatus=lambda status: None,
    )
    planRoutes.executeRoutes(session, routes, False, checkpoint=record)
    assert quantities == [[60, 0, 0, 0, 0]]
