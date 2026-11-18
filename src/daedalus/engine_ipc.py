"""Attach read-only to an already-running IkaBot IPC worker.

No game login, session restore, process creation, or task launch occurs here.
Daedalus only asks the engine for identities and already-authenticated cities.
"""

from __future__ import annotations

import json
import os
import socket
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from daedalus.accounts import Account
from daedalus.warehouse import (
    RESOURCES,
    CityWarehouseSnapshot,
    WarehouseParseError,
    WarehouseResources,
    parse_amount,
)

_MAX_DESCRIPTOR_BYTES = 4096
_MAX_REPLY_BYTES = 512 * 1024
_ALLOWED = frozenset({"ping", "list_sessions", "list_cities_existing", "warehouse_snapshots_existing"})


class EngineIPCUnavailable(RuntimeError):
    """A safe, nonsecret reason why no compatible engine is reachable."""


def default_ipc_descriptor_path() -> Path:
    """The engine's public IPC discovery location, never inside this repository."""
    return Path.home() / ".ikabot" / "ipc.json"


def _is_exact_identity(value: object, account: Account) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("world"), str)
        and isinstance(value.get("player"), str)
        and value["world"].casefold() == account.world.casefold()
        and value["player"].casefold() == account.player.casefold()
    )


class ExistingIPCClient:
    """Authenticated local IPC with descriptor validation and strict allowlist."""

    def __init__(self, descriptor_path: str | Path | None = None) -> None:
        self._path = (
            Path(descriptor_path).expanduser()
            if descriptor_path is not None
            else default_ipc_descriptor_path()
        )

    def _descriptor(self) -> tuple[int, str]:
        path = self._path
        try:
            if path.is_symlink() or path.parent.is_symlink():
                raise EngineIPCUnavailable("IPC descriptor cannot be a symlink")
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_DESCRIPTOR_BYTES:
                raise EngineIPCUnavailable("IPC descriptor is invalid")
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise EngineIPCUnavailable("IPC descriptor must be owner-only")
            with path.open("rb") as handle:
                raw = handle.read(_MAX_DESCRIPTOR_BYTES + 1)
            if len(raw) > _MAX_DESCRIPTOR_BYTES:
                raise EngineIPCUnavailable("IPC descriptor is too large")
            descriptor = json.loads(raw)
        except (OSError, ValueError, TypeError) as exc:
            raise EngineIPCUnavailable("No readable, valid IkaBot IPC descriptor") from exc
        if not isinstance(descriptor, dict):
            raise EngineIPCUnavailable("IPC descriptor must be an object")
        if descriptor.get("host") != "127.0.0.1":
            raise EngineIPCUnavailable("IkaBot IPC must be bound to loopback")
        port, pid, authkey = (
            descriptor.get("port"),
            descriptor.get("pid"),
            descriptor.get("authkey"),
        )
        if type(port) is not int or not 0 < port < 65536:
            raise EngineIPCUnavailable("Invalid IkaBot IPC port")
        if type(pid) is not int or pid <= 0:
            raise EngineIPCUnavailable("Invalid IkaBot IPC owner PID")
        if not isinstance(authkey, str) or len(authkey) != 64:
            raise EngineIPCUnavailable("Invalid IkaBot IPC authentication key")
        try:
            bytes.fromhex(authkey)
        except ValueError as exc:
            raise EngineIPCUnavailable("Invalid IkaBot IPC authentication key") from exc
        # Windows os.kill(pid, 0) may call TerminateProcess rather than probing.
        # On Windows, rely on authenticated loopback connection and socket timeout.
        if os.name != "nt":
            try:
                os.kill(pid, 0)
            except ProcessLookupError as exc:
                raise EngineIPCUnavailable("IkaBot IPC owner process no longer exists") from exc
            except PermissionError as exc:
                raise EngineIPCUnavailable("Cannot verify IkaBot IPC owner") from exc
        return port, authkey

    def request(self, action: str, *, account: Account | None = None) -> dict[str, Any]:
        """Issue only a fixed nonmutating action; never expose an unrestricted RPC."""
        if action not in _ALLOWED:
            raise ValueError("This IPC bridge is read-only")
        if action in {"list_cities_existing", "warehouse_snapshots_existing"} and account is None:
            raise ValueError("Explicit account identity is required")
        if account is not None and not account.enabled:
            raise ValueError("Account is disabled")
        return self._exchange(action, account=account)

    def _exchange(
        self, action: str, *, account: Account | None = None,
        additional: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """Private wire method; public request() remains strictly read-only."""
        port, secret = self._descriptor()
        payload: dict[str, object] = {"action": action, "authkey": secret}
        if account is not None:
            payload.update(world=account.world, player=account.player)
        if additional is not None:
            if any(key in additional for key in ("action", "authkey", "world", "player")):
                raise ValueError("Cannot override IPC authentication or account identity")
            payload.update(additional)
        wire = (json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        if len(wire) > 65536:
            raise ValueError("IPC task request exceeds safe size limit")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as conn:
                conn.settimeout(8.0)
                conn.sendall(wire)
                data = bytearray()
                while len(data) <= _MAX_REPLY_BYTES:
                    chunk = conn.recv(min(65536, _MAX_REPLY_BYTES + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if b"\n" in chunk:
                        break
        except (OSError, TimeoutError) as exc:
            raise EngineIPCUnavailable("IkaBot IPC server is unavailable") from exc
        if len(data) > _MAX_REPLY_BYTES or b"\n" not in data:
            raise EngineIPCUnavailable("IkaBot IPC reply is invalid or oversized")
        try:
            reply = json.loads(bytes(data).split(b"\n", 1)[0])
        except (ValueError, UnicodeError) as exc:
            raise EngineIPCUnavailable("IkaBot IPC reply is not JSON") from exc
        if not isinstance(reply, dict) or reply.get("status") != "ok":
            # Engine errors may contain account data or cookie fragments.
            raise EngineIPCUnavailable("IkaBot IPC request failed")
        return reply

    def list_sessions(self) -> list[dict[str, str]]:
        """Only nonsecret in-memory identities; do not reveal unrelated account emails."""
        rows = self.request("list_sessions").get("sessions")
        if not isinstance(rows, list) or len(rows) > 100:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid session metadata")
        sessions = []
        for item in rows:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("world"), str)
                or not isinstance(item.get("player"), str)
                or not item["world"]
                or not item["player"]
            ):
                raise EngineIPCUnavailable("IkaBot IPC returned invalid session identity")
            sessions.append({"world": item["world"], "player": item["player"]})
        return sessions

    def has_account(self, account: Account) -> bool:
        return sum(_is_exact_identity(row, account) for row in self.list_sessions()) == 1

    def cities(self, account: Account) -> list[dict[str, object]]:
        matches = sum(_is_exact_identity(row, account) for row in self.list_sessions())
        if matches != 1:
            raise EngineIPCUnavailable("No unique already-authenticated account session")
        response = self.request("list_cities_existing", account=account)
        if (
            not isinstance(response.get("world"), str)
            or not isinstance(response.get("username"), str)
            or response["world"].casefold() != account.world.casefold()
            or response["username"].casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("IkaBot IPC returned another account's data")
        rows = response.get("cities")
        if not isinstance(rows, list) or len(rows) > 500:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid city data")
        result: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("IkaBot IPC returned malformed city data")
            city_id = row.get("id")
            name = row.get("name")
            if type(city_id) is not int or city_id <= 0 or not isinstance(name, str):
                raise EngineIPCUnavailable("IkaBot IPC returned invalid city identity")
            result.append(
                {
                    "id": city_id,
                    "name": name[:120],
                    "coords": str(row.get("coords", ""))[:40],
                    "tradegood": str(row.get("tradegood", ""))[:20],
                }
            )
        return result

    def warehouses(self, account: Account) -> list[CityWarehouseSnapshot]:
        """Convert numeric-only engine IPC snapshots into typed warehouse records."""
        if sum(_is_exact_identity(row, account) for row in self.list_sessions()) != 1:
            raise EngineIPCUnavailable("No unique already-authenticated account session")
        response = self.request("warehouse_snapshots_existing", account=account)
        if (
            not isinstance(response.get("world"), str)
            or not isinstance(response.get("username"), str)
            or response["world"].casefold() != account.world.casefold()
            or response["username"].casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("IkaBot IPC returned another account's data")
        rows = response.get("cities")
        if not isinstance(rows, list) or len(rows) > 100:
            raise EngineIPCUnavailable("Invalid warehouse snapshot collection")
        snapshots: list[CityWarehouseSnapshot] = []
        seen: set[int] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Invalid warehouse snapshot")
            city_id, name = row.get("city_id"), row.get("city_name")
            if type(city_id) is not int or city_id <= 0 or city_id in seen:
                raise EngineIPCUnavailable("Invalid or duplicate warehouse city ID")
            if not isinstance(name, str) or not name or len(name) > 120:
                raise EngineIPCUnavailable("Invalid warehouse city name")
            seen.add(city_id)
            reported = row.get("unsecured")
            # Validate an explicit fixed set of resource names: never echo unknown markup.
            if not isinstance(reported, dict) or not reported or set(reported) - set(RESOURCES):
                raise EngineIPCUnavailable("Invalid unsecured resource fields")
            try:
                values = dict.fromkeys(RESOURCES)
                for resource, amount in reported.items():
                    if not isinstance(amount, str):
                        raise WarehouseParseError("Numeric warehouse amount required")
                    values[resource] = parse_amount(amount)
                capacity_str = row.get("capacity")
                if capacity_str is not None and not isinstance(capacity_str, str):
                    raise WarehouseParseError("Numeric capacity required")
                capacity = parse_amount(capacity_str) if capacity_str is not None else None
            except WarehouseParseError as exc:
                raise EngineIPCUnavailable("Invalid warehouse numeric value") from exc
            snapshots.append(CityWarehouseSnapshot(
                account_id=account.id,
                city_id=city_id,
                city_name=name,
                captured_at=datetime.now(UTC).isoformat(),
                resources=WarehouseResources(unsecured=values, capacity=capacity),
            ))
        return snapshots


class ExistingTaskIPCClient(ExistingIPCClient):
    """Explicitly enabled task control for already-authenticated sessions only.

    Unlike ExistingIPCClient.request, these mutating calls are exposed only
    through named operations with account, task, and PID validation.
    """

    def start_task(
        self, account: Account, task: str, config: dict[str, object], request_id: str
    ) -> dict[str, object]:
        if not account.enabled:
            raise ValueError("Cannot start tasks on disabled accounts")
        if not isinstance(task, str) or not task or len(task) > 80:
            raise ValueError("A task name is required")
        if not isinstance(config, dict) or "session" in config:
            raise ValueError("Task configuration must be a JSON object")
        if not isinstance(request_id, str) or len(request_id) != 36:
            raise ValueError("A UUID4 idempotency key is required")
        if not self.has_account(account):
            raise EngineIPCUnavailable("No unique already-authenticated account session")
        response = self._exchange(
            "start_task_existing", account=account,
            additional={"task": task, "config": config, "request_id": request_id},
        )
        self._check_identity(response, account)
        pid = response.get("pid")
        if type(pid) is not int or pid <= 0 or response.get("task") != task:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid task launch data")
        return {"pid": pid, "task": task, "status": "started", "request_id": request_id}

    @staticmethod
    def _check_identity(response: dict[str, Any], account: Account) -> None:
        if (
            not isinstance(response.get("world"), str)
            or not isinstance(response.get("username"), str)
            or response["world"].casefold() != account.world.casefold()
            or response["username"].casefold() != account.player.casefold()
        ):
            raise EngineIPCUnavailable("IkaBot IPC returned a different account identity")

    def list_tasks(self, account: Account) -> list[dict[str, object]]:
        response = self._exchange("list_managed_tasks", account=account)
        self._check_identity(response, account)
        rows = response.get("tasks")
        if not isinstance(rows, list) or len(rows) > 128:
            raise EngineIPCUnavailable("IkaBot IPC returned invalid managed task list")
        results: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise EngineIPCUnavailable("Invalid managed task entry")
            pid, task, status, started = (
                row.get("pid"), row.get("task"), row.get("status"), row.get("started_at")
            )
            if (
                type(pid) is not int or pid <= 0
                or not isinstance(task, str) or not task or len(task) > 80
                or status not in {"running", "finished"}
                or not isinstance(started, int | float)
            ):
                raise EngineIPCUnavailable("Invalid managed task fields")
            results.append({"pid": pid, "task": task, "status": status, "started_at": started})
        return results

    def stop_task(self, account: Account, pid: int) -> dict[str, object]:
        if type(pid) is not int or pid <= 0:
            raise ValueError("A valid managed task PID is required")
        response = self._exchange(
            "stop_managed_task", account=account, additional={"pid": pid}
        )
        if response.get("pid") != pid or response.get("state") != "stopped":
            raise EngineIPCUnavailable("IkaBot IPC returned invalid task stop confirmation")
        return {"pid": pid, "status": "stopped"}
