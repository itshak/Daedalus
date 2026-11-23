"""Supervised cookie-only world workers for explicit native Mac sign-in.

The HTTPS browser handoff verifies and seals the cookie first. A subsequent
host-local worker, launched without passwords or lobby tokens, independently
validates the same account before its private IPC endpoint becomes usable.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time

from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.recovery_runtime import ManagedAccountWorker, RecoveryWorkerError, RecoveryWorkers, RoutedAccountIPC

logger = logging.getLogger("daedalus.browser_cookie_workers")


class BrowserCookieWorkers:
    """One leased IkaBot process per exact configured account; no task replay."""

    def __init__(self, owner: AccountSessionCoordinator, router: RoutedAccountIPC,
                 *, launch_timeout: float = 35.0) -> None:
        self.owner = owner
        self.router = router
        self.launch_timeout = launch_timeout
        self._workers: dict[str, ManagedAccountWorker] = {}
        self._mutex = threading.RLock()

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
                    if child.poll() is not None:
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
            except Exception:
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

    def close(self) -> None:
        with self._mutex:
            for aid, worker in list(self._workers.items()):
                try:
                    worker.stop()
                except (OSError, RecoveryWorkerError):
                    logger.error("Cookie worker shutdown could not be confirmed")
                    continue
                worker.lease.close()
                del self._workers[aid]
