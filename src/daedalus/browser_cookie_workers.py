"""Supervised cookie-only world workers for explicit native Mac sign-in.

The HTTPS browser handoff verifies and seals the cookie first. A subsequent
host-local worker, launched without passwords or lobby tokens, independently
validates the same account before its private IPC endpoint becomes usable.
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import sys
import threading
import time

from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError, SessionPhase
from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.recovery_runtime import (
    ManagedAccountWorker,
    RecoveryWorkerError,
    RecoveryWorkers,
    RoutedAccountIPC,
)

logger = logging.getLogger("daedalus.browser_cookie_workers")
_WORLD = re.compile(r"s[0-9]{1,6}-[a-z]{2,4}\\Z")
_UPSTREAM_UNREACHABLE = (
    "Game world is unreachable from the Daedalus server; "
    "saved sessions will retry when connectivity recovers"
)


class BrowserCookieWorkers:
    """One leased IkaBot process per exact configured account; no task replay."""

    def __init__(self, owner: AccountSessionCoordinator, router: RoutedAccountIPC,
                 *, launch_timeout: float = 35.0) -> None:
        self.owner = owner
        self.router = router
        self.launch_timeout = launch_timeout
        self._workers: dict[str, ManagedAccountWorker] = {}
        self._mutex = threading.RLock()
        self._connectivity: dict[str, tuple[float, bool]] = {}
        self._retry_stop = threading.Event()
        self._retry_thread: threading.Thread | None = None
        self._retry_interval = 300.0

    def world_reachable(self, world: str, *, refresh: bool = False) -> bool:
        """Bounded TCP-only upstream preflight, not an identity attestation.

        A world host must be derived solely from a validated configured world
        name. HTTPS certificate/player/cookie validation still belongs to the
        authenticated IkaBot session. Negative checks expire quickly so the
        recovery loop can recover automatically after a temporary outage.
        """
        if not isinstance(world, str) or _WORLD.fullmatch(world) is None:
            return False
        now = time.monotonic()
        with self._mutex:
            cached = self._connectivity.get(world)
            if not refresh and cached and now - cached[0] < 30:
                return cached[1]
        reachable = False
        try:
            with socket.create_connection(
                (f"{world}.ikariam.gameforge.com", 443), timeout=3.0,
            ):
                reachable = True
        except (OSError, ValueError):
            pass
        with self._mutex:
            self._connectivity[world] = (time.monotonic(), reachable)
        return reachable

    def start_auto_restore(
        self, accounts: list[Account], *, confirmed: bool, retry_seconds: float = 300,
    ) -> None:
        """Retry read-only, previously consented cookies without re-login/tasks.

        This work runs outside Uvicorn startup, so network failure never blocks
        the API. Retry is opt-in through the existing restore-saved-workers CLI
        flag and never uses a browser, a password, or a background game task.
        """
        if confirmed is not True:
            raise ValueError("Explicit read-only restore consent required")
        if not self.owner.matches_accounts(accounts):
            raise ValueError("Saved worker retry accounts do not match the owner")
        if retry_seconds <= 0:
            raise ValueError("Retry interval must be positive")
        with self._mutex:
            if self._retry_thread is not None:
                raise ValueError("Saved-cookie recovery retry already running")
            self._retry_interval = retry_seconds
            self._retry_stop.clear()
            self._retry_thread = threading.Thread(
                target=self._auto_restore_loop, args=(tuple(accounts),),
                name="daedalus-saved-cookie-restore", daemon=True,
            )
            self._retry_thread.start()

    def _auto_restore_loop(self, accounts: tuple[Account, ...]) -> None:
        while not self._retry_stop.is_set():
            try:
                self.restore_saved(list(accounts), confirmed=True)
            except Exception:  # noqa: BLE001 - sanitized daemon boundary
                logger.warning("Scheduled saved-cookie recovery pass could not finish")
            if self._retry_stop.wait(self._retry_interval):
                break

    def recovery_status(self) -> dict[str, object]:
        """Public-safe state for a health diagnostic; no account/world names."""
        with self._mutex:
            enabled = self._retry_thread is not None
            unavailable = sum(
                not ok for checked, ok in self._connectivity.values()
                if time.monotonic() - checked < self._retry_interval + 30
            )
            return {
                "enabled": enabled, "retry_seconds": int(self._retry_interval),
                "unreachable_worlds": unavailable,
            }

    def reap(self) -> None:
        """Release a dead child so a later explicit login can retry."""
        with self._mutex:
            for aid, worker in list(self._workers.items()):
                if worker.alive():
                    continue
                try:
                    worker.stop()
                except (OSError, RecoveryWorkerError):
                    logger.warning("Stopped cookie worker could not be fully cleaned up")
                    continue
                worker.lease.close()
                del self._workers[aid]
                logger.warning("Verified cookie worker exited; account is disconnected")

    def start(self, account: Account) -> None:
        """Requires prior one-time browser consent and a server-bound cookie.

        Never replaces a live account owner or an unrelated IkaBot IPC session.
        The authenticated flag is set only after a fresh private IPC probe.
        """
        with self._mutex:
            self.reap()
            if account.id in self._workers or self.owner.status(account.id) != "not_connected":
                raise RecoveryWorkerError("Another worker owns this game account")
            try:
                if self.router.fallback.has_account(account):
                    raise RecoveryWorkerError("A separate IkaBot owner is already running")
            except EngineIPCUnavailable:
                pass
            lease = self.owner.acquire(account.id)
            child = None
            descriptor = RecoveryWorkers._descriptor(account)
            try:
                if descriptor.exists():
                    candidate = ControlledIPCClient(descriptor)
                    try:
                        if candidate.has_account(account):
                            raise RecoveryWorkerError("Existing account IPC owner is still running")
                    except EngineIPCUnavailable:
                        pass
                    descriptor.unlink()
                env = os.environ.copy()
                env["DAEDALUS_ACCOUNT_IPC_FILE"] = str(descriptor)
                child = subprocess.Popen(
                    [sys.executable, "-m", "daedalus.browser_cookie_child"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, env=env,
                    start_new_session=(os.name == "posix"),
                )
                assert child.stdin is not None
                child.stdin.write(json.dumps({
                    "id": account.id, "world": account.world, "player": account.player,
                }, separators=(",", ":")).encode() + b"\n")
                child.stdin.close()
                candidate = ControlledIPCClient(descriptor)
                deadline = time.monotonic() + self.launch_timeout
                while time.monotonic() < deadline:
                    exit_code = child.poll()
                    if exit_code is not None:
                        # Only a fixed numeric exit code, never stderr or a
                        # game URL/cookie from the isolated engine process.
                        logger.warning("Cookie-only IPC child exited before attestation: code=%d", exit_code)
                        break
                    if descriptor.exists():
                        try:
                            if candidate.validate_account(account):
                                self.router.use(account.id, descriptor)
                                lease.transition(SessionPhase.AUTHENTICATED)
                                worker = ManagedAccountWorker(
                                    account, descriptor, child, lease, self.router,
                                )
                                self._workers[account.id] = worker
                                logger.info("Cookie-only worker independently authenticated and attached")
                                return
                        except (EngineIPCUnavailable, ValueError, OSError):
                            pass
                    time.sleep(0.2)
                raise RecoveryWorkerError("Verified cookie worker did not become ready")
            except Exception:  # noqa: BLE001 - sanitized worker process boundary
                logger.warning("Cookie-only worker startup failed without attaching a session")
                raise RecoveryWorkerError("Cookie-only worker startup failed") from None
            finally:
                if account.id not in self._workers:
                    if child is not None:
                        try:
                            ManagedAccountWorker(
                                account, descriptor, child, lease, self.router,
                            ).stop()
                        except (OSError, RecoveryWorkerError):
                            logger.error("Cannot confirm failed cookie worker was stopped")
                            # Fail closed: retain the owner lease if child may still exist.
                            raise RecoveryWorkerError("Cookie worker cleanup is uncertain") from None
                    lease.close()

    def restore_saved(self, accounts: list[Account], *, confirmed: bool) -> dict[str, int]:
        """Opt-in, read-only startup recovery of previously verified world cookies.

        No browser login, lobby token, task replay, or plaintext cookie
        transport occurs. Each account gets an independent fresh IPC/player
        attestation before becoming authenticated.
        """
        if confirmed is not True:
            raise ValueError("Explicit read-only restore consent required")
        from daedalus.saved_session_recovery import (
            SavedSessionUnavailable,
            _email_binding,
            _world_cookie_binding,
        )

        report = {"connected": 0, "missing_binding": 0, "unavailable": 0}
        warned_worlds: set[str] = set()
        for account in accounts:
            if self._retry_stop.is_set() and self._retry_thread is not None:
                break
            if not account.enabled:
                continue
            self.reap()
            if self.owner.status(account.id) == SessionPhase.AUTHENTICATED.value:
                report["connected"] += 1
                continue
            try:
                _email_binding(account, None)
                if _world_cookie_binding(account, None) is None:
                    report["missing_binding"] += 1
                    continue
            except SavedSessionUnavailable:
                report["missing_binding"] += 1
                continue
            if not self.world_reachable(account.world):
                report["unavailable"] += 1
                if account.world not in warned_worlds:
                    logger.warning(
                        "Game world unreachable from backend; saved-cookie retry deferred"
                    )
                    warned_worlds.add(account.world)
                continue
            try:
                self.start(account)
            except (RecoveryWorkerError, SessionBusyError, OSError, ValueError):
                report["unavailable"] += 1
                logger.warning("Previously verified cookie could not restore a worker")
            else:
                report["connected"] += 1
        logger.info("Saved-cookie restore completed: %s connected, %s missing, %s unavailable",
                    report["connected"], report["missing_binding"], report["unavailable"])
        return report

    def close(self) -> None:
        self._retry_stop.set()
        thread = self._retry_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self.launch_timeout + 5)
            if thread.is_alive():
                raise RecoveryWorkerError("Scheduled cookie restore is still shutting down")
        with self._mutex:
            for aid, worker in list(self._workers.items()):
                try:
                    worker.stop()
                except (OSError, RecoveryWorkerError):
                    logger.error("Cookie worker shutdown could not be confirmed")
                    continue
                worker.lease.close()
                del self._workers[aid]
