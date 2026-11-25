"""Bounded, account-scoped review tickets for native operation launches.

Tickets are opaque process-local identifiers, not bearer credentials. The
controller still authenticates every request and the engine revalidates plans.
Restart or expiry requires a new preview. A ticket cannot authorize two
different task requests, even after an uncertain outcome.
"""
from __future__ import annotations

import copy
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Preview:
    account_id: str
    operation: str
    config: dict[str, object]
    expires_at: float
    request_id: str | None = None


class PreviewUnavailable(ValueError):
    """The preview expired, belongs to another scope, or has been consumed."""


class OperationPreviews:
    def __init__(
        self, *, ttl: int = 120, capacity: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl <= 0 or capacity <= 0:
            raise ValueError("Preview limits must be positive")
        self.ttl = ttl
        self._capacity = capacity
        self._clock = clock
        self._mutex = threading.Lock()
        self._entries: dict[str, _Preview] = {}

    def _prune(self, now: float) -> None:
        for key in list(self._entries):
            if self._entries[key].expires_at <= now:
                del self._entries[key]

    def issue(
        self, account_id: str, operation: str, config: dict[str, object],
    ) -> str:
        with self._mutex:
            now = self._clock()
            self._prune(now)
            while len(self._entries) >= self._capacity:
                del self._entries[next(iter(self._entries))]
            key = secrets.token_urlsafe(32)
            self._entries[key] = _Preview(
                account_id, operation, copy.deepcopy(config), now + self.ttl,
            )
            return key

    def check_unused(self, key: str, account_id: str, operation: str) -> None:
        """Read-only check; a claimed or expired ticket cannot join a new batch."""
        with self._mutex:
            self._prune(self._clock())
            preview = self._entries.get(key)
            if (preview is None or preview.account_id != account_id
                    or preview.operation != operation or preview.request_id is not None):
                raise PreviewUnavailable("Review expired or unavailable; prepare a new preview")

    def claim(
        self, key: str, account_id: str, operation: str, request_id: str,
    ) -> dict[str, object]:
        with self._mutex:
            self._prune(self._clock())
            preview = self._entries.get(key)
            if (
                preview is None or preview.account_id != account_id
                or preview.operation != operation
                or preview.request_id not in (None, request_id)
            ):
                raise PreviewUnavailable("Review expired or unavailable; prepare a new preview")
            preview.request_id = request_id
            return copy.deepcopy(preview.config)
