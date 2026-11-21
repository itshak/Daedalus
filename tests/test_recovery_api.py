"""Authenticated recovery policy/API and durable desired job tracking."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.recovery_state import RecoveryStore
from daedalus.task_control import TaskController

TOKEN="R"*48
AUTH={"Authorization":f"Bearer {TOKEN}"}


class FakeIPC:
    def has_account(self,_):return True
    def validate_account(self,_):return True
    def preflight_task(self,account,task):
        return {"ready":True,"task":task,"reason":"none","checked":[]}
    def start_managed_task(self,account,task,config,rid):
        return {"task_id":"a"*24,"pid":19200}
    def stop_managed_task(self,account,task_id):
        return {"task_id":task_id,"status":"stopped"}
    def list_managed_tasks(self,account):
        return [{"task_id":"a"*24,"task":"alertAttacks","status":"running"}]


class FakeCredentials:
    def __init__(self):self.token=False
    def available(self,_):return self.token
    def import_saved(self,account,*,confirmed):
        assert confirmed
        self.token=True
    def forget(self,account,*,confirmed):
        self.token=False


def test_authenticated_policy_import_pause_resume_and_bulk(tmp_path):
    acc=Account("alpha","s301-en","ExamplePlayer","Example",True)
    config=tmp_path/"accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\n'
        'world = "s301-en"\nplayer = "ExamplePlayer"\nlabel = "Example"\n',
    )
    store=RecoveryStore(tmp_path/"recovery.sqlite3")
    owner=AccountSessionCoordinator([acc],state_dir=tmp_path/"locks")
    controller=TaskController([acc],owner,FakeIPC(),ledger_path=tmp_path/"tasks.sqlite3",
                              recovery_store=store)
    creds=FakeCredentials()
    app=create_app(accounts_path=config,api_token=TOKEN,session_coordinator=owner,
                   task_controller=controller,recovery_store=store,
                   recovery_credentials=creds)
    try:
        with TestClient(app) as client:
            root="/api/v1/accounts/alpha/recovery"
            assert client.get(root).status_code==401
            data=client.get(root,headers=AUTH).json()
            assert data["policy"]["enabled"] is False
            assert data["server_token_available"] is False
            policy={"confirmed":True,"enabled":True,"auto_resume":True,
                    "expected_revision":0,"grace_seconds":300}
            assert client.put(root+"/policy",headers=AUTH,json=policy).status_code==409
            assert client.post(root+"/import-saved-token",
                               headers=AUTH,json={"confirmed":False}).status_code==422
            assert client.post(root+"/import-saved-token",
                               headers=AUTH,json={"confirmed":True}).json()["server_token_available"]
            assert client.put(root+"/policy",headers=AUTH,json=policy).json()["enabled"]
            assert client.put(root+"/policy",headers=AUTH,json=policy).status_code==409
            pause=client.post(root+"/pause",headers=AUTH,
                              json={"confirmed":True,"seconds":900})
            assert pause.status_code==200
            assert pause.json()["pause_until"] is not None
            assert client.post(root+"/unpause",headers=AUTH,
                               json={"confirmed":True}).json()["pause_until"] is None
            assert client.post(root+"/resume-now",headers=AUTH,
                               json={"confirmed":True}).status_code==503
            assert client.get("/api/v1/recovery",headers=AUTH).json()["accounts"][0]["policy"]["enabled"]

            # A single confirmed task launch creates a durable desired config.
            task=client.post("/api/v1/accounts/alpha/tasks",headers=AUTH,json={
                "confirmed":True,"task":"alertAttacks","config":{"listen":True},
                "request_id":str(uuid.uuid4()),
            })
            assert task.status_code==200,task.text
            job_id=task.json()["desired_job_id"]
            jobs=client.get(root+"/jobs",headers=AUTH).json()["jobs"]
            assert len(jobs)==1 and jobs[0]["id"]==job_id
            assert jobs[0]["config"]=={"listen":True}
            result=client.post(
                "/api/v1/accounts/alpha/tasks/"+("a"*24)+"/stop",headers=AUTH,
            )
            assert result.status_code==200
            assert client.get(root+"/jobs",headers=AUTH).json()["jobs"][0]["desired_state"]=="stopped"
            assert client.post("/api/v1/recovery/policy/bulk",headers=AUTH,json={
                "confirmed":True,"account_ids":["alpha"],
                "enabled":False,"auto_resume":False,
            }).json()["results"][0]["status"]=="saved"
            assert client.get(root,headers=AUTH).json()["policy"]["enabled"] is False
    finally:
        controller.close()


def test_all_recovery_endpoints_require_bearer_and_exact_account(tmp_path):
    acc=Account("a","s301-en","Player","Player",True)
    config=tmp_path/"accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "a"\n'
                      'world = "s301-en"\nplayer = "Player"\n')
    owner=AccountSessionCoordinator([acc],state_dir=tmp_path/"locks")
    store=RecoveryStore(tmp_path/"recover.sqlite3")
    ctl=TaskController([acc],owner,FakeIPC(),ledger_path=tmp_path/"tasks.sqlite3",
                       recovery_store=store)
    client=TestClient(create_app(accounts_path=config,api_token=TOKEN,
                                 session_coordinator=owner,task_controller=ctl,
                                 recovery_store=store,recovery_credentials=FakeCredentials()))
    try:
        for path in ("/api/v1/recovery","/api/v1/accounts/a/recovery",
                     "/api/v1/accounts/a/recovery/jobs"):
            assert client.get(path).status_code==401
        assert client.get("/api/v1/accounts/nope/recovery",headers=AUTH).status_code==404
        assert client.post("/api/v1/recovery/policy/bulk",headers=AUTH,json={
            "confirmed":True,"account_ids":["nope"],"enabled":True,"auto_resume":True,
        }).json()["results"][0]["status"]=="unknown_account"
        assert client.post("/api/v1/recovery/policy/bulk",headers=AUTH,json={
            "confirmed":True,"account_ids":["a","a"],"enabled":True,"auto_resume":True,
        }).status_code==422
        assert client.post("/api/v1/accounts/a/recovery/import-saved-token",
                           headers=AUTH,json={"confirmed":True,"cookie":"bad"}).status_code==422
    finally:
        ctl.close()
