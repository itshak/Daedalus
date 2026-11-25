"""Synthetic recruitment review; no live game sessions."""
import copy
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.function import trainArmy as engine

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for
from daedalus.task_control import TaskController
from daedalus.training_contract import (
    build_training_review,
    training_draft,
    validate_training_review,
)


def catalog(cid=1):
    return {"account_id": "alpha", "city_id": cid, "train_troops": True,
            "city": {"id": str(cid), "pos": "3", "cityName": f"Town {cid}"},
            "units": [{"unit_type_id": 301, "local_name": "Swordsman",
                       "costs": {"wood": 10, "citizens": 1}},
                      {"unit_type_id": 302, "local_name": "Hoplite",
                       "costs": {"wood": 20, "sulfur": 5, "citizens": 1}}],
            "available": [100, 0, 0, 0, 100], "free_citizens": 10}


DRAFT = {"city_ids": [1, 2], "train_troops": True,
         "rounds": [[{"unit_type_id": 301, "cantidad": 2}],
                    [{"unit_type_id": 302, "cantidad": 3}]], "cycles": 2}


def test_review_uses_exact_costs_and_rejects_scope():
    plan = build_training_review("alpha", DRAFT, [catalog(1), catalog(2)])
    assert plan["ready"] and plan["cities"][0]["total_costs"] == [160, 0, 0, 0, 30, 10]
    public = {k: v for k, v in plan.items() if k != "config"}
    public.update(preview_id="a"*43, expires_in=120)
    validate_training_review("alpha", DRAFT, public)
    tampered = copy.deepcopy(public)
    tampered["cities"][0]["total_costs"][0] = 159
    with pytest.raises(ValueError):
        validate_training_review("alpha", DRAFT, tampered)
    with pytest.raises(ValueError):
        build_training_review("alpha", DRAFT, [catalog(2), catalog(1)])
    with pytest.raises(ValueError):
        training_draft({**DRAFT, "city_ids": [1, 1]})
    with pytest.raises(ValueError):
        training_draft({**DRAFT, "cycles": True})
    assert restart_class_for("trainArmy", plan["config"]) == "manual"


def test_reviewed_training_stops_on_unobserved_queue_or_stale_cost(monkeypatch):
    plan = build_training_review("alpha", DRAFT, [catalog(1), catalog(2)])
    session = Mock()
    monkeypatch.setattr(engine, "available_trainable_units", lambda _s,cid,_m: catalog(int(cid)))
    monkeypatch.setattr(engine, "waitForTraining", lambda *_a: None)
    monkeypatch.setattr(engine, "getBuildingInfo", lambda *_a: [[], [None,None,["","",""]]])
    # Exact response shape from waitForTraining: [1][1][1] is HTML.
    monkeypatch.setattr(engine, "getBuildingInfo", lambda *_a: [[], [None,[None,""]]])
    with pytest.raises(ValueError, match="not observed"):
        engine._run_reviewed_training(session, plan["config"]["reviewed_jobs"], True)
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["retry_on_failure"] is False
    session.reset_mock()
    monkeypatch.setattr(engine, "getBuildingInfo",
                        lambda *_a: [[], [None,[None,"'buildProgress', 1234,"]]])
    engine._run_reviewed_training(session, plan["config"]["reviewed_jobs"], True)
    assert session.post.call_count == 8
    session.reset_mock()

    def changed(_s, cid, _m):
        data = catalog(int(cid))
        data["units"][0]["costs"]["wood"] = 11
        return data

    monkeypatch.setattr(engine, "available_trainable_units", changed)
    with pytest.raises(ValueError, match="changed"):
        engine.prepare_trainArmy(session, **plan["config"])
    session.post.assert_not_called()


def test_training_ticket_scope_and_native_launch_guard(monkeypatch, tmp_path):
    file = tmp_path/"accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Example"\n')
    accounts = load_accounts(file)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path/"locks")
    ipc = ControlledIPCClient()
    monkeypatch.setattr(ipc, "cities", lambda _a: [{"id":1},{"id":2}])
    monkeypatch.setattr(ipc, "trainable_units", lambda _a,cid,**_kw: catalog(cid))
    monkeypatch.setattr(ipc, "has_account", lambda _a: True)
    monkeypatch.setattr(ipc, "preflight_task", lambda _a,task: {
        "task":task,"ready":True,"reason":"none","notifications_required":False,"checked":[]})
    starts=[]
    def start(account,task,config,rid):
        starts.append((account.id,task,config,rid))
        return {"task_id":"a"*24,"pid":1234,"task":task,"status":"running"}
    monkeypatch.setattr(ipc, "start_managed_task", start)
    controller=TaskController(accounts,owner,ipc,ledger_path=tmp_path/"tasks.sqlite")
    token="x"*48
    auth={"Authorization":"Bearer "+token}
    client=TestClient(create_app(accounts_path=file,api_token=token,ipc_client=ipc,
                                  session_coordinator=owner,task_controller=controller))
    try:
        path="/api/v1/accounts/alpha/cities/1/training-plan"
        assert client.post(path,headers=auth,json={**DRAFT,"city_ids":[1,3]}).status_code==422
        reply=client.post(path,headers=auth,json=DRAFT)
        assert reply.status_code==200, reply.text
        plan=reply.json()
        assert "config" not in plan and plan["ready"]
        payload={"preview_id":plan["preview_id"],"request_id":str(uuid.uuid4()),"confirmed":True}
        assert client.post("/api/v1/accounts/alpha/tasks",headers=auth,json={
            "task":"trainArmy","config":{},"request_id":str(uuid.uuid4()),"confirmed":True}).status_code==422
        url="/api/v1/accounts/alpha/tasks/training-start"
        assert client.post(url,headers=auth,json=payload).status_code==200
        assert starts[0][2]["reviewed_jobs"]["cycles"]==2
        assert client.post(url,headers=auth,json=payload).status_code==200
        assert len(starts)==1
    finally:
        controller.close()
