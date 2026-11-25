"""Independent account reviews for rewards and exact distribution routes."""
from unittest.mock import Mock

import pytest
from ikabot.function import distributeResources, loginDaily
from test_recurring_review import DRAFT as CONSOLIDATION_DRAFT
from test_recurring_review import OBS as CONSOLIDATION_OBS

from daedalus.daily_distribution_review import (
    daily_draft,
    distribution_draft,
    validate_daily,
    validate_distribution,
)
from daedalus.reviewed_batch import validated_batch_entries

DRAFT = {"resource":"wood","mode":"even","cities_ids":[101,102],"useFreighters":False}
ROUTES = [{"from":101,"to":102,"resources":[200,0,0,0,0]}]
PLAN = {"routes":[{**ROUTES[0],"origin_name":"Athens","destination_name":"Sparta",
                  "stock":[400,0,0,0,0],"destination_space":[500,0,0,0,0],
                  "first_load_limit":100,"minimum_loads":2}],
        "capacity":100,"available_ships":1,"total_ships":1,"ready":True,"useFreighters":False}


def test_distribution_projection_rejects_foreign_wrong_resource_and_overflow():
    assert validate_distribution(distribution_draft(DRAFT), PLAN) == ROUTES
    for row in ({**PLAN["routes"][0],"to":103},
                {**PLAN["routes"][0],"resources":[0,200,0,0,0]},
                {**PLAN["routes"][0],"destination_space":[150,0,0,0,0]}):
        with pytest.raises(ValueError):
            validate_distribution(DRAFT,{**PLAN,"routes":[row]})
    with pytest.raises(ValueError):
        distribution_draft({**DRAFT,"cities_ids":[101,101]})
    assert validated_batch_entries([
        {"account_id":"alpha","task":"distributeResources","preview_id":"a"*43},
        {"account_id":"beta","task":"loginDaily","preview_id":"b"*43}])


def test_distribution_worker_rejects_recalculated_allocation(monkeypatch):
    session=Mock()
    cities={"101":{"id":"101","name":"Athens"},"102":{"id":"102","name":"Sparta"}}
    monkeypatch.setattr(distributeResources,"getIdsOfCities",lambda *_:(list(cities),cities))
    monkeypatch.setattr(distributeResources,"requireOwnCity",lambda _s,c,_n:str(c))
    monkeypatch.setattr(distributeResources,"plan_routes",lambda *_:[(cities["101"],cities["102"],1,201,0,0,0,0)])
    with pytest.raises(ValueError,match="allocation changed"):
        distributeResources.prepare_distributeResources(session,**DRAFT,reviewed_routes=ROUTES)
    session.post.assert_not_called()


def test_daily_preview_reads_only_advisor(monkeypatch):
    session=Mock()
    monkeypatch.setattr(loginDaily,"requireOwnCity",lambda _s,c,_n:str(c))
    monkeypatch.setattr(loginDaily,"getIdsOfCities",lambda *_:(["101"],{"101":{"name":"Athens"}}))
    session.post.return_value='{"currentFavor":20,"favorLimit":100,"dailyTasksCountdown":{"countdown":{"enddate":1000,"currentdate":500}}}'
    draft=daily_draft({"wine_city":101})
    result=loginDaily.preview_daily_rewards(session,draft)
    assert result=={"cities":{"wine_city":"Athens"},"favour":20,"limit":100,"reset_seconds":500,"collectable":0}
    assert validate_daily(draft,result)==result
    session.post.assert_called_once()
    assert "view=dailyTasks" in session.post.call_args.args[0]
    assert session.post.call_args.kwargs=={"retry_on_failure":False}
    with pytest.raises(ValueError):
        validate_daily(draft,{**result,"favour":101})
    with pytest.raises(ValueError):
        daily_draft({"wine_city":101,"favour_tasks":[{}]})

@pytest.mark.parametrize(("task","endpoint","draft","observation"),[
    ("consolidateResources","consolidate-start",CONSOLIDATION_DRAFT,CONSOLIDATION_OBS),
    ("distributeResources","distribution-start",DRAFT,PLAN),
    ("loginDaily","daily-start",daily_draft({"wine_city":101}),
     {"cities":{"wine_city":"Athens"},"favour":20,"limit":100,"reset_seconds":500,"collectable":0}),
])
def test_review_ticket_scope_and_replay(monkeypatch,tmp_path,task,endpoint,draft,observation):
    import uuid

    from fastapi.testclient import TestClient

    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.api import create_app
    from daedalus.engine_ipc import ControlledIPCClient
    from daedalus.task_control import TaskController

    file=tmp_path/"accounts.toml"
    file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Mine"\n'
                    '[[accounts]]\nid = "beta"\nworld = "s1-en"\nplayer = "Other"\n')
    accounts=load_accounts(file)
    owner=AccountSessionCoordinator(accounts,state_dir=tmp_path/"locks")
    ipc=ControlledIPCClient()
    monkeypatch.setattr(ipc,"preflight_task",lambda _a,t:{
        "task":t,"ready":True,"reason":"none","notifications_required":False,"checked":[]})
    monkeypatch.setattr(ipc,"has_account",lambda _a:True)
    monkeypatch.setattr(ipc,"native_reward_distribution_preview",lambda _a,_t,_d:observation)
    monkeypatch.setattr(ipc,"recurring_preview",lambda _a,_t,_d:observation)
    starts=[]
    def start(account,t,config,rid):
        starts.append((account.id,t,config,rid))
        return {"task_id":"a"*24,"pid":1234,"task":t,"status":"running"}
    monkeypatch.setattr(ipc,"start_managed_task",start)
    controller=TaskController(accounts,owner,ipc,ledger_path=tmp_path/"tasks.sqlite")
    token="x"*48
    auth={"Authorization":"Bearer "+token}
    client=TestClient(create_app(accounts_path=file,api_token=token,session_coordinator=owner,
                                 task_controller=controller,ipc_client=ipc))
    try:
        path="/api/v1/accounts/alpha"
        response=client.post(path+"/reward-distribution-plan",headers=auth,json={"task":task,"draft":draft})
        assert response.status_code==200,response.text
        rid=str(uuid.uuid4())
        payload={"preview_id":response.json()["preview_id"],"request_id":rid,"confirmed":True}
        assert client.post(path.replace("alpha","beta")+"/tasks/"+endpoint,headers=auth,json=payload).status_code==409
        assert client.post(path+"/tasks",headers=auth,json={
            "task":task,"config":draft,"request_id":rid,"confirmed":True}).status_code==422
        assert not starts
        assert client.post(path+"/tasks/"+endpoint,headers=auth,json=payload).status_code==200
        assert starts[0][:2]==("alpha",task)
        assert starts[0][2]==({**draft,"reviewed_routes":ROUTES} if task=="distributeResources" else draft)
        assert client.post(path+"/tasks/"+endpoint,headers=auth,json=payload).status_code==200
        assert len(starts)==1
    finally:
        controller.close()
