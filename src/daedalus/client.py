"""Typed-ish, read-only Daedalus HTTP client for local/remote desktop use.

Never stores a bearer token on disk or logs server response bodies. Plain HTTP
is restricted to loopback; use HTTPS or an authenticated local tunnel remotely.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

_ACCOUNT_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


class APIConnectionError(RuntimeError):
    """Sanitized transport/HTTP failure; never includes response bodies or credentials."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validated_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Use a server root URL with no embedded credentials, path or query")
    if parsed.scheme == "http":
        host = parsed.hostname
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if not loopback:
            raise ValueError("Plain HTTP is allowed only on loopback; use HTTPS or a local tunnel")
    return url.rstrip("/")


class DaedalusClient:
    """Read-only API client. Token exists only in process memory."""

    def __init__(
        self,
        server_url: str,
        api_token: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        server = _validated_url(server_url)
        if not isinstance(api_token, str) or len(api_token) < 32 or any(
            char in api_token for char in "\r\n\0"
        ):
            raise ValueError("A valid bearer token is required")
        self._server = server
        self._http = httpx.Client(
            base_url=server,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=httpx.Timeout(connect=8, read=120, write=8, pool=8),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"DaedalusClient(server={self._server!r}, token=[redacted])"

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def _read(self, path: str) -> dict[str, object]:
        try:
            response = self._http.get("/api/v1/" + path)
        except httpx.RequestError as exc:
            raise APIConnectionError("Cannot connect to Daedalus backend") from exc
        if response.status_code != 200:
            explanation = {
                401: "Backend authorization rejected",
                404: "Requested resource was not found",
                503: "Backend snapshot is not available yet",
            }.get(response.status_code, "Backend request failed")
            raise APIConnectionError(explanation, response.status_code)
        try:
            document = response.json()
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid JSON") from exc
        if not isinstance(document, dict):
            raise APIConnectionError("Backend returned an unexpected response shape")
        return document

    def _mutate(
        self, method: str, path: str, *, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        if method not in {"POST", "DELETE"}:
            raise ValueError("Unsupported HTTP method")
        try:
            response = self._http.request(method, "/api/v1/" + path, json=payload)
        except httpx.RequestError as exc:
            raise APIConnectionError("Cannot reach the Daedalus task controller") from exc
        if response.status_code != 200:
            explanation = {
                401: "Backend authorization rejected",
                404: "Requested account or task was not found",
                409: "Account is disabled",
                422: "Task request did not pass validation",
                503: "Task control is disabled or unavailable",
            }.get(response.status_code, "Task operation failed")
            raise APIConnectionError(explanation, response.status_code)
        try:
            document = response.json()
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid task result") from exc
        if not isinstance(document, dict):
            raise APIConnectionError("Backend returned unexpected task result")
        return document

    def task_control_status(self) -> dict[str, object]:
        return self._read("task-control")

    def tasks(self, account_id: str) -> list[dict[str, object]]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        values = self._read(f"accounts/{account_id}/tasks").get("tasks")
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise APIConnectionError("Backend returned invalid managed tasks")
        return values

    def start_task(
        self, account_id: str, task: str, config: dict[str, object],
        *, request_id: str | None = None,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if not isinstance(task, str) or not task or len(task) > 80:
            raise ValueError("Invalid task name")
        if not isinstance(config, dict):
            raise TypeError("Task config must be JSON object")
        if request_id is None:
            request_id = str(uuid4())
        if UUID(request_id).version != 4:
            raise ValueError("Task request ID must be UUID4")
        return self._mutate(
            "POST", f"accounts/{account_id}/tasks",
            payload={"task": task, "config": config, "request_id": request_id},
        )

    def stop_task(self, account_id: str, pid: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if type(pid) is not int or pid <= 0:
            raise ValueError("Invalid task PID")
        return self._mutate("DELETE", f"accounts/{account_id}/tasks/{pid}")

    def health(self) -> dict[str, object]:
        return self._read("health")

    def accounts(self) -> list[dict[str, object]]:
        data = self._read("accounts").get("accounts")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise APIConnectionError("Backend returned invalid account metadata")
        return data

    def capabilities(self) -> dict[str, object]:
        data = self._read("capabilities")
        if not isinstance(data.get("operations"), list):
            raise APIConnectionError("Backend returned invalid operation registry")
        return data

    def account_session(self, account_id: str) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        return self._read(f"accounts/{account_id}/session")

    def connected_accounts(self) -> list[str]:
        data = self._read("engine/connected-accounts").get("connected_account_ids")
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise APIConnectionError("Backend returned invalid attached-account list")
        return data

    def cities(self, account_id: str) -> list[dict[str, object]]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        data = self._read(f"accounts/{account_id}/cities").get("cities")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise APIConnectionError("Backend returned invalid city data")
        return data

    def warehouses(self, account_id: str) -> list[dict[str, object]]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        data = self._read(f"warehouses/{account_id}").get("cities")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise APIConnectionError("Backend returned invalid warehouse snapshots")
        return data
