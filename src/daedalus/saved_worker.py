"""Explicit opt-in, cookie-only, host-local IkaBot worker bootstrap.

Unlike a one-shot cookie probe, this holds the authoritative account lease and
an authenticated engine session until the local API process shuts down. It
never performs Gameforge lobby login, browser automation or task replay.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Self

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    OwnedAccountSession,
    SessionPhase,
)
from daedalus.accounts import Account
from daedalus.saved_session_recovery import (
    CredentialStore,
    SavedSessionUnavailable,
    _email_binding,
    _real_restore,
    _world_cookie_binding,
    verify_restored_identity,
)

logger = logging.getLogger(__name__)


class SavedWorkerUnavailable(RuntimeError):
    """Sanitized startup or shutdown failure without secret contents."""


class SavedCookieWorker:
    """Own exactly one previously saved, strictly verified world session."""

    def __init__(
        self,
        account: Account,
        coordinator: AccountSessionCoordinator,
        *,
        credential_store: CredentialStore | None = None,
        restore: Callable[[Account, str, str | None], object] | None = None,
        start_ipc: Callable[[object], object] | None = None,
        stop_ipc: Callable[[], None] | None = None,
    ) -> None:
        if (start_ipc is None) != (stop_ipc is None):
            raise ValueError("IPC start and stop must be provided together")
        self.account = account
        self.coordinator = coordinator
        self._credentials = credential_store
        self._restore = restore or _real_restore
        self._start_ipc = start_ipc
        self._stop_ipc = stop_ipc
        self.lease: OwnedAccountSession | None = None
        self._session: object | None = None
        self._ipc_server: object | None = None

    def start(self, *, confirmed: bool) -> SavedCookieWorker:
        if confirmed is not True:
            raise SavedWorkerUnavailable("Explicit cookie-only network consent is required")
        if self.lease is not None or self._session is not None:
            raise SavedWorkerUnavailable("This worker has already started")
        if not self.account.enabled:
            raise SavedWorkerUnavailable("The selected account is disabled")
        if (
            self.account.id not in self.coordinator.account_ids
            or self.coordinator._accounts[self.account.id] != self.account
        ):
            raise SavedWorkerUnavailable("Worker identity does not match configured account")
        try:
            self.lease = self.coordinator.acquire(self.account.id)
            email = _email_binding(self.account, self._credentials)
            cookie = _world_cookie_binding(self.account, self._credentials)
            # The maintained engine's cookies_only=True code path must never
            # ask the lobby for a loginLink, password, CAPTCHA or new token.
            self._session = self._restore(self.account, email, cookie)
            verify_restored_identity(self._session, self.account)
            if self._start_ipc is None:
                from ikabot.helpers.ipc import start_dedicated_ipc_server
                self._ipc_server = start_dedicated_ipc_server(self._session)
            else:
                self._ipc_server = self._start_ipc(self._session)
            if self._ipc_server is None:
                raise SavedWorkerUnavailable("A separate IkaBot IPC owner is already running")
            self.lease.transition(SessionPhase.AUTHENTICATED)
            return self
        except BaseException as exc:
            try:
                self.close()
            except SavedWorkerUnavailable:
                logger.warning("Saved worker cleanup could not complete safely")
                raise SavedWorkerUnavailable(
                    "Cannot safely confirm the failed worker was stopped"
                ) from None
            if isinstance(exc, SavedWorkerUnavailable):
                raise
            if isinstance(exc, SavedSessionUnavailable):
                raise SavedWorkerUnavailable(str(exc)) from exc
            raise SavedWorkerUnavailable(
                "Saved cookies could not start a verified isolated worker; "
                "manual recovery may be required"
            ) from exc

    def recover_from_verified_cookie(self, controller, *, confirmed: bool) -> dict[str, str]:
        """Rebind an idle dedicated worker without releasing its identity lease.

        The operator must have already imported and engine-verified a fresh
        world cookie into this host's keyring. No task is replayed. Reject
        running or uncertain tasks before replacing the IPC session.
        """
        if confirmed is not True:
            raise SavedWorkerUnavailable("Explicit worker recovery approval is required")
        with controller._mutex:
            if (
                self.lease is None or self.lease._closed
                or self._session is None or self._ipc_server is None
                or controller._coordinator is not self.coordinator
                or self.lease not in controller.owned_sessions()
            ):
                raise SavedWorkerUnavailable("A matching owned dedicated worker is required")
            try:
                status = controller.list_tasks(self.account.id)
                if any(task.get("status") in {"running", "stopping"}
                       for task in status["engine_tasks"]) or any(
                    item.get("status") in {"pending", "dispatching", "uncertain"}
                    for item in status["requests"]
                ):
                    raise SavedWorkerUnavailable(
                        "Active or uncertain tasks must be reconciled before recovery"
                    )
            except SavedWorkerUnavailable:
                raise
            except Exception as exc:
                raise SavedWorkerUnavailable("Cannot verify that the worker is idle") from exc
            candidate = None
            try:
                email = _email_binding(self.account, self._credentials)
                cookie = _world_cookie_binding(self.account, self._credentials)
                candidate = self._restore(self.account, email, cookie)
                verify_restored_identity(candidate, self.account)
            except Exception as exc:
                if candidate is not None:
                    http = getattr(candidate, "s", None)
                    if callable(getattr(http, "close", None)):
                        http.close()
                raise SavedWorkerUnavailable("Recovered cookie did not verify the worker") from exc
            old = self._session
            try:
                if self._stop_ipc is None:
                    from ikabot.helpers.ipc import stop_ipc_server
                    stop_ipc_server()
                else:
                    self._stop_ipc()
            except Exception as exc:
                http = getattr(candidate, "s", None)
                if callable(getattr(http, "close", None)):
                    http.close()
                raise SavedWorkerUnavailable("Cannot safely stop the old IPC owner") from exc
            self._ipc_server = None
            try:
                if self._start_ipc is None:
                    from ikabot.helpers.ipc import start_dedicated_ipc_server
                    new_ipc = start_dedicated_ipc_server(candidate)
                else:
                    new_ipc = self._start_ipc(candidate)
                if new_ipc is None:
                    raise SavedWorkerUnavailable("Recovered IPC owner did not start")
                self._ipc_server = new_ipc
                self._session = candidate
                old_http = getattr(old, "s", None)
                if callable(getattr(old_http, "close", None)):
                    try:
                        old_http.close()
                    except OSError:
                        logger.warning("Previous session cleanup was incomplete")
                if self.lease.phase is SessionPhase.PAUSED:
                    self.lease.transition(SessionPhase.VALIDATING_SESSION)
                if self.lease.phase is SessionPhase.VALIDATING_SESSION:
                    self.lease.transition(SessionPhase.AUTHENTICATED)
                return {"account_id": self.account.id, "status": "worker_recovered"}
            except Exception as exc:
                self._session = candidate
                # Keep the lease; a supervisor must explicitly shut down or
                # reconcile the now unavailable worker. Never retry tasks.
                if self.lease.phase is not SessionPhase.FAILED:
                    self.lease.transition(SessionPhase.FAILED)
                raise SavedWorkerUnavailable(
                    "Recovered worker IPC failed; account lease retained"
                ) from exc

    def close(self) -> None:
        if self._ipc_server is not None:
            try:
                if self._stop_ipc is None:
                    from ikabot.helpers.ipc import stop_ipc_server
                    stop_ipc_server()
                else:
                    self._stop_ipc()
            except Exception as exc:
                # Do not release the identity lease while an IPC worker may
                # still be accepting live task dispatch.
                raise SavedWorkerUnavailable(
                    "Cannot safely confirm the dedicated IPC worker has stopped"
                ) from exc
            self._ipc_server = None
        try:
            if self._session is not None:
                http = getattr(self._session, "s", None)
                if callable(getattr(http, "close", None)):
                    http.close()  # never logout: that could rotate a live world
        finally:
            self._session = None
            if self.lease is not None:
                self.lease.close()
                self.lease = None

    def __enter__(self) -> Self:
        if self.lease is None:
            raise SavedWorkerUnavailable("Explicit start confirmation is required")
        return self

    def __exit__(self, *_unused: object) -> None:
        self.close()
