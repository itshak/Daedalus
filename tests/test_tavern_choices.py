"""Exact one-shot tavern servings are not an equilibrium schedule."""
from unittest.mock import Mock

import pytest
from ikabot.function import tavernManager as engine

from daedalus.recovery_reconcile import restart_class_for
from daedalus.tavern_choices import fixed_tavern_review, validate_fixed_tavern

CITY = {"id": "11", "name": "Athens", "position": [{"building": "tavern", "position": 2}]}
INFO = {"current_level": 1, "level_observed": True, "action_code": "synthetic",
        "consumption_values": [(0, 0), (1, 5), (2, 12), (3, 20), (4, 30)]}
ROW = {"city_id": 11, "city_name": "Athens", "has_tavern": True,
       "serving_level": 1, "wine_per_hour": 5, "serving_options": [list(r) for r in INFO["consumption_values"]]}


def test_exact_percentage_projection():
    assert engine.native_serving_options(INFO) == ROW["serving_options"]
    assert engine.native_serving_options({**INFO, "level_observed": False}) is None
    draft = fixed_tavern_review([ROW], 75)
    assert draft["rows"][0] == {"city_id": 11, "city_name": "Athens", "current_level": 1,
                                "max_level": 4, "target_level": 3, "current_wine": 5, "target_wine": 20}
    assert restart_class_for("tavernManager", {"run_hours": 0, "fixed_servings": draft}) == "manual"
    with pytest.raises(ValueError):
        fixed_tavern_review([ROW, ROW], 50)
    with pytest.raises(ValueError):
        fixed_tavern_review([{**ROW, "serving_options": None}], 50)
    draft["rows"][0]["target_level"] = 4
    with pytest.raises(ValueError):
        validate_fixed_tavern(draft)


def test_worker_rechecks_all_rows_and_observes_the_submission(monkeypatch):
    session = Mock()
    info = dict(INFO)
    monkeypatch.setattr(engine, "requireOwnCity", lambda _s, cid, _: str(cid))
    monkeypatch.setattr(engine, "getCity", lambda _: CITY)
    monkeypatch.setattr(engine.TavernManager, "_get_tavern_data", lambda *_a, **_k: info.copy())
    draft = fixed_tavern_review([ROW], 75)
    assert engine.prepare_tavernManager(session, 0, fixed_servings=draft)["fixed_servings"] == draft
    session.post.assert_not_called()
    info["current_level"] = 2
    with pytest.raises(ValueError, match="changed"):
        engine.do_tavernManager.__wrapped__(session, 0, fixed_servings=draft)
    session.post.assert_not_called()
    info["current_level"] = 1
    session.post.side_effect = lambda **_kw: info.update(current_level=3)
    engine.do_tavernManager.__wrapped__(session, 0, fixed_servings=draft)
    session.post.assert_called_once()
    assert session.post.call_args.kwargs["retry_on_failure"] is False
    assert session.post.call_args.kwargs["params"]["amount"] == 3
    info["current_level"] = 1
    session.post.reset_mock()
    session.post.side_effect = None
    with pytest.raises(RuntimeError, match="unconfirmed"):
        engine.do_tavernManager.__wrapped__(session, 0, fixed_servings=draft)
    session.post.assert_called_once()
