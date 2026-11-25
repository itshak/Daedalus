"""Single-authority, opt-in host recovery and safe task reconciliation.

Live Gameforge operations are delegated exclusively to maintained IkaBot,
isolated in account-specific process groups and protected IPC endpoints. The
controller never reimplements game HTTP or shares credentials with a browser.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    SessionBusyError,
    SessionPhase,
)
from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.recovery_credentials import (
    RecoveryCredentials,
    RecoveryCredentialsUnavailable,
)
from daedalus.recovery_reconcile import (
    construction_plan,
    convergent_transport_plan,
    fixed_transfer_plan,
)
from daedalus.recovery_state import RecoveryStore, identity
from daedalus.task_control import TaskController, TaskUnavailable

logger = logging.getLogger("daedalus.recovery_runtime")

_ACCOUNT_METHODS = frozenset({
    "has_account", "validate_account", "cities", "buildings",
    "construction_preview", "workshop_upgrades", "trainable_units",
    "vacation_preview", "attack_inventory", "attack_preview", "grind_preview",
    "station_preview", "build_options", "build_preview", "layout_preview",
    "worker_preview", "donation_preview", "island_destinations", "shipment_preview", "native_reward_distribution_preview", "recurring_preview", "fill_preview",
    "market_quotes", "academies", "taverns", "miracles",
    "shrine_status", "pirate_fortresses", "military_overview", "administrative_status",
    "ship_movements", "warehouses", "preflight_task",
    "notification_settings_begin", "notification_settings_complete", "extension_settings", "challenge_policy", "world_reports", "proxy_profiles",
    "start_managed_task", "list_managed_tasks", "stop_managed_task",
})


class RoutedAccountIPC:
    """Route a validated account to its own worker IPC; preserve legacy IPC."""

    def __init__(self, fallback: ControlledIPCClient | None = None) -> None:
        self.fallback = fallback or ControlledIPCClient()
        self._active: dict[str, ControlledIPCClient] = {}
        self._mutex = threading.RLock()

    def use(self, account_id: str, descriptor: Path) -> None:
        with self._mutex:
            self._active[account_id] = ControlledIPCClient(descriptor)

    def drop(self, account_id: str) -> None:
        with self._mutex:
            self._active.pop(account_id, None)

    def _client(self, account: Account) -> ControlledIPCClient:
        with self._mutex:
            return self._active.get(account.id, self.fallback)

    def list_sessions(self):
        with self._mutex:
            clients = tuple(self._active.values())
        rows = []
        try:
            rows.extend(self.fallback.list_sessions())
        except (EngineIPCUnavailable, ValueError, OSError):
            pass
        for client in clients:
            try:
                rows.extend(client.list_sessions())
            except (EngineIPCUnavailable, ValueError, OSError):
                continue
        return rows

    def __getattr__(self, name: str):
        if name not in _ACCOUNT_METHODS:
            raise AttributeError(name)

        def invoke(account: Account, *args, **kwargs):
            return getattr(self._client(account), name)(account, *args, **kwargs)
        return invoke


class RecoveryWorkerError(RuntimeError):
    """A sanitized recovery failure; no secret material is exposed."""


class ManagedAccountWorker:
    """The daemon owns the lease, while IkaBot runs in a killable process group."""

    def __init__(self, account: Account, descriptor: Path, process: subprocess.Popen,
                 lease, router: RoutedAccountIPC):
        self.account = account
        self.descriptor = descriptor
        self.process = process
        self.lease = lease
        self.router = router

    def alive(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> None:
        self.router.drop(self.account.id)
        # Stop all Gameforge task descendants, not merely the IkaBot parent.
        if os.name == "posix":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif self.process.poll() is None:
            self.process.kill()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise RecoveryWorkerError("Recovery worker cleanup is uncertain") from exc
        self.descriptor.unlink(missing_ok=True)


class RecoveryWorkers:
    def __init__(self, owner: AccountSessionCoordinator,
                 controller: TaskController, router: RoutedAccountIPC,
                 credentials: RecoveryCredentials, broker=None,
                 *, launch_timeout: float = 35.0) -> None:
        self.owner = owner
        self.controller = controller
        self.router = router
        self.credentials = credentials
        self.broker = broker
        self.launch_timeout = launch_timeout
        self._workers: dict[str, ManagedAccountWorker] = {}
        self._mutex = threading.RLock()

    def get(self, account: Account) -> ManagedAccountWorker | None:
        with self._mutex:
            return self._workers.get(account.id)

    @staticmethod
    def _descriptor(account: Account) -> Path:
        root = Path.home() / ".local" / "state" / "daedalus" / "account-ipc"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink():
            raise RecoveryWorkerError("Unsafe private IPC directory")
        if os.name == "posix":
            os.chmod(root, 0o700)
        return root / f"{identity(account)}.json"

    def _promote(self, account: Account, lease) -> None:
        """Promote ONLY after a current authenticated IPC/world/player probe."""
        if lease.phase != SessionPhase.AUTHENTICATED:
            if self.broker is not None:
                self.broker.verified_auto_reconnect(lease, confirmed=True)
            else:
                if lease.phase not in (SessionPhase.PAUSED, SessionPhase.FAILED):
                    lease.transition(SessionPhase.PAUSED)
                lease.transition(SessionPhase.VALIDATING_SESSION)
                lease.transition(SessionPhase.AUTHENTICATED)
        if account.id not in self.controller._owned:
            self.controller.adopt_verified_saved_worker(account.id, lease)

    def start(self, account: Account) -> ManagedAccountWorker:
        """Bounded, one-account trusted refresh; caller serializes login attempts."""
        with self._mutex:
            prior = self._workers.get(account.id)
            if prior is not None:
                prior.stop()
                # Remove old process entry BEFORE launching the replacement.
                # A failed new launch must not be mistaken for a live worker.
                del self._workers[account.id]
                # Keep the same account lease through replacement.
            if prior is not None:
                lease = prior.lease
            else:
                if self.owner.status(account.id) != "not_connected":
                    raise RecoveryWorkerError("Another session already owns this account")
                # Existing global IkaBot owner for this exact player must not
                # be silently overtaken by an account-scoped auto worker.
                try:
                    if self.router.fallback.has_account(account):
                        raise RecoveryWorkerError("A separate IkaBot owner is already running")
                except EngineIPCUnavailable:
                    pass
                lease = self.owner.acquire(account.id)

            child = None
            descriptor = self._descriptor(account)
            try:
                email, token = self.credentials.retrieve(account)
                if descriptor.exists():
                    # Never overwrite a still-live separate IPC owner.
                    stale = ControlledIPCClient(descriptor)
                    try:
                        if stale.has_account(account):
                            raise RecoveryWorkerError("Existing account IPC owner is still running")
                    except EngineIPCUnavailable:
                        pass
                    descriptor.unlink()
                env = os.environ.copy()
                env["DAEDALUS_ACCOUNT_IPC_FILE"] = str(descriptor)
                child = subprocess.Popen(
                    [sys.executable, "-m", "daedalus.recovery_child"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, env=env,
                    start_new_session=(os.name=="posix"),
                )
                assert child.stdin is not None
                request={"id":account.id,"world":account.world,"player":account.player,
                         "email":email,"lobby_token":token}
                child.stdin.write(json.dumps(request,separators=(",",":")).encode()+b"\n")
                child.stdin.close()
                # Wait for the actual protected IkaBot IPC and independent
                # read-only world player validation; a PID alone is not proof.
                deadline=time.monotonic()+self.launch_timeout
                candidate=ControlledIPCClient(descriptor)
                while time.monotonic()<deadline:
                    if child.poll() is not None:
                        break
                    if descriptor.exists():
                        try:
                            if candidate.validate_account(account):
                                self.router.use(account.id,descriptor)
                                self._promote(account,lease)
                                worker=ManagedAccountWorker(account,descriptor,child,lease,self.router)
                                self._workers[account.id]=worker
                                logger.info("Verified isolated recovered worker for account ID %s",account.id)
                                return worker
                        except (EngineIPCUnavailable,ValueError,OSError):
                            pass
                    time.sleep(.2)
                raise RecoveryWorkerError("Trusted IkaBot account refresh unavailable or unverified")
            except (RecoveryCredentialsUnavailable, SessionBusyError) as exc:
                raise RecoveryWorkerError("Protected login unavailable or owner busy") from exc
            except Exception as exc:
                if isinstance(exc,RecoveryWorkerError):
                    raise
                raise RecoveryWorkerError("Isolated Gameforge login could not be verified") from exc
            finally:
                new_worker=self._workers.get(account.id)
                if child is not None and (
                    new_worker is None or new_worker.process is not child
                ):
                    ManagedAccountWorker(account,descriptor,child,lease,self.router).stop()
                if new_worker is None:
                    if prior is not None:
                        # Preserve stopped old owner/lease for a later retry;
                        # never allow a second process to acquire this identity.
                        self._workers[account.id]=prior
                    elif lease is not None:
                        lease.close()

    def close(self) -> None:
        with self._mutex:
            for item in tuple(self._workers.values()):
                try:
                    item.stop()
                except (OSError,RecoveryWorkerError):
                    logger.warning("Account worker shutdown could not be verified")
                else:
                    item.lease.close()
            self._workers.clear()


class RecoverySupervisor:
    """Process-wide single login lane, with opt-in and private durable timing."""

    def __init__(self, accounts: list[Account], store: RecoveryStore,
                 workers: RecoveryWorkers, controller: TaskController,
                 credentials: RecoveryCredentials, *,
                 clock=None, poll_seconds: float = 30.0):
        self.accounts={a.id:a for a in accounts}
        self.store=store
        self.workers=workers
        self.controller=controller
        self.credentials=credentials
        self._clock=clock or time.time
        self.poll_seconds=poll_seconds
        self._stop=threading.Event()
        self._wake=threading.Event()
        self._thread: threading.Thread | None=None
        self._suspected: dict[str,float]={}
        self._force: set[str]=set()
        self._mutex=threading.RLock()

    def start(self) -> None:
        self.store.protect_after_restart(list(self.accounts.values()))
        # Only accounts PREVIOUSLY verified as recovered may be scheduled
        # after an API restart. New policies with no prior login do nothing.
        for account in self.accounts.values():
            event=self.store.event(account)
            if (event and event["phase"]=="restored" and
                    self.store.policy(account)["enabled"] and
                    self.workers.get(account) is None):
                self.store.record_loss(account)
        with self._mutex:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread=threading.Thread(target=self._loop,daemon=True,
                                          name="daedalus-auto-recovery")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread=None
        self.workers.close()

    def request_now(self, account: Account) -> dict[str,str]:
        """Queue a single forced attempt; HTTP never waits on game networking."""
        if account.id not in self.accounts or self.accounts[account.id]!=account:
            raise RecoveryWorkerError("Unknown configured recovery account")
        if not self.store.policy(account)["enabled"]:
            raise RecoveryWorkerError("Automatic recovery is not enabled")
        if self.workers.get(account) is not None and self.workers.get(account).alive():
            raise RecoveryWorkerError("Account worker is already running")
        self.store.reset_failed_for_manual_retry(account)
        self.store.record_loss(account)
        self.store.unpause(account)
        with self._mutex:
            self._force.add(account.id)
        self._wake.set()
        return {"account_id":account.id,"status":"queued"}

    def _observe(self, account: Account) -> None:
        worker=self.workers.get(account)
        if worker is None:
            # Existing sessions attached through the previous task controller
            # can still be observed safely, without claiming a second owner.
            existing=next((lease for lease in self.controller.owned_sessions()
                           if lease.account==account),None)
            if (existing is None or existing.phase not in (
                SessionPhase.AUTHENTICATED,SessionPhase.NEEDS_ASSISTANCE)):
                return
        else:
            existing=worker.lease
        # A dead managed worker is definitive loss, not a transient timeout.
        if worker is not None and not worker.alive():
            if existing.phase is SessionPhase.AUTHENTICATED:
                existing.transition(SessionPhase.NEEDS_ASSISTANCE)
            self.store.record_loss(account)
            return
        try:
            valid=self.workers.router.validate_account(account)
        except (EngineIPCUnavailable,ValueError,OSError):
            valid=False
        if valid:
            self._suspected.pop(account.id,None)
            return
        now=self._clock()
        first=self._suspected.setdefault(account.id,now)
        if now-first >= 10:
            self.store.record_loss(account)
            # Block the old game's child tasks as soon as loss is confirmed.
            # The owner lease is intentionally held through grace/recovery.
            if worker is not None:
                worker.stop()
            if existing.phase is SessionPhase.AUTHENTICATED:
                existing.transition(SessionPhase.NEEDS_ASSISTANCE)
            self._suspected.pop(account.id,None)

    def _resume_jobs(self, account: Account, epoch: str) -> dict[str,int]:
        totals={"restored":0,"completed":0,"skipped":0,"unconfirmed":0}
        policy=self.store.policy(account)
        if not policy["auto_resume"]:
            return totals
        if self.controller._ledger.has_unresolved(account.id):
            totals["skipped"]=len(self.store.desired(account))
            return totals
        try:
            running=self.controller.list_tasks(account.id)["engine_tasks"]
        except (EngineIPCUnavailable,TaskUnavailable,ValueError,OSError):
            totals["skipped"]=len(self.store.desired(account))
            return totals
        active={str(row["task"]) for row in running
                if row.get("status") in ("running","stopping")}
        jobs=self.store.desired(account,include_config=True)
        for job in jobs:
            if job["desired_state"]!="running":
                continue
            if job["restart_class"] not in (
                    "continuous", "reconcile_construction", "convergent_transport",
                    "fixed_transfer"
                ) or job["task"] in active:
                totals["skipped"]+=1
                continue
            # Two identical task types with different configs are ambiguous
            # because the current engine's task listing omits config hashes.
            if sum(j["task"]==job["task"] and j["desired_state"]=="running"
                   for j in jobs)>1:
                totals["skipped"]+=1
                continue
            resume_config=job["config"]
            if job["restart_class"] in (
                "reconcile_construction", "convergent_transport", "fixed_transfer"
            ):
                try:
                    if job["restart_class"]=="reconcile_construction":
                        plan=construction_plan(self.controller._ipc,account,resume_config)
                    elif job["restart_class"]=="fixed_transfer":
                        plan=fixed_transfer_plan(
                            self.store,self.controller._ipc,account,resume_config,
                        )
                    else:
                        plan=convergent_transport_plan(
                            self.controller._ipc,account,job["task"],resume_config,
                        )
                except (EngineIPCUnavailable,TaskUnavailable,ValueError,OSError):
                    # Cannot prove the remaining operations: retry only a
                    # read-only preflight in a future healthy supervisor tick.
                    totals["skipped"]+=1
                    continue
                if plan.state=="completed":
                    if self.store.complete_job(
                        account,job["id"],revision=job["revision"],
                    ):
                        totals["completed"]+=1
                    else:
                        totals["skipped"]+=1
                    continue
                if plan.state!="ready" or plan.config is None:
                    totals["skipped"]+=1
                    continue
                resume_config=plan.config
            prepared=self.store.begin_resume(account,job["id"],epoch)
            if prepared is None:
                totals["skipped"]+=1
                continue
            # Recheck a possible user stop after reserving the durable
            # receipt; a recovery racing a policy change cannot revive a job.
            latest=next((row for row in self.store.desired(account)
                        if row["id"]==job["id"]),None)
            if (latest is None or latest["desired_state"]!="running"
                    or latest["revision"]!=prepared["revision"]):
                self.store.finish_resume(
                    account,job["id"],epoch,status="skipped",
                )
                totals["skipped"]+=1
                continue
            try:
                result=self.controller.start(
                    account.id,prepared["task"],resume_config,
                    prepared["request_id"],confirmed=True,track_desired=False,
                )
                if result.get("status")!="started":
                    raise TaskUnavailable("No fresh engine start receipt")
                live=self.controller.list_tasks(account.id)["engine_tasks"]
                if not any(x.get("task_id")==result["task_id"] and
                           x.get("status")=="running" for x in live):
                    raise TaskUnavailable("New task is not verified as running")
                latest=next((row for row in self.store.desired(account)
                            if row["id"]==job["id"]),None)
                if (latest is None or latest["desired_state"]!="running"
                        or latest["revision"]!=prepared["revision"]):
                    # User requested stop while IPC was in flight. Stop the
                    # newly started task; never label it as desired-running.
                    self.controller.stop(account.id,result["task_id"])
                    self.store.finish_resume(
                        account,job["id"],epoch,status="skipped",
                    )
                    totals["skipped"]+=1
                    continue
                self.store.finish_resume(
                    account,job["id"],epoch,status="started",
                    task_id=result["task_id"],revision=prepared["revision"],
                )
                active.add(job["task"])
                totals["restored"]+=1
            except Exception:  # noqa: BLE001 - sanitized boundary or independent recovery loop
                # A lost IPC response may already have launched the task.
                # Stop the account's entire reconciliation, never retry it.
                self.store.finish_resume(account,job["id"],epoch,status="unconfirmed")
                totals["unconfirmed"]+=1
                break
        return totals

    def tick(self) -> None:
        """One bounded reconciliation cycle; called only in backend thread/tests."""
        for account in self.accounts.values():
            if not self.store.policy(account)["enabled"]:
                continue
            self._observe(account)
        for account in self.accounts.values():
            if self._stop.is_set():
                break
            with self._mutex:
                force=account.id in self._force
                self._force.discard(account.id)
            attempt=self.store.claim_due(account,force=force)
            if attempt is None:
                continue
            if not self.credentials.available(account):
                self.store.outcome(account,attempt["epoch"],
                                   success=False,reason="token_unavailable")
                continue
            try:
                self.workers.start(account)
                self.store.outcome(account,attempt["epoch"],success=True)
                self._resume_jobs(account,attempt["epoch"])
            except RecoveryWorkerError:
                self.store.outcome(account,attempt["epoch"],
                                   success=False,reason="needs_assistance")
        # Building work may already be queued in-game, or resources may be
        # missing during the first fresh read. Re-check only after a verified
        # worker is live. No dispatch receipt exists until a plan is ready.
        for account in self.accounts.values():
            policy=self.store.policy(account)
            event=self.store.event(account)
            worker=self.workers.get(account)
            if (self._stop.is_set() or not policy["enabled"]
                    or not policy["auto_resume"] or not event
                    or event["phase"]!="restored" or worker is None
                    or not worker.alive()):
                continue
            self._resume_jobs(account,event["epoch"])

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - sanitized boundary or independent recovery loop
                logger.warning("One recovery cycle failed safely; retry will remain bounded")
            self._wake.wait(self.poll_seconds)
            self._wake.clear()
