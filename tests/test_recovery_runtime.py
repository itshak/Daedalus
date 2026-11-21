"""Synthetic, no-network session loss, cooldown, and fenced resume tests."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from daedalus.account_sessions import SessionPhase
from daedalus.accounts import Account
from daedalus.recovery_runtime import (
    RecoverySupervisor,
    RecoveryWorkerError,
    RoutedAccountIPC,
)
from daedalus.recovery_state import RecoveryStore


@pytest.fixture
def system(tmp_path):
    now=[1000.0]
    account=Account("account-a","s53-ru","monjo","Monjo",True)
    journal=RecoveryStore(tmp_path/"recovery.sqlite3",clock=lambda:now[0])
    journal.set_policy(account,enabled=True,auto_resume=True)
    class Credentials:
        active=True
        def available(self,_):return self.active
    class Ledger:
        uncertain=False
        def has_unresolved(self,_):return self.uncertain
    class Controller:
        def __init__(self):
            self._ledger=Ledger()
            self.started=[]
            self.raised=False
        def owned_sessions(self):
            return ()
        def list_tasks(self,_):
            return {"engine_tasks":[{"task":x["task"],"task_id":x["task_id"],
                                     "status":"running"} for x in self.started]}
        def start(self,aid,task,config,request_id,*,confirmed,track_desired):
            assert aid==account.id and confirmed and not track_desired
            assert request_id and config=={"listen": True}
            if self.raised:raise OSError("synthetic IPC lost reply")
            task_id="synth"+str(len(self.started))
            self.started.append({"task":task,"task_id":task_id})
            return {"status":"started","task_id":task_id}
    class Workers:
        def __init__(self):
            self.starts=[]
            self.running=None
        def get(self,_):
            return self.running
        def start(self,acc):
            self.starts.append(acc.id)
            return object()
        def close(self):pass
    creds=Credentials()
    workers=Workers()
    ctl=Controller()
    supervisor=RecoverySupervisor([account],journal,workers,ctl,creds,
                                  clock=lambda:now[0])
    return account,journal,creds,workers,ctl,supervisor,now


def test_verified_timer_uses_grace_and_restores_one_safe_background_job(system):
    a,j,_c,w,ctl,s,t=system
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    j.capture_started(a,"sendResources",{"listen":True},"manual")
    j.record_loss(a)
    s.tick()
    assert w.starts==[] and ctl.started==[]
    t[0]=1299
    s.tick()
    assert w.starts==[] and ctl.started==[]
    t[0]=1300
    s.tick()
    assert w.starts==[a.id]
    assert len(ctl.started)==1
    assert ctl.started[0]["task"]=="alertAttacks"
    assert j.event(a)["phase"]=="restored"
    receipts=j.receipts(a)
    assert len(receipts)==1 and receipts[0]["status"]=="started"
    s.tick()
    assert len(ctl.started)==1


def test_disabled_and_missing_tokens_never_login(system):
    a,j,c,w,_ctl,s,t=system
    c.active=False
    j.record_loss(a)
    t[0]=1300
    s.tick()
    assert w.starts==[]
    assert j.event(a)["phase"]=="failed"
    assert j.event(a)["last_reason"]=="token_unavailable"


def test_owner_browser_pause_prevents_login_even_if_due(system):
    a,j,_c,w,_ctl,s,t=system
    j.record_loss(a)
    j.pause(a,seconds=None)
    t[0]=2000
    s.tick()
    assert w.starts==[]


def test_manual_resume_requires_approved_policy_and_is_queued(system):
    a,j,_c,w,_ctl,s,_t=system
    assert s.request_now(a)=={"account_id":a.id,"status":"queued"}
    s.tick()
    assert w.starts==[a.id]
    assert j.event(a)["phase"]=="restored"
    j.set_policy(a,enabled=False,auto_resume=False)
    with pytest.raises(RecoveryWorkerError):
        s.request_now(a)


def test_uncertain_task_receipt_blocks_new_launchs(system):
    a,j,_c,_w,ctl,s,t=system
    job=j.capture_started(a,"alertAttacks",{"listen":True},"old")
    ctl.raised=True
    j.record_loss(a)
    t[0]=1300
    s.tick()
    receipt=j.receipts(a)
    assert len(receipt)==1 and receipt[0]["status"]=="unconfirmed"
    assert ctl.started==[]
    assert j.begin_resume(a,job,j.event(a)["epoch"]) is None


def test_known_unresolved_prior_request_blocks_task_restoration(system):
    a,j,_c,w,ctl,s,t=system
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    ctl._ledger.uncertain=True
    j.record_loss(a)
    t[0]=1300
    s.tick()
    assert w.starts==[a.id]
    assert ctl.started==[]
    assert j.receipts(a)==[]


def test_two_negative_probes_are_required_for_browser_loss(system):
    a,j,_c,w,_ctl,s,t=system
    class Lease:
        phase=SessionPhase.AUTHENTICATED
        def transition(self,phase):self.phase=phase
    class Worker:
        lease=Lease()
        stopped=0
        def alive(self):return True
        def stop(self):self.stopped+=1
    child=Worker()
    w.running=child
    w.router=SimpleNamespace(validate_account=lambda _:False)
    s.tick()
    assert j.event(a) is None
    t[0]+=9
    s.tick()
    assert j.event(a) is None
    t[0]+=1
    s.tick()
    assert j.event(a)["lost_at"]==1010
    assert j.event(a)["due_at"]==1310
    assert child.stopped==1
    assert child.lease.phase==SessionPhase.NEEDS_ASSISTANCE


def test_transient_negative_followed_by_healthy_does_not_schedule(system):
    a,j,_c,w,_ctl,s,t=system
    worker=SimpleNamespace(
        alive=lambda:True,
        lease=SimpleNamespace(phase=SessionPhase.AUTHENTICATED),
    )
    w.running=worker
    calls=[False,True,False]
    w.router=SimpleNamespace(validate_account=lambda _:calls.pop(0))
    s.tick()
    t[0]+=40
    s.tick()
    assert j.event(a) is None
    t[0]+=40
    s.tick()
    assert j.event(a) is None


def test_router_dispatches_only_to_correct_account_and_legacy_fallback():
    a=Account("a","s53-ru","A","A",True)
    b=Account("b","s53-ru","B","B",True)
    class FakeIPC:
        def __init__(self,tag):self.tag=tag
        def validate_account(self,acc):return (self.tag,acc.id)
        def list_sessions(self):return [{"tag":self.tag}]
    legacy=FakeIPC("legacy")
    router=RoutedAccountIPC(legacy)
    router._active[a.id]=FakeIPC("managed")
    assert router.validate_account(a)==("managed","a")
    assert router.validate_account(b)==("legacy","b")
    assert router.list_sessions()==[{"tag":"legacy"},{"tag":"managed"}]
    router.drop(a.id)
    assert router.validate_account(a)==("legacy","a")
    with pytest.raises(AttributeError):
        router.delete_everything(a)


def test_engine_account_descriptor_env_is_exact_and_private(tmp_path,monkeypatch):
    pytest.importorskip(
        "ikabot.helpers.ipc", reason="Bundled IkaBot engine not installed in core-only CI"
    )
    from ikabot.helpers.ipc import get_ipc_file_path, get_ipc_lock_path
    monkeypatch.delenv("DAEDALUS_ACCOUNT_IPC_FILE",raising=False)
    assert get_ipc_file_path().endswith(".ikabot/ipc.json")
    monkeypatch.setattr("pathlib.Path.home",lambda:tmp_path)
    directory=tmp_path/".local"/"state"/"daedalus"/"account-ipc"
    path=directory/(("a"*64)+".json")
    monkeypatch.setenv("DAEDALUS_ACCOUNT_IPC_FILE",str(path))
    assert get_ipc_file_path()==str(path)
    assert get_ipc_lock_path()==str(path)[:-5]+".lock"
    assert directory.is_dir()
    if os.name=="posix":assert directory.stat().st_mode & 0o077==0
    monkeypatch.setenv("DAEDALUS_ACCOUNT_IPC_FILE",str(tmp_path/"bad.json"))
    with pytest.raises(ValueError):
        get_ipc_file_path()


def test_child_uses_exact_bounded_secret_pipe_only(monkeypatch,capfd):
    import io
    import json

    from daedalus import recovery_child
    calls=[]
    class FakeSession:
        @classmethod
        def from_saved(cls,**kw):
            calls.append(("from_saved",kw["world"],kw["player"]))
            return SimpleNamespace()
    pytest.importorskip(
        "ikabot.web.session", reason="Bundled IkaBot engine not installed in core-only CI"
    )
    import ikabot.web.session as original
    from ikabot.helpers import ipc
    monkeypatch.setattr(original,"Session",FakeSession)
    monkeypatch.setattr(ipc,"start_dedicated_ipc_server",
                        lambda sess: calls.append(("IPC","started")) or object())
    monkeypatch.setattr(ipc,"stop_ipc_server",
                        lambda: calls.append(("IPC","stopped")))
    import daedalus.saved_session_recovery as saved
    monkeypatch.setattr(saved,"verify_restored_identity",
                        lambda sess,acc:calls.append(("verify",acc.id)))
    monkeypatch.setattr(recovery_child.sys,"stdin",
                        SimpleNamespace(buffer=io.BytesIO(json.dumps({
                            "id":"a","world":"s53-ru","player":"monjo",
                            "email":"example@invalid.test","lobby_token":"S"*30,
                        }).encode()+b"\n")))
    monkeypatch.setattr(recovery_child.time,"sleep",
                        lambda _:(_ for _ in ()).throw(KeyboardInterrupt()))
    assert recovery_child.main()==1
    assert calls==[("from_saved","s53-ru","monjo"),
                   ("verify","a"),("IPC","started"),("IPC","stopped")]
    assert capfd.readouterr().out==""


def test_broker_trusted_auto_reconnect_clears_stale_assistance(tmp_path):
    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.auth_assistance import AssistanceBroker, AssistanceReason
    a=Account("a","s53-ru","A","A",True)
    owner=AccountSessionCoordinator([a],state_dir=tmp_path/"locks")
    broker=AssistanceBroker(owner)
    lease=owner.acquire(a.id)
    lease.transition(SessionPhase.AUTHENTICATED)
    broker.request(lease,AssistanceReason.SESSION_EXPIRED)
    assert broker.snapshot(a.id)["ticket"] is not None
    broker.verified_auto_reconnect(lease,confirmed=True)
    assert lease.phase==SessionPhase.AUTHENTICATED
    assert broker.snapshot(a.id)["ticket"] is None
    lease.close()
