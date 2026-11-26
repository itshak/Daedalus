"""Offline warehouse-fill review and guard tests; never contact a game."""
import json
from unittest.mock import Mock

import pytest
from ikabot.function import fillCityWarehouse as worker
from ikabot.function import sendResources as upstream
from ikabot.helpers import planRoutes as routes

from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.fill_warehouse_review import draft_fill, validate_fill
from daedalus.recovery_reconcile import restart_class_for

REAL_WAIT_FOR_ARRIVAL = routes.waitForArrival
REAL_AVAILABLE_SHIPS = routes.getAvailableShips

DRAFT = {"destination_city": 103, "resource": "marble", "useFreighters": False}
NAMES = {101: "Athens", 102: "Sparta", 103: "Corinth"}
CITIES = {cid: {"id": str(cid), "name": NAMES[cid], "islandId": "8", "availableResources": [0, 0, stock, 0, 0],
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
    monkeypatch.setattr(routes, "waitForArrival", lambda *_: 2)
    monkeypatch.setattr(routes, "getShipCapacity", lambda *_: (100, 1000))
    monkeypatch.setattr(upstream, "getIdsOfCities", lambda *_: (
        list(map(str, NAMES)), {str(cid): {"name": name} for cid, name in NAMES.items()}))
    monkeypatch.setattr(upstream, "requireOwnCity", lambda _s, cid, _k: str(cid))
    monkeypatch.setattr(upstream, "getCityById", lambda _s, cid: CITIES[int(cid)])
    session.get.side_effect = lambda path: CITIES[int(path.split("=")[-1])]
    monkeypatch.setattr(routes, "getCity", lambda city: city)
    monkeypatch.setattr(upstream, "setInfoSignal", Mock())
    monkeypatch.setattr(worker, "setInfoSignal", Mock())
    monkeypatch.setattr(worker, "wait", Mock())
    monkeypatch.setattr(routes.time, "sleep", Mock())
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
    monkeypatch.setattr(routes, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[])
    sender.assert_not_called()


def test_execution_stops_if_accepted_cargo_not_visible(offline, monkeypatch):
    sender = Mock(side_effect=lambda *args, **kwargs: kwargs["before_send"]())
    monkeypatch.setattr(routes, "sendGoods", sender)
    with pytest.raises(RuntimeError, match="cargo unconfirmed"):
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

    monkeypatch.setattr(routes, "sendGoods", sender)
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

    monkeypatch.setattr(routes, "sendGoods", sender)
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
    offline._daedalus_fill_progress = [0, 0, 0]
    sender = Mock(side_effect=lambda *args, **kwargs: kwargs["before_send"]())
    monkeypatch.setattr(routes, "sendGoods", sender)
    with pytest.raises(RuntimeError, match="cargo unconfirmed"):
        worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[
            {"city_id": 101, "amount": 100}, {"city_id": 102, "amount": 30}])
    assert sender.call_count == 1


def test_progress_records_confirmed_cargo_and_last_stage(offline, monkeypatch):
    from ikabot.helpers.fillProgress import snapshot
    offline._daedalus_managed_fill = True
    offline._daedalus_fill_progress = [0, 0, 0]
    pending = [20]
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: pending[0])
    def sender(*args, **kwargs):
        kwargs["before_send"]()
        pending[0] += args[5][2]
    monkeypatch.setattr(routes, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[{"city_id": 101, "amount": 100}])
    assert snapshot(offline._daedalus_fill_progress) == {
        "stage": "finished", "submitted": 100, "verified": 100}


def test_progress_retains_failure_stage(offline, monkeypatch):
    from ikabot.helpers.fillProgress import snapshot
    offline._daedalus_managed_fill = True
    offline._daedalus_fill_progress = [0, 0, 0]
    monkeypatch.setattr(routes, "sendGoods", Mock(side_effect=RuntimeError("private")))
    with pytest.raises(RuntimeError):
        worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[{"city_id": 101, "amount": 100}])
    assert snapshot(offline._daedalus_fill_progress) == {
        "stage": "checking_source", "submitted": 0, "verified": 0}


def test_fill_json_load_matches_upstream_send_resources_cli(offline, monkeypatch):
    """Both entrypoints produce the same normalized city and cargo arguments."""
    from ikabot.function import sendResources as upstream
    from ikabot.helpers.ipc import _validate_task_config, parse_config_arg

    # Simulate the same JSON round-trip the authenticated IPC performs.
    draft = {**DRAFT, "resource": "marble", "reviewed_sources": [{"city_id": 101, "amount": 100}]}
    fill_config = _validate_task_config("fillCityWarehouse", worker.fill,
                                       parse_config_arg(json.dumps(draft)))
    cli_config = parse_config_arg(json.dumps({
        "routes": [{"from": 101, "to": 103, "resources": {"marble": 100}}],
        "useFreighters": False,
    }))
    names = {str(cid): {"name": name} for cid, name in NAMES.items()}
    monkeypatch.setattr(upstream, "getIdsOfCities", lambda *_: (list(names), names))
    monkeypatch.setattr(upstream, "requireOwnCity", lambda _s, cid, _n: str(cid))
    monkeypatch.setattr(upstream, "getCityById", lambda _s, cid: CITIES[int(cid)])
    monkeypatch.setattr(upstream, "setInfoSignal", Mock())
    execute = Mock(wraps=routes.executeRoutes)
    monkeypatch.setattr(upstream, "executeRoutes", execute)
    prepared = upstream.prepare_sendResources(offline, **cli_config)
    cli_sender = Mock()
    monkeypatch.setattr(routes, "sendGoods", cli_sender)
    upstream.do_it.__wrapped__(offline, **prepared)
    route = execute.call_args.args[1][0]
    cli_args = cli_sender.call_args.args
    pending = [20]
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: pending[0])
    def sender(*args, **kwargs):
        kwargs["before_send"]()
        pending[0] += args[5][2]
    capture = Mock(side_effect=sender)
    monkeypatch.setattr(routes, "sendGoods", capture)
    worker.fill.__wrapped__(offline, **fill_config)
    args = capture.call_args.args
    assert (args[1], args[2], args[3], args[5], args[6]) == (
        route[0]["id"], route[1]["id"], route[2], list(route[3:]), prepared["useFreighters"])
    assert args[4] == 1
    assert args[1:7] == cli_args[1:7]
    assert execute.call_count == 2
    assert "policy" not in execute.call_args_list[0].kwargs
    assert execute.call_args_list[1].kwargs["policy"] is not None


def test_warehouse_and_cli_share_real_sender_and_cookie_post_boundary(offline, monkeypatch):
    """A synthetic world verifies real JSON preparation, route loop, and HTTP adapter."""
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit

    from ikabot.config import actionRequest
    from ikabot.helpers.fillProgress import snapshot
    from ikabot.web.session import Session

    city_data = {cid: {**city, "availableResources": list(city["availableResources"])}
                 for cid, city in CITIES.items()}

    class World:
        def __init__(self):
            self.selected = 103
            self.pending = 20
            self.calls = []

        def get(self, url, **kwargs):
            query = parse_qs(urlsplit(url).query)
            if "cityId" in query:
                self.selected = int(query["cityId"][0])
            if "currentCityId" in query:
                self.selected = int(query["currentCityId"][0])
            page = ('<span id="avatarName">Mine</span> currentCityId: '
                    + str(self.selected) + ', actionRequest: "synthetic-token-1234"')
            return self.response(url, page)

        @staticmethod
        def response(url, page):
            return SimpleNamespace(url=url, status_code=200, text=page,
                                   content=page.encode(), history=[])

        def post(self, url, *, data, params, **kwargs):
            assert data == {}
            assert kwargs == {"allow_redirects": False, "verify": True, "timeout": 12}
            assert params["actionRequest"] == "synthetic-token-1234"
            self.calls.append(dict(params))
            if params["action"] == "header":
                assert int(params["currentCityId"]) == self.selected
                self.selected = int(params["cityId"])
                return self.response(url, '[["updateGlobalData",{}]]')
            assert params["function"] == "loadTransportersWithFreight"
            assert int(params["currentCityId"]) == self.selected == 101
            assert params["destinationCityId"] == "103"
            assert params["transporters"] == 1
            assert params["cargo_tradegood2"] == 100
            assert "normalTransportersMax" not in params
            self.pending += params["cargo_tradegood2"]
            city_data[101]["availableResources"][2] -= params["cargo_tradegood2"]
            return self.response(url, '[["provideFeedback",[{"type":10}]]]')

    world = World()
    session = Session.__new__(Session)
    session.host = "s1-en.ikariam.gameforge.com"
    session.urlBase = "https://" + session.host + "/index.php?"
    session.s = world
    session.username = "Mine"
    session._daedalus_cookies_only = True
    session._daedalus_managed_fill = True
    session._daedalus_fill_progress = [0, 0, 0]
    session.setStatus = Mock()

    def read_city(_session, cid):
        world.selected = int(cid)
        return city_data[int(cid)]

    def parse_city(page):
        import re
        return city_data[int(re.search(r"currentCityId: (\d+),", page).group(1))]

    def incoming(_session, target, *_args):
        world.selected = target  # the final guard changes selected-city context
        return world.pending

    monkeypatch.setattr(worker, "_city", read_city)
    monkeypatch.setattr(upstream, "getCityById", read_city)
    monkeypatch.setattr(worker, "incoming_amount", incoming)
    monkeypatch.setattr(routes, "getCity", parse_city)
    monkeypatch.setattr(routes, "getAvailableShips", lambda *_: 2)
    monkeypatch.setattr(Session, "_Session__checkCookie", Mock(side_effect=AssertionError("legacy relogin")))
    monkeypatch.setattr(Session, "_Session__token", Mock(side_effect=AssertionError("legacy token")))
    config = json.loads(json.dumps({**DRAFT, "reviewed_sources": [{"city_id": 101, "amount": 100}]}))
    worker.fill.__wrapped__(session, **config)
    assert len(world.calls) == 2
    assert world.calls[0]["function"] == "changeCurrentCity"
    assert world.calls[0]["currentCityId"] == "103"
    assert world.calls[1]["function"] == "loadTransportersWithFreight"
    assert world.pending == 120
    assert snapshot(session._daedalus_fill_progress) == {
        "stage": "finished", "submitted": 100, "verified": 100}
    assert actionRequest != "synthetic-token-1234"

    # Same authenticated transport for ordinary upstream JSON task; only the
    # warehouse policy is absent. Actual cargo form must be identical.
    warehouse_payload = world.calls[1]
    city_data[101]["availableResources"][2] = 100
    world.pending, world.selected = 20, 103
    world.calls.clear()
    session._daedalus_managed_fill = False
    prepared = upstream.prepare_sendResources(session, routes=[
        {"from": 101, "to": 103, "resources": {"marble": 100}}], useFreighters=False)
    upstream.do_it.__wrapped__(session, **prepared)
    assert len(world.calls) == 2
    assert world.calls[1] == warehouse_payload
    assert world.pending == 120


def test_depleted_source_does_not_prevent_other_reviewed_sources(offline, monkeypatch):
    pending = [20]
    monkeypatch.setattr(worker, "incoming_amount", lambda *_: pending[0])
    monkeypatch.setitem(CITIES, 101, {**CITIES[101], "availableResources": [0]*5})
    sent = []

    def sender(*args, **kwargs):
        kwargs["before_send"]()
        sent.append((args[1], args[5][2]))
        pending[0] += args[5][2]

    monkeypatch.setattr(routes, "sendGoods", sender)
    worker.fill.__wrapped__(offline, **DRAFT, reviewed_sources=[
        {"city_id": 101, "amount": 100}, {"city_id": 102, "amount": 100}])
    assert sent == [("102", 100)]


def test_consolidated_multiple_loads_use_upstream_ajax_fleet_wait(offline, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit

    from ikabot.helpers.fillProgress import snapshot
    from ikabot.web.session import Session

    # Restore the real shared upstream wait implementation (the fixture stubs it).
    # Import a reference captured before the fixture applies monkeypatches.
    monkeypatch.setattr(routes, "waitForArrival", REAL_WAIT_FOR_ARRIVAL)
    monkeypatch.setattr(routes, "get_random_wait_time", lambda: 0)
    monkeypatch.setattr(routes, "getAvailableShips", REAL_AVAILABLE_SHIPS)
    monkeypatch.setattr(routes, "getShipCapacity", lambda *_: (100, 1000))
    city_data = {
        cid: {**city, "availableResources": list(city["availableResources"]),
              "freeSpaceForResources": list(city["freeSpaceForResources"])}
        for cid, city in CITIES.items()
    }
    city_data[101]["availableResources"][2] = 300
    city_data[103]["freeSpaceForResources"][2] = 500

    class World:
        def __init__(self):
            self.selected = 103
            self.pending = 20
            self.free = 1
            self.cargo = []
            self.advisor_calls = 0
            self.waits = []

        @staticmethod
        def response(url, page):
            return SimpleNamespace(url=url, status_code=200, text=page,
                                   content=page.encode(), history=[])

        def get(self, url, **kwargs):
            query = parse_qs(urlsplit(url).query)
            if "cityId" in query:
                self.selected = int(query["cityId"][0])
            if "currentCityId" in query:
                self.selected = int(query["currentCityId"][0])
            page = ('<span id="avatarName">Mine</span> currentCityId: '
                    + str(self.selected) + ', actionRequest: "synthetic-token-1234" '
                    + 'id="GlobalMenu_freeTransporters">' + str(self.free) + '<')
            return self.response(url, page)

        def post(self, url, *, data, params, **kwargs):
            assert data == {}
            assert kwargs == {"allow_redirects": False, "verify": True, "timeout": 12}
            if parse_qs(urlsplit(url).query).get("view") == ["militaryAdvisor"]:
                self.advisor_calls += 1
                assert self.free == 0
                query = parse_qs(urlsplit(url).query)
                assert query == {
                    "view": ["militaryAdvisor"], "oldView": ["city"],
                    "oldBackgroundView": ["city"], "backgroundView": ["city"],
                    "currentCityId": [str(self.selected)], "actionRequest": ["synthetic-token-1234"],
                    "ajax": ["1"],
                }
                assert params == {}
                return self.response(url, json.dumps([
                    ["updateGlobalData", {"time": 1000}],
                    ["changeView", [None, None, {"viewScriptParams": {
                        "militaryAndFleetMovements": [
                            {"isOwnArmyOrFleet": True, "eventTime": 1120},
                            {"isOwnArmyOrFleet": False, "eventTime": 1010},
                        ]
                    }}]],
                ]))
            assert params["actionRequest"] == "synthetic-token-1234"
            if params["action"] == "header":
                assert int(params["currentCityId"]) == self.selected
                self.selected = int(params["cityId"])
                return self.response(url, '[["updateGlobalData",{}]]')
            assert self.free == 1
            assert params["function"] == "loadTransportersWithFreight"
            assert int(params["currentCityId"]) == self.selected == 101
            assert params["transporters"] == 1
            assert params["cargo_tradegood2"] == 100
            self.free = 0
            self.cargo.append(params["cargo_tradegood2"])
            self.pending += params["cargo_tradegood2"]
            city_data[101]["availableResources"][2] -= params["cargo_tradegood2"]
            return self.response(url, '[["provideFeedback",[{"type":10}]]]')

        def wait(self, seconds):
            assert self.free == 0
            self.waits.append(seconds)
            self.free = 1

    world = World()
    session = Session.__new__(Session)
    session.host = "s1-en.ikariam.gameforge.com"
    session.urlBase = "https://" + session.host + "/index.php?"
    session.s = world
    session.username = "Mine"
    session._daedalus_cookies_only = True
    session._daedalus_managed_fill = True
    session._daedalus_fill_progress = [0, 0, 0]
    session.setStatus = Mock()

    def read_city(_session, cid):
        world.selected = int(cid)
        return city_data[int(cid)]

    def parse_city(page):
        import re
        return city_data[int(re.search(r"currentCityId: (\d+),", page).group(1))]

    def incoming(_session, target, *_args):
        world.selected = target
        return world.pending

    monkeypatch.setattr(worker, "_city", read_city)
    monkeypatch.setattr(upstream, "getCityById", read_city)
    monkeypatch.setattr(worker, "incoming_amount", incoming)
    monkeypatch.setattr(routes, "getCity", parse_city)
    monkeypatch.setattr(routes, "wait", world.wait)
    monkeypatch.setattr(Session, "_Session__checkCookie", Mock(side_effect=AssertionError("legacy relogin")))
    monkeypatch.setattr(Session, "_Session__token", Mock(side_effect=AssertionError("legacy token")))
    worker.fill.__wrapped__(session, **DRAFT, reviewed_sources=[{"city_id": 101, "amount": 300}])
    assert world.cargo == [100, 100, 100]
    assert world.advisor_calls == 2
    assert world.waits == [120, 120]
    assert snapshot(session._daedalus_fill_progress) == {
        "stage": "finished", "submitted": 300, "verified": 300}
