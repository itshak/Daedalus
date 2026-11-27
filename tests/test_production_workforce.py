import copy

import pytest
from ikabot.function.productionWorkforce import (
    donor_restore_target,
    feasible_after_release,
    plan_city_production,
    read_city_production,
)


def observed(free=200):
    return {"city_id": 1, "island_id": 2, "luxury": "crystal", "free_citizens": free,
            "sites": {"resource": {"available": True, "maximum": 700, "extra": 100, "current": 700},
                      "tradegood": {"available": True, "maximum": 750, "extra": 150, "current": 400}}}


def draft(**changes):
    return {"resource": "crystal", "mode": "maximum", "amount": None, "overcharge": True,
            "available_only": False, "allow_fallback": False, **changes}


def test_priority_minimal_release_and_available_only():
    source = observed()
    original = copy.deepcopy(source)
    plan = plan_city_production(source, draft())
    assert (plan["desired"], plan["target_after"], plan["donor_release"], plan["donor_after"]) == (900, 900, 300, 400)
    assert source == original
    plan = plan_city_production(source, draft(available_only=True))
    assert (plan["target_after"], plan["donor_release"], plan["shortfall"]) == (600, 0, 300)


def test_sufficient_population_and_donor_exhaustion():
    assert plan_city_production(observed(600), draft())["donor_release"] == 0
    source = observed(20)
    source["sites"]["resource"]["current"] = 100
    plan = plan_city_production(source, draft())
    assert (plan["donor_release"], plan["target_after"], plan["shortfall"]) == (100, 520, 380)


def test_wood_priority_and_lower_exact():
    source = observed(0)
    source["sites"]["resource"]["current"] = 100
    plan = plan_city_production(source, draft(resource="wood"))
    assert (plan["target_kind"], plan["donor_kind"], plan["target_after"], plan["donor_release"]) == ("resource", "tradegood", 500, 400)
    plan = plan_city_production(source, draft(mode="exact", amount=300, overcharge=False))
    assert (plan["target_after"], plan["donor_release"]) == (300, 0)


def test_fallback_requires_explicit_approval_and_known_assignments():
    source = observed(None)
    with pytest.raises(ValueError, match="unknown"):
        plan_city_production(source, draft())
    plan = plan_city_production(source, draft(allow_fallback=True))
    assert plan["fallback"] and plan["donor_release"] == 700
    assert plan["target_after"] is None and plan["donor_after"] is None
    fresh = observed(900)
    fresh["sites"]["resource"]["current"] = 0
    assert feasible_after_release(plan, fresh) == 900
    fresh["sites"]["tradegood"]["current"] = 900
    fresh["free_citizens"] = 400
    assert donor_restore_target(plan, fresh, 900) == 400
    source["sites"]["resource"]["current"] = None
    with pytest.raises(ValueError, match="known"):
        plan_city_production(source, draft(allow_fallback=True))


def test_fresh_observation_never_expands_review_or_restores_above_original():
    plan = plan_city_production(observed(), draft())
    fresh = observed(900)
    fresh["sites"]["resource"]["current"] = 400
    assert feasible_after_release(plan, fresh) == 900
    fresh["sites"]["tradegood"]["current"] = 900
    assert donor_restore_target(plan, fresh, 900) == 700
    fresh["sites"]["resource"]["current"] = 401
    with pytest.raises(ValueError, match="verify"):
        donor_restore_target(plan, fresh, 900)


@pytest.mark.parametrize("changes", [
    {"resource": "wine"}, {"mode": "exact", "amount": 901},
    {"mode": "percentage", "amount": 50}, {"available_only": True, "allow_fallback": True},
    {"mode": "exact", "amount": True}, {"mode": "maximum", "amount": 100},
])
def test_rejects_invalid_or_unmatched_targets(changes):
    with pytest.raises(ValueError):
        plan_city_production(observed(), draft(**changes))


def test_inventory_reuses_upstream_helpers(monkeypatch):
    from ikabot.function import productionWorkforce as module
    class Session:
        def get(self, url):
            assert url.endswith("2")
            return "island"
    monkeypatch.setattr(module, "requireOwnCity", lambda *args: "1")
    monkeypatch.setattr(module, "getCityById", lambda *args, **kwargs: {
        "id": "1", "islandId": "2", "name": "Synthetic", "freeCitizens": 200,
        "position": [{"building": "academy"}]})
    monkeypatch.setattr(module, "getIsland", lambda html: {"id": 2, "tipo": "3"})
    kinds = []
    def read(session, city, kind):
        kinds.append(kind)
        return {"max_value": 750, "overcharge": 150, "value": 400 if kind == "tradegood" else None}, None
    monkeypatch.setattr(module, "_read_worker_slider", read)
    result = read_city_production(Session(), 1)
    assert result["luxury"] == "crystal"
    assert result["free_citizens"] == 200
    assert result["sites"]["resource"]["current"] is None
    assert result["sites"]["tradegood"]["current"] == 400
    assert result["sites"]["temple"]["reason"] == "building_absent"
    assert kinds == ["resource", "tradegood", "academy"]


def test_inventory_api_rejects_wrong_identity_foreign_city_and_bad_shape(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from daedalus.api import create_app
    from daedalus.engine_ipc import ExistingIPCClient

    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n')
    ipc = ExistingIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda account: [{"id": 1, "name": "Town"}])
    sample = observed()
    sample["city_name"] = "Town"
    sample["sites"].update(academy={"available": False, "reason": "building_absent"},
                           temple={"available": False, "reason": "building_absent"})
    calls = []
    identity = {"world": "s1-en", "username": "Example"}
    def exchange(payload, **kwargs):
        calls.append(payload)
        return {"status": "ok", **identity, "inventory": sample}
    monkeypatch.setattr(ipc, "_exchange", exchange)
    token = "x" * 48
    with TestClient(create_app(accounts_path=file, api_token=token, ipc_client=ipc)) as client:
        path = "/api/v1/accounts/alpha/cities/1/production"
        auth = {"Authorization": "Bearer " + token}
        assert client.get(path).status_code == 401
        assert client.get(path.replace("/1/", "/2/"), headers=auth).status_code == 404
        assert not calls
        result = client.get(path, headers=auth)
        assert result.status_code == 200, result.text
        assert result.json() == {"account_id": "alpha", **sample}
        assert calls == [{"action": "production_inventory_existing", "world": "s1-en",
                          "player": "Example", "city_id": 1}]
        identity["username"] = "Other"
        assert client.get(path, headers=auth).status_code == 503
        identity["username"] = "Example"
        sample["free_citizens"] = True
        assert client.get(path, headers=auth).status_code == 503
        sample["free_citizens"] = None
        sample["sites"]["resource"]["current"] = None
        assert client.get(path, headers=auth).json()["sites"]["resource"]["current"] is None
        assert client.post(path, headers=auth, json={}).status_code == 405


@pytest.fixture
def staged_city(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from uuid import uuid4

    from daedalus.recovery_state import RecoveryStore
    from ikabot.function import productionWorkforce as module
    from ikabot.helpers.productionJournal import ProductionJournal

    source = observed()
    session = SimpleNamespace(mundo=1, servidor="en", username="Example")
    store = RecoveryStore(tmp_path / "private" / "recovery.db")
    calls = []
    delays = []
    monkeypatch.setattr(module, "read_city_production", lambda *_: copy.deepcopy(source))
    monkeypatch.setattr(module, "wait", lambda *args: delays.append(args))
    def submit(_session, city, island, kind, position, value, *, reviewed):
        assert (city, island, position, reviewed) == ("1", "2", None, True)
        old = source["sites"][kind]["current"]
        source["sites"][kind]["current"] = value
        if source["free_citizens"] is not None:
            source["free_citizens"] += old - value
        calls.append((kind, value))
    monkeypatch.setattr(module, "_submit_worker_assignment", submit)
    def approve(settings):
        plan = module.plan_city_production(source, settings)
        run_id = str(uuid4())
        with store._db() as conn:
            conn.execute("INSERT INTO production_runs VALUES(?,?,?,?,?,?,'prepared',0)",
                         (run_id, "alpha", "identity", "s1-en", "example",
                          json.dumps([plan], sort_keys=True, separators=(",", ":"))))
        return plan, ProductionJournal(session, run_id, [plan], db_path=store.path)
    return SimpleNamespace(source=source, session=session, calls=calls, delays=delays,
                           approve=approve, store=store, module=module, submit=submit)


def test_staged_execution_minimum_release_and_confirmed_readback(staged_city):
    f = staged_city
    plan, journal = f.approve(draft())
    result = f.module.execute_city_production(f.session, plan, journal)
    assert result == {"city_id": 1, "target": 900, "donor": 400, "shortfall": 0}
    assert f.calls == [("resource", 400), ("tradegood", 900)]
    assert f.delays == [(2, 2), (2, 2)]
    with f.store._db() as conn:
        assert [tuple(r) for r in conn.execute("SELECT stage,status FROM production_stages ORDER BY rowid")] == [
            ("release", "confirmed"), ("target", "confirmed")]
        assert conn.execute("SELECT status FROM production_cities").fetchone()[0] == "complete"
    with pytest.raises(ValueError):
        journal.begin_city(plan)


def test_staged_fallback_restores_only_unused_donor(staged_city, monkeypatch):
    f = staged_city
    f.source["free_citizens"] = None
    plan, journal = f.approve(draft(allow_fallback=True))
    def reveal_population(*args, **kwargs):
        f.submit(*args, **kwargs)
        if len(f.calls) == 1:
            f.source["free_citizens"] = 900
    monkeypatch.setattr(f.module, "_submit_worker_assignment", reveal_population)
    result = f.module.execute_city_production(f.session, plan, journal)
    assert f.calls == [("resource", 0), ("tradegood", 900), ("resource", 400)]
    assert result["donor"] == 400


@pytest.mark.parametrize("error", [TimeoutError, KeyboardInterrupt])
def test_pending_stage_survives_uncertain_write_and_blocks_replay(staged_city, monkeypatch, error):
    f = staged_city
    plan, journal = f.approve(draft())
    def interrupted(*args, **kwargs):
        f.submit(*args, **kwargs)
        raise error("Connection interrupted")
    monkeypatch.setattr(f.module, "_submit_worker_assignment", interrupted)
    with pytest.raises(error):
        f.module.execute_city_production(f.session, plan, journal)
    assert f.calls == [("resource", 400)]
    with f.store._db() as conn:
        assert conn.execute("SELECT status FROM production_stages").fetchone()[0] == "pending"
    with pytest.raises(ValueError, match="Incomplete"):
        journal.begin_city(plan)
    with pytest.raises(ValueError, match="Unsafe"):
        journal.reserve(plan, "target", "tradegood", 900)


def test_silent_rejection_does_not_trigger_unsafe_compensation(staged_city, monkeypatch):
    f = staged_city
    plan, journal = f.approve(draft())
    def rejected(*args, **kwargs):
        if args[3] == "resource":
            f.submit(*args, **kwargs)
    monkeypatch.setattr(f.module, "_submit_worker_assignment", rejected)
    with pytest.raises(f.module.ProductionNeedsReview):
        f.module.execute_city_production(f.session, plan, journal)
    assert f.calls == [("resource", 400)]
    with f.store._db() as conn:
        assert [tuple(r) for r in conn.execute("SELECT stage,status FROM production_stages ORDER BY rowid")] == [
            ("release", "confirmed"), ("target", "pending")]


def test_stale_capacity_and_resource_identity_block_before_write(staged_city):
    f = staged_city
    plan, journal = f.approve(draft())
    f.source["sites"]["resource"]["maximum"] += 1
    with pytest.raises(ValueError, match="stale"):
        f.module.execute_city_production(f.session, plan, journal)
    assert not f.calls
    f.source["sites"]["resource"]["maximum"] -= 1
    f.source["luxury"] = "wine"
    with pytest.raises(ValueError):
        f.module.execute_city_production(f.session, plan, journal)
    assert not f.calls


def test_decreasing_target_without_known_free_population(staged_city):
    f = staged_city
    f.source["free_citizens"] = None
    plan, journal = f.approve(draft(mode="exact", amount=250, overcharge=False))
    result = f.module.execute_city_production(f.session, plan, journal)
    assert f.calls == [("tradegood", 250)]
    assert result["donor"] == 700


def test_reviewed_api_dispatch_and_reconcile_fence(monkeypatch, tmp_path):
    import uuid
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.api import create_app
    from daedalus.engine_ipc import ControlledIPCClient
    from daedalus.recovery_state import RecoveryStore
    from daedalus.task_control import TaskController
    from ikabot.function import productionWorkforce as module
    from ikabot.helpers.productionJournal import ProductionJournal

    file = tmp_path / "accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts = load_accounts(file)
    coordinator = AccountSessionCoordinator(accounts, state_dir=tmp_path / "leases")
    ipc = ControlledIPCClient()
    store = RecoveryStore(tmp_path / "private" / "recovery.db")
    sample = observed()
    sample["city_name"] = "Town"
    sample["sites"].update(academy={"available": False, "reason": "building_absent"},
                           temple={"available": False, "reason": "building_absent"})
    session = SimpleNamespace(mundo=1, servidor="en", username="Example")
    monkeypatch.setattr(module, "read_city_production", lambda *_: copy.deepcopy(sample))
    monkeypatch.setattr(ipc, "cities", lambda _account: [{"id": 1, "name": "Town"}])
    monkeypatch.setattr(ipc, "has_account", lambda account: True)
    monkeypatch.setattr(ipc, "preflight_task", lambda account, task: {"task": task, "ready": True, "reason": "none"})
    monkeypatch.setattr(ipc, "list_managed_tasks", lambda account: [])
    def exchange(payload, **kwargs):
        reply = {"status": "ok", "world": payload["world"], "username": payload["player"]}
        if payload["action"] == "production_inventory_existing":
            return {**reply, "inventory": copy.deepcopy(sample)}
        assert payload["action"] == "preview_workers_existing"
        return {**reply, "plans": module.preview_priority_production(session, payload["city_id"], payload["priority"])}
    monkeypatch.setattr(ipc, "_exchange", exchange)
    starts = []
    def start(account, task, config, request_id):
        # The controller must persist the exact immutable plan BEFORE dispatch.
        journal = ProductionJournal(session, config["production_run_id"], config["production_plans"], db_path=store.path)
        starts.append((account.id, task, config, journal))
        return {"task_id": "a" * 24, "pid": 1234}
    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller = TaskController(accounts, coordinator, ipc, ledger_path=tmp_path / "tasks.sqlite",
                                recovery_store=store)
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    with TestClient(create_app(accounts_path=file, api_token=token, session_coordinator=coordinator,
                               task_controller=controller, ipc_client=ipc)) as client:
        path = "/api/v1/accounts/alpha/cities/1/worker-plan"
        request = {"task": "modifyProduction", "draft": {"priority": [{"city_id": 1, "draft": draft()}]}}
        assert client.post(path, json=request).status_code == 401
        assert client.post(path, headers=auth, json={"task": "modifyProduction", "draft": {
            "priority": [{"city_id": 1, "draft": draft()}, {"city_id": 2, "draft": draft()}]}}).status_code == 422
        review = client.post(path, headers=auth, json=request)
        assert review.status_code == 200, review.text
        payload = {"task": "modifyProduction", "preview_id": review.json()["preview_id"],
                   "request_id": str(uuid.uuid4()), "confirmed": True}
        route = "/api/v1/accounts/alpha/tasks/worker-start"
        assert client.post(route.replace("alpha", "beta"), headers=auth, json=payload).status_code == 409
        assert not starts
        started = client.post(route, headers=auth, json=payload)
        assert started.status_code == 200, started.text
        assert len(starts) == 1
        assert client.post(route, headers=auth, json=payload).status_code == 200
        assert len(starts) == 1
        assert controller.preflight("alpha", "alertAttacks")["unresolved_request"] is True
        assert store.production_blocked(accounts[0])
        assert not store.production_blocked(accounts[1])
        plan = starts[0][2]["production_plans"][0]
        journal = starts[0][3]
        journal.begin_city(plan)
        journal.reserve(plan, "release", "resource", 400)
        sample["sites"]["resource"]["current"] = 400
        history_path = "/api/v1/accounts/alpha/production-runs"
        history = client.get(history_path, headers=auth).json()
        assert history["runs"][0]["cities"][0]["stages"][0]["status"] == "pending"
        reconcile_path = history_path + "/" + payload["request_id"]
        # The new run remains fenced until actual counts are independently reviewed.
        preview = client.post(reconcile_path + "/reconcile-plan", headers=auth, json={})
        assert preview.status_code == 200, preview.text
        assert preview.json()["observations"][0]["resource"] == 400
        approve = {"preview_id": preview.json()["preview_id"], "request_id": str(uuid.uuid4()), "confirmed": True}
        sample["sites"]["resource"]["current"] = 401
        assert client.post(reconcile_path + "/reconcile", headers=auth, json=approve).status_code == 409
        assert store.production_blocked(accounts[0])
        sample["sites"]["resource"]["current"] = 400
        result = client.post(reconcile_path + "/reconcile", headers=auth, json=approve)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "reconciled"
        assert not store.production_blocked(accounts[0])
        assert len(starts) == 1
        with pytest.raises(ValueError):
            journal.reserve(plan, "target", "tradegood", 900)
    controller.close()


@pytest.mark.parametrize("free,only,expected", [(200,False,(900,400)), (200,True,(600,700)), (700,False,(900,800))])
def test_both_resource_priority_plan_and_execution(staged_city, free, only, expected):
    from daedalus.production_inventory import validate_priority_plan
    f = staged_city
    f.source["free_citizens"] = free
    settings = draft(fill_both=True, available_only=only)
    plan, journal = f.approve(settings)
    assert (plan["target_after"], plan["donor_after"]) == expected
    assert validate_priority_plan(1, settings, plan) == plan
    result = f.module.execute_city_production(f.session, plan, journal)
    assert (result["target"], result["donor"]) == expected
    if only:
        assert not any(kind == "resource" and value < 700 for kind,value in f.calls)
    if free == 700:
        assert f.calls == [("tradegood",900),("resource",800)]


def test_both_resource_plan_disallows_unreviewed_fallback():
    with pytest.raises(ValueError):
        plan_city_production(observed(None), draft(fill_both=True))
    with pytest.raises(ValueError):
        plan_city_production(observed(None), draft(fill_both=True, allow_fallback=True))


def test_unknown_capacity_requires_reviewed_maximum_and_fresh_readback(staged_city, monkeypatch):
    from daedalus.production_inventory import validate_priority_plan
    f = staged_city
    f.source["sites"]["tradegood"]["maximum"] = None
    with pytest.raises(ValueError, match="unknown"):
        f.approve(draft())
    settings = draft(allow_fallback=True)
    plan, journal = f.approve(settings)
    assert plan["desired"] is None and plan["donor_release"] == 700
    assert validate_priority_plan(1, settings, plan) == plan
    def reveal_capacity(*args, **kwargs):
        f.submit(*args, **kwargs)
        if len(f.calls) == 1:
            f.source["sites"]["tradegood"]["maximum"] = 750
    monkeypatch.setattr(f.module, "_submit_worker_assignment", reveal_capacity)
    result = f.module.execute_city_production(f.session, plan, journal)
    assert result == {"city_id":1,"target":900,"donor":400,"shortfall":0}
    assert f.calls == [("resource",0),("tradegood",900),("resource",400)]


def test_unknown_capacity_after_release_fences_instead_of_guessing(staged_city):
    f = staged_city
    f.source["sites"]["tradegood"]["maximum"] = None
    plan, journal = f.approve(draft(allow_fallback=True))
    with pytest.raises(ValueError, match="verify"):
        f.module.execute_city_production(f.session, plan, journal)
    assert f.calls == [("resource",0)]
    with pytest.raises(ValueError, match="Incomplete"):
        journal.begin_city(plan)
