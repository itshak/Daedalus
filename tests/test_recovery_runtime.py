"""Synthetic, no-network session loss, cooldown, and fenced resume tests."""
from __future__ import annotations

import os
from pathlib import Path
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
    assert tuple(Path(get_ipc_file_path()).parts[-2:]) == (".ikabot", "ipc.json")
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


def test_inconclusive_ipc_errors_never_trigger_recovery(system):
    from daedalus.engine_ipc import EngineIPCUnavailable

    a,j,_c,w,_ctl,s,t=system
    w.running=SimpleNamespace(alive=lambda:True, lease=SimpleNamespace(phase=SessionPhase.AUTHENTICATED))
    def unavailable(_):
        raise EngineIPCUnavailable("synthetic transient timeout")
    w.router=SimpleNamespace(validate_account=unavailable)
    for _ in range(4):
        s.tick()
        t[0]+=40
    assert j.event(a) is None
    assert not w.starts
    # A negative observation separated by a transport error must not be enough.
    def probe(_):
        return False
    w.router.validate_account=probe
    s.tick()
    t[0]+=40
    w.router.validate_account=unavailable
    s.tick()
    t[0]+=40
    w.router.validate_account=probe
    s.tick()
    assert j.event(a) is None


def test_revoked_during_worker_start_does_not_restore_job(system):
    a,j,_c,w,ctl,s,t=system
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    original=w.start
    def revoke(account):
        original(account)
        j.set_policy(account,enabled=False,auto_resume=False)
    w.start=revoke
    j.record_loss(a)
    t[0]+=300
    s.tick()
    assert w.starts==[a.id]
    assert ctl.started==[] and j.event(a) is None


def test_simultaneous_account_loss_serialized_and_failed_account_isolated(system):
    a,j,c,w,ctl,_s,t=system
    b=Account("account-b","s53-ru","Other synthetic player","Other",True)
    supervisor=RecoverySupervisor([a,b],j,w,ctl,c,clock=lambda:t[0])
    j.record_loss(a);j.record_loss(b)
    original=w.start
    def start(account):
        original(account)
        if account.id==a.id:
            raise RecoveryWorkerError("synthetic worker failure")
    w.start=start
    t[0]+=300
    supervisor.tick()
    assert w.starts==[a.id,b.id]
    assert j.event(a)["phase"]=="failed" and j.event(b)["phase"]=="restored"


def test_stopped_job_during_grace_is_not_restored(system):
    a,j,_c,w,ctl,s,t=system
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    j.record_loss(a)
    assert j.stop_task(a,"old")==1
    t[0]+=300
    s.tick()
    assert w.starts==[a.id] and ctl.started==[] and j.receipts(a)==[]


def test_dead_worker_is_definitive_loss_even_without_ipc_probe(system):
    a,j,_c,w,_ctl,s,t=system
    class Lease:
        phase=SessionPhase.AUTHENTICATED
        def transition(self,phase):self.phase=phase
    w.running=SimpleNamespace(alive=lambda:False,lease=Lease())
    s.tick()
    assert j.event(a)["due_at"]==t[0]+300
    assert w.running.lease.phase==SessionPhase.NEEDS_ASSISTANCE
    assert w.starts==[]


def test_restart_with_zero_workers_only_recovers_previously_verified_account(system, monkeypatch):
    a,j,c,w,ctl,s,t=system
    other=Account("account-b", "s53-ru", "Other synthetic player", "Other", True)
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    j.record_loss(a)
    attempt=j.claim_due(a,force=True)
    j.outcome(a,attempt["epoch"],success=True)
    reopened=RecoveryStore(j.path,clock=lambda:t[0])
    s=RecoverySupervisor([a,other],reopened,w,ctl,c,clock=lambda:t[0])
    # Exercise startup reconciliation without an uncontrolled background thread.
    class DormantThread:
        def __init__(self,**_):pass
        def start(self):pass
    monkeypatch.setattr("daedalus.recovery_runtime.threading.Thread",DormantThread)
    s.start()
    assert reopened.event(a)["phase"]=="grace"
    assert reopened.event(a)["due_at"]==t[0]+300
    assert reopened.event(other) is None
    t[0]+=299
    s.tick()
    assert w.starts==[]
    t[0]+=1
    s.tick()
    assert w.starts==[a.id]
    assert len(ctl.started)==1


def test_identity_change_during_grace_never_starts_replacement_player(system):
    a,j,c,w,ctl,s,t=system
    j.capture_started(a,"alertAttacks",{"listen":True},"old")
    j.record_loss(a)
    replacement=Account(a.id,a.world,"Other synthetic player",a.label,True)
    s=RecoverySupervisor([replacement],j,w,ctl,c,clock=lambda:t[0])
    t[0]+=300
    s.tick()
    assert not w.starts and not ctl.started
    assert j.event(replacement) is None
    assert not j.desired(replacement)


@pytest.mark.parametrize("uncertain", [False, True])
def test_warehouse_cold_start_requires_durable_safe_receipt(system, monkeypatch, uncertain):
    from uuid import uuid4

    a,j,_c,w,ctl,s,t=system
    cfg={"destination_city":103,"resource":"marble","useFreighters":False,
         "reviewed_sources":[{"city_id":101,"amount":100}],
         "transfer_id":str(uuid4())}
    j.prepare_fixed_transfer(a,cfg,task="fillCityWarehouse")
    j.finish_fixed_transfer(a,cfg["transfer_id"],
                            status="unconfirmed" if uncertain else "started",
                            task_id=None if uncertain else "old")
    # No earlier recovery epoch or prior reconnect.
    assert j.event(a) is None

    class DormantThread:
        def __init__(self,**_):pass
        def start(self):pass

    monkeypatch.setattr("daedalus.recovery_runtime.threading.Thread",DormantThread)
    s.start()
    if uncertain:
        assert j.event(a) is None
        return
    assert j.event(a)["phase"]=="grace"
    assert j.event(a)["due_at"]==t[0]+300
    monkeypatch.setattr("daedalus.recovery_runtime.warehouse_fill_plan",
                        lambda *_:SimpleNamespace(state="ready",reason="warehouse_remaining",config=cfg))
    ctl._ipc=object()
    def start(aid,task,config,request_id,*,confirmed,track_desired):
        assert aid==a.id and task=="fillCityWarehouse" and config==cfg
        assert confirmed and not track_desired and request_id
        ctl.started.append({"task":task,"task_id":"warehouse-restored"})
        return {"status":"started","task_id":"warehouse-restored"}
    ctl.start=start
    t[0]+=299
    s.tick()
    assert not w.starts
    t[0]+=1
    s.tick()
    assert w.starts==[a.id]
    assert len(ctl.started)==1
    s.tick()
    assert len(ctl.started)==1


def test_uncertain_warehouse_fences_other_automatic_transport_but_not_alerts(system, monkeypatch):
    import json
    from uuid import uuid4

    a,j,_c,_w,ctl,s,t=system
    cfg={"destination_city":103,"resource":"marble","useFreighters":False,
         "reviewed_sources":[{"city_id":101,"amount":100}],
         "transfer_id":str(uuid4())}
    j.prepare_fixed_transfer(a,cfg,task="fillCityWarehouse")
    j.finish_fixed_transfer(a,cfg["transfer_id"],status="started",task_id="old")
    with j._db() as conn:
        conn.execute("""INSERT INTO fixed_transfer_chunks
            (transfer_id,route_index,cargo_json,status,updated_at) VALUES(?,?,?,'pending',?)""",
            (cfg["transfer_id"],0,json.dumps([0,0,40,0,0]),t[0]))
    j.capture_started(a,"consolidateResources",{
        "limits":[100]*5,"sourceCityIds":[101],"destinationCityId":103,
        "intervalInHours":1,"shipType":1},"old-transport")
    j.capture_started(a,"alertAttacks",{"listen":True},"old-alert")
    assert any(x["restart_class"]=="convergent_transport" for x in j.desired(a))
    def unsafe_preview(*_):
        pytest.fail("Uncertain cargo must fence automatic transport before planning")
    monkeypatch.setattr("daedalus.recovery_runtime.convergent_transport_plan",unsafe_preview)
    monkeypatch.setattr("daedalus.recovery_runtime.warehouse_fill_plan",unsafe_preview)
    j.record_loss(a)
    t[0]+=300
    s.tick()
    assert [r["task"] for r in ctl.started]==["alertAttacks"]
    assert j.summary(a)["manual_review"]==1


def test_fast_warehouse_completion_does_not_race_restoration_receipt(system, monkeypatch):
    from uuid import uuid4

    a,j,_c,_w,ctl,s,t=system
    cfg={"destination_city":103,"resource":"marble","useFreighters":False,
         "reviewed_sources":[{"city_id":101,"amount":100}],
         "transfer_id":str(uuid4())}
    j.prepare_fixed_transfer(a,cfg,task="fillCityWarehouse")
    j.finish_fixed_transfer(a,cfg["transfer_id"],status="started",task_id="old")
    monkeypatch.setattr("daedalus.recovery_runtime.warehouse_fill_plan",
                        lambda *_:SimpleNamespace(state="ready",reason="warehouse_remaining",config=cfg))
    ctl._ipc=object()
    def start(*_a, **_kw):
        # Fresh engine guard observes no destination capacity before the
        # new task is listed. No game cargo was submitted.
        with j._db() as conn:
            conn.execute("UPDATE fixed_transfers SET status='capacity_reached' WHERE transfer_id=?",
                         (cfg["transfer_id"],))
        return {"status":"started","task_id":"fast-warehouse"}
    def list_tasks(_):
        j.settle_warehouse_jobs(a)
        return {"engine_tasks":[]}
    ctl.start=start
    ctl.list_tasks=list_tasks
    ctl.stop=lambda *_:pytest.fail("A completed warehouse job is not a user stop")
    j.record_loss(a)
    t[0]+=300
    s.tick()
    row=j.desired(a)[0]
    assert row["desired_state"]=="completed"
    assert row["last_task_id"]=="fast-warehouse"
    assert j.warehouse_reason(a,row["id"],row["revision"])=="warehouse_capacity_reached"
    assert j.receipts(a)[0]["status"]=="started"
    s.tick()
    assert len(j.receipts(a))==1
