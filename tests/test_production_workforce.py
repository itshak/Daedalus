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
    monkeypatch.setattr(module, "getCityById", lambda *args: {
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
