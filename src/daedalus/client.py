"""Typed-ish, read-only Daedalus HTTP client for local/remote desktop use.

Never stores a bearer token on disk or logs server response bodies. Plain HTTP
is restricted to loopback; use HTTPS or an authenticated local tunnel remotely.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Self
from urllib.parse import urlsplit

import httpx

from daedalus.reviewed_operations import (
    validate_attack_inventory,
    validate_attack_plan,
    validate_build_inventory,
    validate_grind_plan,
    validate_island_destinations,
    validate_shipment_plan,
    validated_attack_draft,
    validated_build_draft,
    validated_coordinates,
    validated_grind_draft,
    validated_layout_draft,
    validated_shipment_draft,
    validated_station_draft,
    validated_worker_draft,
)

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

    def _write(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            response = self._http.post("/api/v1/" + path, json=payload)
        except httpx.RequestError as exc:
            raise APIConnectionError("Cannot connect to Daedalus backend") from exc
        if response.status_code != 200:
            # Only recognize a specifically audited, nonsecret error string.
            # Never surface arbitrary server messages, which may contain
            # session data or tokens from older engine versions.
            if response.status_code in {409, 422}:
                try:
                    detail = response.json().get("detail")
                except (TypeError, ValueError, AttributeError):
                    detail = None
                safe_409 = {
                    "Configure Telegram or Discord notifications before starting this alert",
                    "A Gameforge email is required for first-time account binding",
                    "This worker is busy or has an uncertain task; reconcile it before login",
                    "Running or uncertain tasks must be reconciled before login",
                    "This backend has not enabled native browser login",
                    "Server did not verify the exact game account; login was not accepted",
                    "Gameforge email differs from the existing account binding",
                    "Another worker owns this game account",
                    "Browser handoff is expired or already consumed",
                    "Game world is unreachable from the Daedalus server; saved sessions will retry when connectivity recovers",
                }
                if (response.status_code == 409 and detail in safe_409) or (
                    response.status_code == 422 and detail ==
                    "Invalid automation parameters. Review the fields and try again."
                ):
                    raise APIConnectionError(detail, response.status_code)
            raise APIConnectionError("Backend task request was rejected", response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid task JSON") from exc
        if not isinstance(data, dict):
            raise APIConnectionError("Backend returned invalid task receipt")
        return data

    def account_config(self) -> dict[str, object]:
        """Read safe account metadata editor status and optimistic generation."""
        try:
            result = self._read("account-config")
        except APIConnectionError as exc:
            if exc.status_code == 404:  # older read-only backend
                return {"enabled": False, "revision": None, "accounts": []}
            raise
        if result.get("enabled") is True and (
            not isinstance(result.get("revision"), str)
            or not isinstance(result.get("accounts"), list)
        ):
            raise APIConnectionError("Backend returned invalid editable account configuration")
        return result

    def replace_account_config(
        self, revision: str, accounts: list[dict[str, object]], *, confirmed: bool,
    ) -> dict[str, object]:
        if not confirmed or not re.fullmatch(r"[0-9a-f]{64}", revision):
            raise ValueError("An explicit confirmation and valid revision are required")
        if not isinstance(accounts, list):
            raise TypeError("Invalid account records")
        try:
            response = self._http.put("/api/v1/account-config", json={
                "revision": revision, "accounts": accounts, "confirmed": True,
            })
        except httpx.RequestError as exc:
            raise APIConnectionError("Cannot connect to Daedalus backend") from exc
        if response.status_code != 200:
            raise APIConnectionError("Account metadata change was rejected", response.status_code)
        try:
            result = response.json()
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid metadata JSON") from exc
        if not isinstance(result, dict) or result.get("enabled") is not True:
            raise APIConnectionError("Backend returned invalid metadata receipt")
        return result

    def task_control_status(self) -> dict[str, object]:
        return self._read("task-control")

    def reviewed_batch_check(self, entries: list[dict[str, str]]) -> dict[str, object]:
        from daedalus.reviewed_batch import validate_batch_check, validated_batch_entries

        clean = validated_batch_entries(entries)
        result = self._write("tasks/reviewed-batch-check", {"entries": clean})
        try:
            return validate_batch_check(result, clean)
        except ValueError as exc:
            raise APIConnectionError("Invalid independent review check") from exc

    def start_reviewed_task(self, account_id: str, task: str, preview_id: str,
                            request_id: str) -> dict[str, object]:
        from daedalus.reviewed_batch import validated_batch_entries

        validated_batch_entries([{"account_id": account_id, "task": task, "preview_id": preview_id}])
        return self.start_task(account_id, task, {"preview_id": preview_id},
                               request_id, confirmed=True)

    def start_task(
        self, account_id: str, task: str, config: dict[str, object],
        request_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        from daedalus.reviewed_batch import PREVIEW_ID_PATTERN, REVIEW_ENDPOINTS

        endpoint = REVIEW_ENDPOINTS.get(task)
        # Keep legacy own-city construction/shipment clients compatible.
        if endpoint and (task not in {"constructionList", "sendResources"} or set(config) == {"preview_id"}):
            if (set(config) != {"preview_id"} or not isinstance(config["preview_id"], str)
                    or not re.fullmatch(PREVIEW_ID_PATTERN, config["preview_id"])):
                raise ValueError("Prepare a valid operation review first")
            payload = {"preview_id": config["preview_id"], "request_id": request_id,
                       "confirmed": confirmed}
            if endpoint == "worker-start":
                payload["task"] = task
            return self._write(f"accounts/{account_id}/tasks/{endpoint}", payload)
        return self._write(f"accounts/{account_id}/tasks", {
            "task": task, "config": config, "request_id": request_id,
            "confirmed": confirmed,
        })

    def task_preflight(self, account_id: str, task: str) -> dict[str, object]:
        """Show only game-side prerequisite readiness, never auth materials."""
        if not _ACCOUNT_ID.fullmatch(account_id) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]{0,79}", task
        ):
            raise ValueError("Invalid task selection")
        from urllib.parse import quote

        data = self._read(f"accounts/{account_id}/tasks/preflight?task={quote(task)}")
        if (data.get("account_id") != account_id or data.get("task") != task
                or type(data.get("ready")) is not bool
                or data.get("reason") not in {"none", "notifications_required"}
                or type(data.get("unresolved_request")) is not bool):
            raise APIConnectionError("Backend returned invalid prerequisite status")
        return data

    def activity(self, account_id: str, *, before: int | None = None,
                 limit: int = 50, status: str = "all") -> dict[str, object]:
        from daedalus.activity_history import validate_activity_page, validate_activity_query

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        validate_activity_query(before, limit, status)
        path = f"accounts/{account_id}/activity?limit={limit}&status={status}"
        if before is not None:
            path += f"&before={before}"
        data = self._read(path)
        try:
            return validate_activity_page(data, account_id, before, limit, status)
        except ValueError as exc:
            raise APIConnectionError("Invalid server activity") from exc

    def tasks(self, account_id: str) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        return self._read(f"accounts/{account_id}/tasks")

    def stop_task(self, account_id: str, task_id: str) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if not re.fullmatch(r"[0-9a-f]{24}", task_id):
            raise ValueError("Invalid managed task ID")
        return self._write(f"accounts/{account_id}/tasks/{task_id}/stop", {})

    def acknowledge_task(
        self, account_id: str, request_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if not re.fullmatch(r"[0-9a-f-]{36}", request_id):
            raise ValueError("Invalid task request ID")
        return self._write(
            f"accounts/{account_id}/tasks/requests/{request_id}/acknowledge",
            {"confirmed": confirmed},
        )

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

    def recovery_index(self) -> dict[str, object]:
        try:
            return self._read("recovery")
        except APIConnectionError as exc:
            if exc.status_code in (404,503):
                return {"enabled": False, "supervisor_enabled": False, "accounts": []}
            raise

    def recovery_import(self, account_id: str) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account identity")
        return self._write(f"accounts/{account_id}/recovery/import-saved-token", {"confirmed": True})

    def recovery_policy(self, account_id: str, *, enabled: bool,
                        expected_revision: int) -> dict[str, object]:
        if (not _ACCOUNT_ID.fullmatch(account_id) or type(enabled) is not bool
                or type(expected_revision) is not int or expected_revision < 0):
            raise ValueError("Invalid recovery policy selection")
        try:
            response = self._http.put(f"/api/v1/accounts/{account_id}/recovery/policy",
                json={"confirmed": True, "enabled": enabled, "auto_resume": enabled,
                      "grace_seconds": 300, "expected_revision": expected_revision})
        except httpx.RequestError as exc:
            raise APIConnectionError("Cannot connect to Daedalus backend") from exc
        if response.status_code != 200:
            raise APIConnectionError("Recovery policy change was rejected", response.status_code)
        result = response.json()
        if not isinstance(result, dict) or result.get("enabled") is not enabled:
            raise APIConnectionError("Invalid recovery policy confirmation")
        return result

    def recovery_bulk(self, account_ids: list[str], *, enabled: bool) -> dict[str,object]:
        if (not account_ids or len(set(account_ids)) != len(account_ids)
                or not all(isinstance(aid,str) and _ACCOUNT_ID.fullmatch(aid)
                           for aid in account_ids)):
            raise ValueError("Invalid distinct account selection")
        return self._write("recovery/policy/bulk", {
            "account_ids": account_ids, "enabled": enabled,
            "auto_resume": enabled, "grace_seconds": 300, "confirmed": True,
        })

    def recovery_pause(self, account_id: str, seconds: int | None) -> dict[str,object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or seconds not in (None,900,1800,3600):
            raise ValueError("Invalid recovery pause")
        return self._write(f"accounts/{account_id}/recovery/pause",
                           {"confirmed": True, "seconds": seconds})

    def recovery_unpause(self, account_id: str) -> dict[str,object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        return self._write(f"accounts/{account_id}/recovery/unpause", {"confirmed": True})

    def recovery_resume(self, account_id: str) -> dict[str,object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        return self._write(f"accounts/{account_id}/recovery/resume-now", {"confirmed": True})

    def recovery_jobs(self, account_id: str) -> dict[str,object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        return self._read(f"accounts/{account_id}/recovery/jobs")

    def health(self) -> dict[str, object]:
        return self._read("health")

    def release_status(self) -> dict[str, object]:
        from daedalus.release_catalog import validate_release_status

        try:
            return validate_release_status(self._read("release-status"))
        except ValueError:
            raise APIConnectionError("Invalid release metadata") from None

    def accounts(self) -> list[dict[str, object]]:
        data = self._read("accounts").get("accounts")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise APIConnectionError("Backend returned invalid account metadata")
        return data

    def login_vaults(self) -> dict[str, dict[str, object]]:
        """Obtain sealed server copies; never request plaintext passwords."""
        try:
            data = self._read("login-vaults")
        except APIConnectionError as exc:
            if exc.status_code in {404, 503}:
                return {}  # Older servers have no protected vault feature.
            raise
        vaults = data.get("vaults")
        if not isinstance(vaults, dict):
            raise APIConnectionError("Backend returned invalid encrypted login index")
        for aid, envelope in vaults.items():
            if (not isinstance(aid, str) or not _ACCOUNT_ID.fullmatch(aid)
                    or not isinstance(envelope, dict)
                    or set(envelope) != {"version", "nonce", "ciphertext"}
                    or type(envelope.get("version")) is not int or envelope["version"] != 1
                    or not all(isinstance(envelope.get(key), str)
                               and len(envelope[key]) <= 6000
                               for key in ("nonce", "ciphertext"))):
                raise APIConnectionError("Backend returned invalid encrypted login index")
        return vaults

    def store_login_vault(
        self, account_id: str, sealed: dict[str, object],
    ) -> bool:
        """Upload Mac-encrypted material, not a Gameforge password."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if (not isinstance(sealed, dict)
                or set(sealed) != {"version", "nonce", "ciphertext", "confirmed"}
                or sealed.get("confirmed") is not True
                or type(sealed.get("version")) is not int or sealed["version"] != 1
                or not all(isinstance(sealed.get(key), str)
                           and 0 < len(sealed[key]) <= 6000
                           for key in ("nonce", "ciphertext"))):
            raise ValueError("A valid encrypted login envelope is required")
        response = self._write(f"accounts/{account_id}/login-vault", sealed)
        return response.get("saved") is True

    def capabilities(self) -> dict[str, object]:
        data = self._read("capabilities")
        if not isinstance(data.get("operations"), list):
            raise APIConnectionError("Backend returned invalid operation registry")
        return data

    def monitor_existing_account(self, account_id: str, *, confirmed: bool) -> dict[str, object]:
        """Explicitly lease and verify one pre-existing engine session; never login."""
        if not _ACCOUNT_ID.fullmatch(account_id) or not confirmed:
            raise ValueError("Valid account and separate monitoring confirmation required")
        result = self._write(f"accounts/{account_id}/monitor", {"confirmed": True})
        if result.get("account_id") != account_id or result.get("status") != "monitoring_existing_session":
            raise APIConnectionError("Backend returned an invalid monitoring receipt")
        return result

    def pending_assistance(self) -> dict[str, object]:
        """Only current nonsecret waiting tickets; old servers are read-only."""
        try:
            result = self._read("auth-assistance/pending")
        except APIConnectionError as exc:
            if exc.status_code == 404:
                return {"enabled": False, "tickets": []}
            raise
        if result.get("enabled") is False and result.get("tickets") == []:
            return result
        if result.get("enabled") is not True or not isinstance(result.get("tickets"), list):
            raise APIConnectionError("Backend returned invalid assistance notification data")
        tickets = result["tickets"]
        if len(tickets) > 256:
            raise APIConnectionError("Backend returned excessive assistance notifications")
        for ticket in tickets:
            if not isinstance(ticket, dict) or set(ticket) != {
                "account_id", "ticket_id", "reason", "state"
            }:
                raise APIConnectionError("Backend returned invalid assistance notification")
            if (
                not isinstance(ticket["account_id"], str)
                or not _ACCOUNT_ID.fullmatch(ticket["account_id"])
                or not isinstance(ticket["ticket_id"], str)
                or not re.fullmatch(r"[a-f0-9-]{36}", ticket["ticket_id"])
                or ticket["reason"] not in {"session_expired", "login_required", "manual_challenge"}
                or ticket["state"] != "waiting_operator"
            ):
                raise APIConnectionError("Backend returned invalid assistance notification")
        return result

    def auth_assistance(self, account_id: str) -> dict[str, object]:
        """Read only nonsecret help reason/status; never transfer session data."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        try:
            response = self._read(f"accounts/{account_id}/auth-assistance")
        except APIConnectionError as exc:
            if exc.status_code == 404:
                return {"enabled": False, "account_id": account_id, "ticket": None}
            raise
        if response.get("enabled") is True:
            ticket = response.get("ticket")
            if ticket is not None and (
                not isinstance(ticket, dict)
                or not isinstance(ticket.get("ticket_id"), str)
                or not isinstance(ticket.get("state"), str)
                or not isinstance(ticket.get("reason"), str)
            ):
                raise APIConnectionError("Backend returned invalid assistance status")
        return response

    def approve_auth_assistance(
        self, account_id: str, ticket_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        if not confirmed or not isinstance(ticket_id, str):
            raise ValueError("Explicit confirmation and valid ticket are required")
        import uuid

        try:
            uuid.UUID(ticket_id)
        except ValueError as exc:
            raise ValueError("Invalid assistance ticket") from exc
        return self._write(f"accounts/{account_id}/auth-assistance/{ticket_id}/approve", {
            "confirmed": True,
        })

    def native_browser_login_capabilities(self) -> dict[str, object]:
        try:
            response = self._read("native-browser-login")
        except APIConnectionError as exc:
            if exc.status_code == 404:
                return {"enabled": False, "mode": "unavailable"}
            raise
        if (type(response.get("enabled")) is not bool or
                response.get("mode") != "mac_ephemeral_encrypted"):
            raise APIConnectionError("Backend native browser capability is invalid")
        return response

    def start_native_browser_login(
        self, account_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or confirmed is not True:
            raise ValueError("Exact account and explicit Mac browser approval required")
        response = self._write(f"accounts/{account_id}/browser-login/start", {
            "confirmed": True,
        })
        if (
            response.get("status") != "browser_login_ready"
            or response.get("account_id") != account_id
            or not isinstance(response.get("world"), str)
            or not re.fullmatch(r"s[0-9]{1,6}-[a-z]{2,4}", response["world"])
            or not isinstance(response.get("ticket_id"), str)
            or not re.fullmatch(r"[0-9a-f-]{36}", response["ticket_id"])
            or not isinstance(response.get("public_key"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{42,44}", response["public_key"])
            or not isinstance(response.get("expires_in_seconds"), int)
            or not 60 <= response["expires_in_seconds"] <= 900
        ):
            raise APIConnectionError("Backend native browser challenge is malformed")
        return response

    def finish_native_browser_login(
        self, account_id: str, ticket_id: str, envelope: dict[str, object],
    ) -> dict[str, str]:
        if (not _ACCOUNT_ID.fullmatch(account_id)
                or not re.fullmatch(r"[0-9a-f-]{36}", ticket_id)
                or set(envelope) != {"confirmed", "client_key", "nonce", "ciphertext"}
                or envelope.get("confirmed") is not True
                or any(not isinstance(envelope.get(key), str)
                       for key in ("client_key", "nonce", "ciphertext"))):
            raise ValueError("A valid encrypted and confirmed handoff is required")
        reply = self._write(
            f"accounts/{account_id}/browser-login/{ticket_id}/complete", envelope,
        )
        if (reply.get("account_id") != account_id
                or reply.get("status") not in {
                    "world_cookie_bound", "worker_recovered_verified",
                    "worker_started_verified",
                }):
            raise APIConnectionError("Browser login did not receive a verified server receipt")
        return reply

    def cancel_native_browser_login(
        self, account_id: str, ticket_id: str,
    ) -> dict[str, object]:
        if (not _ACCOUNT_ID.fullmatch(account_id)
                or not re.fullmatch(r"[0-9a-f-]{36}", ticket_id)):
            raise ValueError("Invalid browser login cancellation")
        return self._write(
            f"accounts/{account_id}/browser-login/{ticket_id}/cancel",
            {"confirmed": True},
        )

    def recovery_guide(self, account_id: str) -> dict[str, object]:
        """Read only strictly typed host-local recovery metadata, never secrets."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        try:
            guide = self._read(f"accounts/{account_id}/recovery-guide")
        except APIConnectionError as exc:
            if exc.status_code == 404:
                return {
                    "enabled": False, "account_id": account_id,
                    "mode": "host_local_only",
                    "requires_trusted_host_session": True,
                    "allow_http_cookie_transfer": False,
                    "dedicated_rebind_supported": False,
                    "session_status": "not_connected", "ticket": None,
                }
            raise
        if (
            guide.get("account_id") != account_id
            or type(guide.get("enabled")) is not bool
            or guide.get("mode") != "host_local_only"
            or guide.get("requires_trusted_host_session") is not True
            or guide.get("allow_http_cookie_transfer") is not False
            or type(guide.get("dedicated_rebind_supported")) is not bool
            or guide.get("session_status") not in {
                "not_connected", "validating_session", "authenticated",
                "needs_assistance", "assisted_login", "validating_handoff",
                "paused", "failed",
            }
        ):
            raise APIConnectionError("Untrusted or invalid host-local recovery metadata")
        ticket = guide.get("ticket")
        if ticket is not None and (
            not isinstance(ticket, dict)
            or set(ticket) != {"ticket_id", "reason", "state"}
            or not isinstance(ticket["ticket_id"], str)
            or not re.fullmatch(r"[0-9a-f-]{36}", ticket["ticket_id"])
            or ticket["reason"] not in {
                "session_expired", "login_required", "manual_challenge",
            }
            or ticket["state"] not in {
                "waiting_operator", "operator_ready", "validating_session",
                "verified_by_worker", "retry_required", "expired",
            }
        ):
            raise APIConnectionError("Invalid recovery assistance ticket")
        return guide

    def prepare_dedicated_recovery(
        self, account_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or not confirmed:
            raise ValueError("Exact account and separate preparation consent required")
        receipt = self._write(
            f"accounts/{account_id}/recovery/prepare", {"confirmed": True},
        )
        ticket = receipt.get("ticket")
        if (
            receipt.get("account_id") != account_id
            or receipt.get("status") != "manual_recovery_prepared"
            or not isinstance(ticket, dict)
            or ticket.get("state") != "waiting_operator"
            or not isinstance(ticket.get("ticket_id"), str)
            or not re.fullmatch(r"[a-f0-9-]{36}", ticket["ticket_id"])
        ):
            raise APIConnectionError("Backend did not prepare a safe dedicated recovery")
        return receipt

    def rebind_dedicated_worker(
        self, account_id: str, ticket_id: str, *, confirmed: bool,
    ) -> dict[str, object]:
        """Only approve a SAME-HOST staged rebind; no cookie/body arguments."""
        if not _ACCOUNT_ID.fullmatch(account_id) or not confirmed:
            raise ValueError("Exact account and separate operator consent required")
        import uuid

        try:
            if str(uuid.UUID(ticket_id)) != ticket_id:
                raise ValueError("Invalid recovery ticket")
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Invalid recovery ticket") from exc
        receipt = self._write(
            f"accounts/{account_id}/recovery/{ticket_id}/rebind-worker",
            {"confirmed": True},
        )
        if (
            receipt.get("account_id") != account_id
            or receipt.get("status") != "worker_recovered_verified"
        ):
            raise APIConnectionError("Backend did not verify the recovered worker")
        return receipt

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

    def shipment_preview(self, account_id: str, draft: dict[str, object]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        clean = validated_shipment_draft(draft)
        result = self._write(f"accounts/{account_id}/shipment-plan", clean)
        if result.get("account_id") != account_id:
            raise APIConnectionError("Shipment scope mismatch")
        try:
            validate_shipment_plan(clean, result)
        except ValueError as exc:
            raise APIConnectionError("Invalid shipment preview") from exc
        if result["ready"] and (not isinstance(result.get("preview_id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{43}", result["preview_id"])
                or type(result.get("expires_in")) is not int or not 1 <= result["expires_in"] <= 120):
            raise APIConnectionError("Invalid shipment review")
        return {**result, "draft": clean}

    def island_destinations(self, account_id: str, x: int, y: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        validated_coordinates(x, y)
        data = self._read(f"accounts/{account_id}/island-destinations?x={x}&y={y}")
        if data.get("account_id") != account_id:
            raise APIConnectionError("Invalid island scope")
        try:
            return {"account_id": account_id, "x": x, "y": y,
                    "cities": validate_island_destinations(x, y, data)}
        except ValueError as exc:
            raise APIConnectionError("Invalid island inventory") from exc

    def vacation_preview(self, account_id: str, city_id: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid vacation scope")
        data = self._write(f"accounts/{account_id}/cities/{city_id}/vacation-plan", {})
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or not isinstance(data.get("city_name"), str)
                or type(data.get("active_jobs")) is not int or not 0 <= data["active_jobs"] <= 10000
                or any(type(data.get(k)) is not bool for k in ("managed_active", "recovery_disabled", "ready"))
                or data["ready"] is not (not data["active_jobs"] and not data["managed_active"]
                                         and data["recovery_disabled"])
                or (data["ready"] and (not isinstance(data.get("preview_id"), str)
                                       or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                                       or type(data.get("expires_in")) is not int
                                       or not 1 <= data["expires_in"] <= 120))):
            raise APIConnectionError("Invalid vacation preview")
        return data

    def attack_inventory(self, account_id: str, city_id: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid troop inventory scope")
        data = self._read(f"accounts/{account_id}/cities/{city_id}/attack-options")
        if data.get("account_id") != account_id:
            raise APIConnectionError("Troop inventory scope mismatch")
        try:
            return {"account_id": account_id, **validate_attack_inventory(city_id, data)}
        except ValueError as exc:
            raise APIConnectionError("Invalid troop inventory") from exc

    def attack_preview(self, account_id: str, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        clean = validated_attack_draft(city_id, draft)
        data = self._write(f"accounts/{account_id}/cities/{city_id}/attack-plan", clean)
        if data.get("account_id") != account_id:
            raise APIConnectionError("Manual attack preview scope mismatch")
        try:
            validate_attack_plan(city_id, clean, {**data, "config": {
                "city_id": city_id, **clean, "expected": "0" * 64,
            }})
        except ValueError as exc:
            raise APIConnectionError("Invalid manual attack preview") from exc
        if data["ready"] and (not isinstance(data.get("preview_id"), str)
                              or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                              or type(data.get("expires_in")) is not int
                              or not 1 <= data["expires_in"] <= 120):
            raise APIConnectionError("Invalid manual attack ticket")
        # Internal correlation only; the user sees named wave summaries.
        return {**data, "reviewed_waves": clean["waves"]}

    def grind_preview(self, account_id: str, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        clean = validated_grind_draft(city_id, draft)
        data = self._write(f"accounts/{account_id}/cities/{city_id}/grind-plan", clean)
        if data.get("account_id") != account_id:
            raise APIConnectionError("Automatic attack preview scope mismatch")
        try:
            # Validate display data without exposing the internal fingerprint to the GUI.
            validate_grind_plan(city_id, clean, {**data, "config": {
                "city_id": city_id, **clean, "expected": "0" * 64,
            }})
        except ValueError as exc:
            raise APIConnectionError("Invalid automatic attack preview") from exc
        if data["ready"] and (not isinstance(data.get("preview_id"), str)
                              or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                              or type(data.get("expires_in")) is not int
                              or not 1 <= data["expires_in"] <= 120):
            raise APIConnectionError("Invalid automatic attack ticket")
        return data

    def station_preview(self, account_id: str, city_id: int, draft: dict[str, object]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        clean = validated_station_draft(city_id, draft)
        data = self._write(f"accounts/{account_id}/cities/{city_id}/station-plan", clean)
        from daedalus.reviewed_operations import validate_station_observation

        try:
            if data.get("account_id") != account_id:
                raise ValueError("Invalid account scope")
            validate_station_observation(city_id, clean, data)
            if data["ready"] and (not isinstance(data.get("preview_id"), str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                    or type(data.get("expires_in")) is not int or not 1 <= data["expires_in"] <= 120):
                raise ValueError("Invalid deployment ticket")
        except ValueError as exc:
            raise APIConnectionError("Invalid deployment preview") from exc
        return data

    def build_options(self, account_id: str, city_id: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid building inventory scope")
        data = self._read(f"accounts/{account_id}/cities/{city_id}/build-options")
        if data.get("account_id") != account_id:
            raise APIConnectionError("Building inventory scope mismatch")
        try:
            return {"account_id": account_id, **validate_build_inventory(city_id, data)}
        except ValueError as exc:
            raise APIConnectionError("Invalid building inventory") from exc

    def build_preview(self, account_id: str, city_id: int, draft: dict[str, int]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid building review scope")
        clean = validated_build_draft(draft)
        data = self._write(f"accounts/{account_id}/cities/{city_id}/build-plan", clean)
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or any(data.get(k) != v for k, v in clean.items())
                or not isinstance(data.get("name"), str) or type(data.get("ready")) is not bool
                or any(not isinstance(data.get(k), list) or len(data[k]) != 5
                       or any(type(n) is not int or not 0 <= n <= 10**15 for n in data[k])
                       for k in ("costs", "available", "missing"))
                or (data["ready"] and (not isinstance(data.get("preview_id"), str)
                                       or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                                       or type(data.get("expires_in")) is not int
                                       or not 1 <= data["expires_in"] <= 120))):
            raise APIConnectionError("Invalid building preview")
        return data

    def layout_preview(self, account_id: str, city_id: int, template_city_id: int) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        template = validated_layout_draft(city_id, {"template_city_id": template_city_id})
        data = self._write(f"accounts/{account_id}/cities/{city_id}/layout-plan",
                           {"template_city_id": template})
        moves = data.get("moves")
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or data.get("template_city_id") != template
                or not isinstance(moves, list) or len(moves) > 80
                or any(not isinstance(m, dict) or set(m) != {"from", "to", "building", "displaced"}
                       or any(type(m[k]) is not int or not 0 <= m[k] <= 80 for k in ("from", "to"))
                       or any(not isinstance(m[k], str) or not 0 < len(m[k]) <= 64
                              for k in ("building", "displaced")) for m in moves)
                or any(not isinstance(data.get(k), str) for k in ("city_name", "template_name"))
                or data.get("ready") is not bool(moves)
                or (moves and (not isinstance(data.get("preview_id"), str)
                               or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                               or type(data.get("expires_in")) is not int
                               or not 1 <= data["expires_in"] <= 120))):
            raise APIConnectionError("Backend returned invalid layout preview")
        return data

    def worker_preview(self, account_id: str, city_id: int, task: str,
                       draft: dict[str, object]) -> dict[str, object]:
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or not 0 < city_id < 10**12:
            raise ValueError("Invalid worker city")
        clean = validated_worker_draft(task, draft)
        data = self._write(f"accounts/{account_id}/cities/{city_id}/worker-plan",
                           {"task": task, "draft": clean})
        from daedalus.reviewed_operations import validate_worker_observation

        try:
            if data.get("account_id") != account_id:
                raise ValueError("Invalid account scope")
            validate_worker_observation(task, city_id, clean, data)
            if (not isinstance(data.get("preview_id"), str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                    or type(data.get("expires_in")) is not int or not 1 <= data["expires_in"] <= 120):
                raise ValueError("Invalid worker ticket")
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid worker preview") from exc
        return data

    def donation_preview(self, account_id: str, city_id: int,
                         project: str, amount: int) -> dict[str, object]:
        if (not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int
                or not 0 < city_id < 10**12 or project not in ("resource", "tradegood")
                or type(amount) is not int or not 1 <= amount <= 10**9):
            raise ValueError("Invalid donation draft")
        data = self._write(f"accounts/{account_id}/cities/{city_id}/donation-plan",
                           {"project": project, "amount": amount})
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or data.get("project") != project or data.get("amount") != amount
                or type(data.get("ready")) is not bool
                or type(data.get("upgrading")) is not bool
                or any(type(data.get(k)) is not int or data[k] < 0
                       for k in ("level", "stock", "remaining"))
                or any(not isinstance(data.get(k), str) for k in ("city_name", "project_name"))
                or (data["ready"] and (not isinstance(data.get("preview_id"), str)
                                       or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                                       or type(data.get("expires_in")) is not int
                                       or not 1 <= data["expires_in"] <= 120))):
            raise APIConnectionError("Backend returned invalid donation preview")
        return data

    def construction_preview(
        self, account_id: str, city_id: int, upgrades: list[dict[str, int]],
        *, supply: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Ask the existing IkaBot worker for a read-only, account-scoped plan."""
        if (not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int
                or not 0 < city_id < 10**12 or not isinstance(upgrades, list)
                or not 0 < len(upgrades) <= 12):
            raise ValueError("Invalid construction preview scope")
        for upgrade in upgrades:
            if (not isinstance(upgrade, dict)
                    or set(upgrade) != {"position", "target_level"}
                    or type(upgrade["position"]) is not int
                    or type(upgrade["target_level"]) is not int):
                raise ValueError("Invalid construction preview target")
        from daedalus.reviewed_operations import (
            validate_construction_supply,
            validated_construction_supply,
        )

        if supply is not None:
            supply = validated_construction_supply(city_id, supply)
        data = self._write(
            f"accounts/{account_id}/cities/{city_id}/construction-preview",
            {"upgrades": upgrades, **({"supply": supply} if supply is not None else {})},
        )
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or type(data.get("ready")) is not bool
                or not isinstance(data.get("config"), dict)
                or any(not isinstance(data.get(name), list)
                       or len(data[name]) != 5 for name in ("costs", "missing", "available"))
                or type(data.get("estimated_seconds")) is not int):
            raise APIConnectionError("Backend returned an invalid construction preview")
        if supply is not None:
            try:
                validate_construction_supply(city_id, supply, data, data, data["config"])
            except (ValueError, KeyError, TypeError) as exc:
                raise APIConnectionError("Invalid construction supply preview") from exc
            if data["ready"] and (not isinstance(data.get("preview_id"), str)
                                   or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
                                   or type(data.get("expires_in")) is not int or not 1 <= data["expires_in"] <= 120):
                raise APIConnectionError("Invalid construction supply ticket")
        return data

    def workshop_upgrades(self, account_id: str, city_id: int) -> dict[str, object]:
        """Fetch only real, account-bound workshop options for a city."""
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or city_id <= 0:
            raise ValueError("Invalid workshop scope")
        data = self._read(f"accounts/{account_id}/cities/{city_id}/workshop-upgrades")
        choices = data.get("upgrades")
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or not isinstance(choices, list) or len(choices) > 250
                or type(data.get("workshop_level")) is not int
                or any(not isinstance(choice, dict) for choice in choices)):
            raise APIConnectionError("Backend returned invalid workshop options")
        return data

    def training_preview(self, account_id: str, draft: dict[str, object]) -> dict[str, object]:
        from daedalus.training_contract import training_draft, validate_training_review

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        clean = training_draft(draft)
        data = self._write(f"accounts/{account_id}/cities/{clean['city_ids'][0]}/training-plan", clean)
        try:
            validate_training_review(account_id, clean, data)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise APIConnectionError("Invalid recruitment review") from exc
        return data

    def trainable_units(
        self, account_id: str, city_id: int, *, train_troops: bool,
    ) -> dict[str, object]:
        """Read only actual trainable troop/ship types and source-provided costs."""
        if (not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int
                or city_id <= 0 or type(train_troops) is not bool):
            raise ValueError("Invalid training unit scope")
        mode = "true" if train_troops else "false"
        data = self._read(
            f"accounts/{account_id}/cities/{city_id}/trainable-units?train_troops={mode}"
        )
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or data.get("train_troops") is not train_troops
                or not isinstance(data.get("city"), dict)
                or not isinstance(data.get("units"), list)
                or not isinstance(data.get("available"), list)
                or len(data["available"]) != 5
                or type(data.get("free_citizens")) is not int):
            raise APIConnectionError("Backend returned invalid trainable unit options")
        return data

    def market_quotes(
        self, account_id: str, city_id: int, resource_type: int, side: str,
    ) -> dict[str, object]:
        """Read live offer rows without placing a trade or exposing auth state."""
        if (not _ACCOUNT_ID.fullmatch(account_id)
                or type(city_id) is not int or not 0 < city_id < 10**12
                or type(resource_type) is not int or not 0 <= resource_type <= 4
                or side not in {"buy", "sell_to_offers", "create_offer"}):
            raise ValueError("Invalid market choice")
        result = self._read(
            f"accounts/{account_id}/cities/{city_id}/market-quotes"
            f"?resource_type={resource_type}&side={side}"
        )
        if (result.get("account_id") != account_id
                or result.get("city_id") != city_id
                or result.get("resource_type") != resource_type
                or result.get("side") != side
                or not isinstance(result.get("city"), dict)
                or not isinstance(result.get("offers"), list)):
            raise APIConnectionError("Backend returned invalid market quotes")
        return result

    def academies(self, account_id: str) -> dict[str, object]:
        """Fetch only verified academy and cooldown rows from the selected account."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account for academy research")
        result = self._read(f"accounts/{account_id}/academies")
        if (result.get("account_id") != account_id
                or not isinstance(result.get("academies"), list)
                or len(result["academies"]) > 100
                or any(not isinstance(row, dict) for row in result["academies"])):
            raise APIConnectionError("Backend returned invalid academy research inventory")
        from daedalus.research_choices import validate_studies

        try:
            if "studies" in result:
                result["studies"] = validate_studies(result["studies"])
        except ValueError:
            raise APIConnectionError("Invalid research advisor inventory") from None
        return result

    def taverns(self, account_id: str) -> dict[str, object]:
        """Fetch verified wine and tavern state from one selected game account."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account for tavern management")
        result = self._read(f"accounts/{account_id}/taverns")
        if (result.get("account_id") != account_id
                or not isinstance(result.get("taverns"), list)
                or len(result["taverns"]) > 100
                or any(not isinstance(row, dict) for row in result["taverns"])):
            raise APIConnectionError("Backend returned an invalid tavern inventory")
        return result

    def miracles(self, account_id: str) -> dict[str, object]:
        """Fetch real temples and wonder cooldowns for one account only."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account for wonder inventory")
        result = self._read(f"accounts/{account_id}/miracles")
        if (result.get("account_id") != account_id
                or not isinstance(result.get("miracles"), list)
                or len(result["miracles"]) > 100
                or any(not isinstance(item, dict) for item in result["miracles"])):
            raise APIConnectionError("Backend returned invalid wonder inventory")
        return result

    def configure_notification(self, account_id: str, provider: str,
                               settings: dict[str, object]) -> dict[str, object]:
        from daedalus.notification_settings import (
            PROVIDERS,
            seal_notification_settings,
            validate_receipt,
        )

        if not _ACCOUNT_ID.fullmatch(account_id) or provider not in PROVIDERS:
            raise ValueError("Invalid provider scope")
        path = f"accounts/{account_id}/notifications/{provider}"
        try:
            challenge = self._write(path + "/begin", {"confirmed_global": True})
            envelope = seal_notification_settings(challenge, account_id, provider, settings)
            receipt = self._write(path + "/complete", envelope)
            return validate_receipt(receipt, account_id, provider)
        except (ValueError, APIConnectionError):
            raise APIConnectionError("Provider configuration unavailable or outcome uncertain") from None

    def proxy_profiles(self, account_id: str, draft=None):
        from daedalus.proxy_profiles import validate_proxy_draft, validate_proxy_result

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        path = f"accounts/{account_id}/proxy-settings"
        result = self._read(path) if draft is None else self._write(path, validate_proxy_draft(draft))
        try:
            return validate_proxy_result(result, account_id, draft)
        except ValueError:
            raise APIConnectionError("Invalid network profile result") from None

    def challenge_policy(self, account_id: str, draft=None):
        from daedalus.challenge_policy import (
            validate_challenge_policy,
            validate_challenge_policy_draft,
        )

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        path = f"accounts/{account_id}/challenge-policy"
        result = self._read(path) if draft is None else self._write(path, validate_challenge_policy_draft(draft))
        try:
            return validate_challenge_policy(result, account_id)
        except ValueError:
            raise APIConnectionError("Invalid human challenge policy") from None

    def extension_settings(self, account_id: str, draft=None):
        from daedalus.extension_settings import validate_extension_draft, validate_extension_status

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        path = f"accounts/{account_id}/extensions"
        result = self._read(path) if draft is None else self._write(path, validate_extension_draft(draft))
        try:
            return validate_extension_status(result, account_id)
        except ValueError:
            raise APIConnectionError("Invalid extension status") from None

    def world_reports(self, account_id: str, report_id=None):
        from daedalus.world_reports import REPORT_ID, collect_report, validate_world_reports

        if not _ACCOUNT_ID.fullmatch(account_id) or (report_id is not None and
                (not isinstance(report_id, str) or not REPORT_ID.fullmatch(report_id))):
            raise ValueError("Invalid map report scope")
        path = f"accounts/{account_id}/world-reports"
        try:
            if report_id is None:
                return validate_world_reports(self._read(path), account_id)
            return collect_report(lambda offset: self._read(f"{path}/{report_id}?offset={offset}"),
                                  account_id, report_id)
        except ValueError:
            raise APIConnectionError("Invalid aggregate map report") from None

    def administrative_status(self, account_id: str) -> dict[str, object]:
        from daedalus.admin_status import validate_admin_status

        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account")
        result = self._read(f"accounts/{account_id}/administrative-status")
        try:
            if result.get("account_id") != account_id:
                raise ValueError("Account changed")
            return {"account_id": account_id,
                    "settings": validate_admin_status(result.get("settings"))}
        except ValueError as exc:
            raise APIConnectionError("Backend returned invalid administrative status") from exc

    def shrine_status(self, account_id: str) -> dict[str, object]:
        """Read actual Olympus shrine, preserving unknown favour as unknown."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account for shrine status")
        result = self._read(f"accounts/{account_id}/shrine-status")
        if (result.get("account_id") != account_id
                or (result.get("shrine") is not None
                    and not isinstance(result.get("shrine"), dict))):
            raise APIConnectionError("Backend returned invalid shrine status")
        return result

    def pirate_fortresses(self, account_id: str) -> dict[str, object]:
        """Fetch actual owned fortress mission levels, no game interaction."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account for piracy inventory")
        result = self._read(f"accounts/{account_id}/pirate-fortresses")
        if (result.get("account_id") != account_id
                or not isinstance(result.get("fortresses"), list)
                or len(result["fortresses"]) > 100
                or any(not isinstance(row, dict) for row in result["fortresses"])):
            raise APIConnectionError("Backend returned invalid pirate fortress inventory")
        return result

    def military_overview(self, account_id: str) -> dict[str, object]:
        """Read actual troops/fleets for one account, never start a task."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid military account")
        data = self._read(f"accounts/{account_id}/military")
        if (data.get("account_id") != account_id
                or not isinstance(data.get("cities"), list)
                or len(data["cities"]) > 100
                or type(data.get("observed_at")) is not int):
            raise APIConnectionError("Invalid military overview response")
        return data

    def ship_movements(self, account_id: str) -> dict[str, object]:
        """Read sanitized movement rows for one account, never send ships."""
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid movement account")
        data = self._read(f"accounts/{account_id}/ship-movements")
        if (data.get("account_id") != account_id
                or not isinstance(data.get("movements"), list)
                or len(data["movements"]) > 250
                or type(data.get("observed_at")) is not int):
            raise APIConnectionError("Invalid ship movements response")
        return data

    def buildings(self, account_id: str, city_id: int) -> list[dict[str, object]]:
        """Read sanitized, account-scoped real building rows; never a task launch."""
        if not _ACCOUNT_ID.fullmatch(account_id) or type(city_id) is not int or city_id <= 0:
            raise ValueError("Invalid building inventory scope")
        data = self._read(f"accounts/{account_id}/cities/{city_id}/buildings")
        rows = data.get("buildings")
        if (data.get("account_id") != account_id or data.get("city_id") != city_id
                or not isinstance(rows, list)
                or data.get("available") is not True
                or not all(isinstance(row, dict) for row in rows)):
            raise APIConnectionError("Backend building inventory unavailable")
        return rows

    def warehouses(self, account_id: str) -> list[dict[str, object]]:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("Invalid account ID")
        data = self._read(f"warehouses/{account_id}").get("cities")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise APIConnectionError("Backend returned invalid warehouse snapshots")
        return data
