"""Offline recovery journal and grace-window regressions (never touch Gameforge)."""
import os
import sqlite3

import pytest

from daedalus.accounts import Account
from daedalus.recovery_state import RecoveryConflict, RecoveryStore


@pytest.fixture()
def item(tmp_path):
    now = [1000.0]
    account = Account(id="a", world="s53-ru", player="monjo", label="Monjo", enabled=True)
    store = RecoveryStore(tmp_path / "private" / "recovery.sqlite3", clock=lambda: now[0])
    return store, account, now


def enable(store, account):
    return store.set_policy(account, enabled=True, auto_resume=True)


def test_recovery_defaults_on_and_is_identity_scoped(item):
    store, account, _ = item
    initial = store.policy(account)
    assert initial["enabled"] is True
    assert initial["auto_resume"] is True
    assert initial["grace_seconds"] == 300
    assert initial["revision"] == 0
    result = enable(store, account)
    assert result["enabled"] and result["grace_seconds"] == 300
    different = Account(id="a", world="s53-ru", player="Other", label="Other", enabled=True)
    assert store.policy(different)["enabled"] is False
    assert store.event(different) is None

    unconfigured = Account(id="b", world="s53-ru", player="Other", label="Other", enabled=False)
    assert store.policy(unconfigured)["enabled"] is False
    assert store.policy(unconfigured)["auto_resume"] is False


def test_policy_revision_and_revoke(item):
    store, account, _ = item
    first = enable(store, account)
    with pytest.raises(RecoveryConflict, match="changed"):
        store.set_policy(account, enabled=False, auto_resume=False, expected_revision=0)
    assert store.set_policy(account, enabled=False, auto_resume=False,
                            expected_revision=first["revision"])["enabled"] is False
    with pytest.raises(RecoveryConflict):
        store.set_policy(account, enabled=False, auto_resume=True)


def test_five_minute_grace_from_confirmed_loss_not_a_generic_timer(item):
    store, account, now = item
    event = store.record_loss(account)
    assert store.policy(account)["enabled"] is True
    assert event["due_at"] == 1300
    now[0] = 1299
    assert store.record_loss(account)["epoch"] == event["epoch"]
    assert store.claim_due(account) is None
    now[0] = 1300
    started = store.claim_due(account)
    assert started["phase"] == "attempting" and started["attempts"] == 1
    assert store.claim_due(account) is None
    store.outcome(account, started["epoch"], success=True)
    assert store.event(account)["phase"] == "restored"


def test_browser_pause_and_early_resume(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    store.pause(account, seconds=None)
    now[0] = 1400
    assert store.claim_due(account) is None
    store.unpause(account)
    assert store.claim_due(account, force=True)["phase"] == "attempting"


def test_timed_pause_survives_restart(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    store.pause(account, seconds=900)
    now[0] = 1400
    store.protect_after_restart([account])
    assert store.event(account)["due_at"] >= 1700
    assert store.claim_due(account) is None
    now[0] = 2000
    assert store.claim_due(account) is not None


def test_server_restart_cannot_shorten_grace(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    now[0] = 1200
    store.protect_after_restart([account])
    assert store.event(account)["due_at"] == 1500
    now[0] = 1499
    assert store.claim_due(account) is None
    now[0] = 1500
    assert store.claim_due(account)["phase"] == "attempting"


def test_bounded_retry_and_invalid_credential_stops(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    now[0] = 1300
    first = store.claim_due(account)
    store.outcome(account, first["epoch"], success=False, reason="network_error")
    assert store.event(account)["due_at"] == 1600
    assert store.claim_due(account) is None
    now[0] = 1600
    second = store.claim_due(account)
    assert second["attempts"] == 2
    store.outcome(account, second["epoch"], success=False, reason="challenge_required")
    assert store.event(account)["phase"] == "failed"
    assert store.claim_due(account) is None


def test_persisted_private_store_and_reopening(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    reopened = RecoveryStore(store.path, clock=lambda: now[0])
    assert reopened.policy(account)["enabled"]
    assert reopened.event(account)["due_at"] == 1300
    if os.name == "posix":
        assert store.path.stat().st_mode & 0o077 == 0
        assert store.path.parent.stat().st_mode & 0o077 == 0


def test_capture_running_configs_not_only_hashes_and_stop(item):
    store, account, _ = item
    job_id = store.capture_started(account, "alertAttacks", {"notify": True}, "faketaskid")
    jobs = store.desired(account, include_config=True)
    assert jobs == [{
        "id": job_id, "task": "alertAttacks", "digest": jobs[0]["digest"],
        "restart_class": "continuous", "desired_state": "running",
        "revision": 1, "last_task_id": "faketaskid", "config": {"notify": True},
    }]
    assert store.stop_task(account, "faketaskid") == 1
    assert store.desired(account)[0]["desired_state"] == "stopped"


def test_nonrestartable_jobs_never_get_auto_resume_receipt(item):
    store, account, _ = item
    manual = store.capture_started(account, "sendResources", {"city": 42}, "task-a")
    assert store.desired(account)[0]["restart_class"] == "manual"
    assert store.begin_resume(account, manual, "epoch") is None


def test_new_epoch_single_atomic_receipt_and_revision_fence(item):
    store, account, _ = item
    job = store.capture_started(account, "alertAttacks", {"notify": True}, "task-1")
    first = store.begin_resume(account, job, "new-epoch")
    assert first and first["request_id"] != "task-1"
    assert first["config"] == {"notify": True}
    assert store.begin_resume(account, job, "new-epoch") is None
    store.stop_task(account, "task-1")
    store.finish_resume(account, job, "new-epoch", status="started",
                        task_id="task-2", revision=first["revision"])
    assert store.desired(account)[0]["desired_state"] == "stopped"
    assert store.receipts(account)[0]["status"] == "started"


def test_unknown_outcome_is_not_replayed(item):
    store, account, _ = item
    job = store.capture_started(account, "alertAttacks", {}, "old")
    assert store.begin_resume(account, job, "ep") is not None
    store.finish_resume(account, job, "ep", status="unconfirmed")
    assert store.begin_resume(account, job, "ep") is None
    assert store.receipts(account)[0]["status"] == "unconfirmed"


def test_secret_field_in_job_config_rejected(item):
    store, account, _ = item
    for key in ("password", "gf_token", "cookie", "session"):
        with pytest.raises(ValueError):
            store.capture_started(account, "alertAttacks", {key: "secret"}, "task")


def test_config_tables_have_no_lobby_secrets(item):
    store, account, _ = item
    enable(store, account)
    store.capture_started(account, "alertAttacks", {"city": 123}, "fake")
    with sqlite3.connect(store.path) as conn:
        cols={row[1] for table in ("policies","events","desired_jobs","resume_receipts")
              for row in conn.execute(f"PRAGMA table_info({table})")}
    assert {"password", "token", "cookie", "gf_token"} & cols == set()

def test_exact_schema_version_and_incompatible_newer_schema_fails_closed(item):
    store, _account, _ = item
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        conn.execute("PRAGMA user_version=9")
    with pytest.raises(RecoveryConflict, match="newer Daedalus"):
        RecoveryStore(store.path)


def test_hourly_attempt_limit_survives_new_loss_epochs_and_process_restart(item):
    store, account, now = item
    enable(store, account)
    for index in range(3):
        store.record_loss(account)
        current = store.claim_due(account, force=True)
        assert current is not None
        store.outcome(account, current["epoch"], success=True)
        now[0] += 10
    store = RecoveryStore(store.path, clock=lambda: now[0])
    store.record_loss(account)
    assert store.claim_due(account, force=True) is None
    assert store.event(account)["phase"] == "failed"
    assert store.event(account)["last_reason"] == "rate_limited"


def test_user_can_disable_during_grace_and_no_attempts_are_started(item):
    store, account, now = item
    enable(store, account)
    store.record_loss(account)
    store.set_policy(account, enabled=False, auto_resume=False)
    now[0] = 2000
    assert store.event(account) is None
    assert store.claim_due(account) is None


def test_explicit_disable_survives_restart_even_though_default_is_on(item):
    store, account, now = item
    assert store.policy(account)["enabled"] is True
    store.pause(account, seconds=None)
    assert store.policy(account)["pause_indefinite"] is True
    reopened = RecoveryStore(store.path, clock=lambda: now[0])
    assert reopened.policy(account)["pause_indefinite"] is True
    reopened.set_policy(account, enabled=False, auto_resume=False)
    after_restart = RecoveryStore(store.path, clock=lambda: now[0])
    assert after_restart.policy(account)["enabled"] is False
    assert after_restart.policy(account)["auto_resume"] is False
    assert after_restart.record_loss(account) is None
