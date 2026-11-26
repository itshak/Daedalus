"""Offline reconciliation contracts; no game login, mutations, or live data."""
from __future__ import annotations

from types import SimpleNamespace

from daedalus.accounts import Account
from daedalus.recovery_reconcile import (
    construction_plan,
    convergent_transport_plan,
    restart_class_for,
)
from daedalus.recovery_runtime import RecoverySupervisor
from daedalus.recovery_state import RecoveryStore

ACCOUNT = Account("a", "s53-ru", "monjo", "Monjo", True)


def building(position=5, level=3, target=6, name="academy"):
    return {"position": position, "level": level, "upgradeTo": target,
            "building": name, "name": name}


def construction_config(*buildings):
    return {"city_id": 123, "city_name": "Town",
            "buildings": list(buildings), "shipments": [],
            "expand_overall": True, "wait_resources": False,
            "construction_queue": [360], "total_time": 360}


class ConstructionIPC:
    def __init__(self, *, busy=False, current=3, original="academy", ready=True):
        self.busy, self.current, self.original, self.ready = busy, current, original, ready
        self.planned = []
        self.previewed = 0

    def buildings(self, account, city_id):
        assert account == ACCOUNT and city_id == 123
        return [{"position": 5, "level": self.current, "building": self.original,
                 "busy": self.busy, "can_upgrade": True}]

    def construction_preview(self, account, city_id, upgrades):
        assert account == ACCOUNT and city_id == 123
        self.previewed += 1
        self.planned = upgrades
        fresh = construction_config(
            building(level=self.current, target=upgrades[0]["target_level"]),
        )
        return {"ready": self.ready, "config": fresh}


def test_construction_skips_completed_levels_and_builds_only_missing():
    ipc = ConstructionIPC(current=4)
    original = construction_config(building(level=3, target=6))
    assert restart_class_for("constructionList", original) == "reconcile_construction"
    plan = construction_plan(ipc, ACCOUNT, original)
    assert plan.state == "ready" and plan.config["buildings"][0]["level"] == 4
    assert ipc.planned == [{"position": 5, "target_level": 6}]


def test_construction_busy_defers_without_dispatching_again():
    ipc = ConstructionIPC(busy=True)
    plan = construction_plan(ipc, ACCOUNT, construction_config(building()))
    assert (plan.state, plan.reason) == ("deferred", "building_busy")
    assert ipc.previewed == 0


def test_finished_construction_is_marked_completed_without_restarting():
    ipc = ConstructionIPC(current=6)
    plan = construction_plan(ipc, ACCOUNT, construction_config(building()))
    assert plan.state == "completed"
    assert ipc.previewed == 0


def test_construction_changed_building_is_never_reused():
    ipc = ConstructionIPC(original="warehouse")
    plan = construction_plan(ipc, ACCOUNT, construction_config(building()))
    assert (plan.state, plan.reason) == ("review", "building_changed")


def test_construction_shortages_wait_for_game_resources():
    ipc = ConstructionIPC(ready=False)
    plan = construction_plan(ipc, ACCOUNT, construction_config(building()))
    assert (plan.state, plan.reason) == ("deferred", "resources_missing")


def test_construction_with_shipments_is_not_auto_replayed():
    config = construction_config(building())
    config["shipments"] = [{"from": 1, "to": 2, "resources": [50, 0, 0, 0, 0]}]
    assert restart_class_for("constructionList", config) == "manual"


def consolidate_config():
    return {"limits": [100, -1, 200, 0, -1],
            "sourceCityIds": [101, 102], "destinationCityId": 103,
            "intervalInHours": 1, "shipType": 1}


def manager_config():
    return {"mode": "consolidate", "send_mode": "keep",
            "resource_config": [100, None, 0, None, 10],
            "origin_cities": [101, 102], "destination_city": 103,
            "interval_hours": 2, "useFreighters": False, "notify": "none"}


def test_only_source_threshold_transport_restores():
    assert restart_class_for("consolidateResources", consolidate_config()) == "convergent_transport"
    assert restart_class_for("resourceTransportManager", manager_config()) == "convergent_transport"
    bad = manager_config()
    bad["send_mode"] = "send"
    assert restart_class_for("resourceTransportManager", bad) == "manual"
    bad = manager_config()
    bad["interval_hours"] = 0
    assert restart_class_for("resourceTransportManager", bad) == "manual"
    assert restart_class_for("sendResources", {"routes": []}) == "manual"
    assert restart_class_for("distributeResources", {"mode": "even"}) == "manual"


def test_transport_checks_owned_origins_before_restart():
    class IPC:
        def cities(self, account):
            assert account == ACCOUNT
            return [{"id": 101}, {"id": 102}, {"id": 103}]
    plan = convergent_transport_plan(IPC(), ACCOUNT, "consolidateResources", consolidate_config())
    assert plan.state == "ready"
    class Missing:
        def cities(self, account):
            return [{"id": 101}, {"id": 103}]
    missing = convergent_transport_plan(
        Missing(), ACCOUNT, "resourceTransportManager", manager_config()
    )
    assert missing.state == "review" and missing.reason == "source_city_changed"


def test_reconciler_starts_fresh_remaining_target_and_fences_receipt(tmp_path):
    ipc = ConstructionIPC(current=4)
    journal = RecoveryStore(tmp_path / "recovery.db")
    journal.set_policy(ACCOUNT, enabled=True, auto_resume=True)
    job = journal.capture_started(
        ACCOUNT, "constructionList", construction_config(building()),
        "old-task-id",
    )
    assert journal.desired(ACCOUNT)[0]["restart_class"] == "reconcile_construction"

    class Ledger:
        def has_unresolved(self, _account):
            return False

    class Controller:
        _ledger = Ledger()
        _ipc = ipc
        def __init__(self):
            self.started = []
        def list_tasks(self, _account):
            return {"engine_tasks": [
                {"task": row[0], "task_id": row[2], "status": "running"}
                for row in self.started
            ]}
        def start(self, account_id, task, config, request_id, *,
                  confirmed, track_desired):
            assert account_id == ACCOUNT.id and confirmed and not track_desired
            self.started.append((task, config, request_id))
            return {"status": "started", "task_id": request_id}

    controller = Controller()
    workers = SimpleNamespace(get=lambda _: None)
    supervisor = RecoverySupervisor(
        [ACCOUNT], journal, workers, controller,
        SimpleNamespace(available=lambda _: True),
    )
    journal.record_loss(ACCOUNT)
    attempt = journal.claim_due(ACCOUNT, force=True)
    journal.outcome(ACCOUNT, attempt["epoch"], success=True)
    epoch = attempt["epoch"]
    result = supervisor._resume_jobs(ACCOUNT, epoch)
    assert result["restored"] == 1
    assert len(controller.started) == 1
    assert controller.started[0][1]["buildings"][0]["level"] == 4
    assert journal.receipts(ACCOUNT)[0]["status"] == "started"
    assert supervisor._resume_jobs(ACCOUNT, epoch)["restored"] == 0
    assert len(controller.started) == 1
    assert journal.desired(ACCOUNT)[0]["id"] == job


def test_reconciler_can_complete_without_mutating_game(tmp_path):
    ipc = ConstructionIPC(current=6)
    journal = RecoveryStore(tmp_path / "recovery.db")
    journal.set_policy(ACCOUNT, enabled=True, auto_resume=True)
    journal.capture_started(ACCOUNT, "constructionList",
                            construction_config(building()), "old-id")
    class Controller:
        _ipc = ipc
        _ledger = SimpleNamespace(has_unresolved=lambda _: False)
        def list_tasks(self, _):
            return {"engine_tasks": []}
        def start(self, *args, **kwargs):
            raise AssertionError("Game operation is unnecessary")
    supervisor = RecoverySupervisor(
        [ACCOUNT], journal, SimpleNamespace(), Controller(),
        SimpleNamespace(),
    )
    journal.record_loss(ACCOUNT)
    attempt = journal.claim_due(ACCOUNT, force=True)
    journal.outcome(ACCOUNT, attempt["epoch"], success=True)
    epoch = attempt["epoch"]
    assert supervisor._resume_jobs(ACCOUNT, epoch)["completed"] == 1
    assert journal.desired(ACCOUNT)[0]["desired_state"] == "completed"
    assert supervisor._resume_jobs(ACCOUNT, epoch)["completed"] == 0

def test_even_a_reported_final_level_is_not_complete_while_busy():
    ipc = ConstructionIPC(current=6, busy=True)
    plan = construction_plan(ipc, ACCOUNT, construction_config(building()))
    assert plan.state == "deferred"
    assert ipc.previewed == 0


def test_reconciler_retries_deferred_construction_without_replaying_prior_dispatch(tmp_path):
    ipc = ConstructionIPC(current=3, busy=True)
    journal = RecoveryStore(tmp_path / "recover.db")
    journal.set_policy(ACCOUNT, enabled=True, auto_resume=True)
    journal.capture_started(ACCOUNT, "constructionList",
                            construction_config(building()), "initial")
    class Controller:
        _ipc = ipc
        _ledger = SimpleNamespace(has_unresolved=lambda _: False)
        def __init__(self):
            self.start_count = 0
        def list_tasks(self, _):
            return {"engine_tasks": [
                {"task": "constructionList", "task_id": "new", "status": "running"}
            ] if self.start_count else []}
        def start(self, _aid, _task, _cfg, _rid, *, confirmed, track_desired):
            self.start_count += 1
            return {"status": "started", "task_id": "new"}
    controller = Controller()
    worker = SimpleNamespace(
        alive=lambda: True,
        lease=SimpleNamespace(phase="authenticated"),
    )
    workers = SimpleNamespace(
        get=lambda _: worker,
        router=SimpleNamespace(validate_account=lambda _: True),
    )
    supervisor = RecoverySupervisor(
        [ACCOUNT], journal, workers, controller,
        SimpleNamespace(available=lambda _: True),
    )
    journal.record_loss(ACCOUNT)
    attempt = journal.claim_due(ACCOUNT, force=True)
    journal.outcome(ACCOUNT, attempt["epoch"], success=True)
    supervisor.tick()
    assert controller.start_count == 0
    assert journal.receipts(ACCOUNT) == []
    ipc.busy = False
    ipc.current = 4
    supervisor.tick()
    assert controller.start_count == 1
    assert journal.receipts(ACCOUNT)[0]["status"] == "started"
    supervisor.tick()
    assert controller.start_count == 1


def test_restart_class_cannot_be_unilaterally_overridden(tmp_path):
    import pytest

    from daedalus.recovery_state import RecoveryConflict

    store = RecoveryStore(tmp_path / "recover.db")
    with pytest.raises(RecoveryConflict, match="escalated"):
        store.capture_started(
            ACCOUNT, "sendResources", {"routes": []}, "old",
            restart_class="continuous",
        )

def test_external_recipient_cannot_be_auto_restored_even_if_source_is_owned():
    class IPC:
        def cities(self, account):
            return [{"id": 101}, {"id": 102}]

    config = manager_config()
    config["island"] = "201"
    assert restart_class_for("resourceTransportManager", config) == "manual"
    own_config = manager_config()
    result = convergent_transport_plan(
        IPC(), ACCOUNT, "resourceTransportManager", own_config,
    )
    assert (result.state, result.reason) == (
        "review", "destination_city_changed",
    )
