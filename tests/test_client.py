"""Read-only HTTP client tests using mock transport; no socket is opened."""

from __future__ import annotations

import json

import httpx
import pytest

from daedalus.client import APIConnectionError, DaedalusClient

TOKEN = "x" * 48


def mock_client(handler) -> DaedalusClient:
    return DaedalusClient(
        "http://127.0.0.1:8765",
        TOKEN,
        transport=httpx.MockTransport(handler),
    )


def test_client_uses_bearer_auth_and_returns_account_metadata():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        return httpx.Response(
            200,
            json={"accounts": [{"id": "alpha", "world": "s301-en", "session_status": "not_connected"}]},
        )

    with mock_client(handler) as client:
        accounts = client.accounts()
        assert accounts[0]["id"] == "alpha"
    assert seen == [("GET", "/api/v1/accounts", f"Bearer {TOKEN}")]


def test_client_supports_capability_and_warehouse_calls():
    def handler(request):
        if request.url.path == "/api/v1/capabilities":
            return httpx.Response(200, json={"operations": [], "structured_engine_dispatch": False})
        if request.url.path == "/api/v1/warehouses/alpha":
            return httpx.Response(200, json={"account_id": "alpha", "cities": []})
        if request.url.path == "/api/v1/accounts/alpha/session":
            return httpx.Response(200, json={"account_id": "alpha", "session_status": "paused"})
        return httpx.Response(404)

    client = mock_client(handler)
    assert client.capabilities()["structured_engine_dispatch"] is False
    assert client.warehouses("alpha") == []
    assert client.account_session("alpha")["session_status"] == "paused"
    client.close()


def test_http_errors_hide_server_body_and_token():
    secret_text = "private-game-cookie-should-never-be-logged"

    def handler(_request):
        return httpx.Response(503, text=secret_text)

    client = mock_client(handler)
    with pytest.raises(APIConnectionError, match="not available") as error:
        client.warehouses("alpha")
    assert error.value.status_code == 503
    assert secret_text not in str(error.value)
    assert TOKEN not in repr(client)
    client.close()


def test_untrusted_insecure_http_endpoints_rejected():
    for server in (
        "http://myserver.example",
        "http://localhost.evil.example",
        "http://192.168.1.5:8765",
        "ftp://127.0.0.1",
        "http://token:secret@localhost:8765",
        "http://localhost:8765/?token=secret",
        "http://localhost:8765/api",
    ):
        with pytest.raises(ValueError):
            DaedalusClient(server, TOKEN)


def test_https_endpoint_and_ipv6_loopback_allowed():
    client = DaedalusClient(
        "https://example.org",
        TOKEN,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"service": "daedalus"})),
    )
    assert client.health()["service"] == "daedalus"
    client.close()
    client = DaedalusClient(
        "http://[::1]:8765",
        TOKEN,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"service": "daedalus"})),
    )
    assert client.health()["service"] == "daedalus"
    client.close()


def test_bad_json_and_shape_return_safe_errors():
    for payload in ("not json", json.dumps(["not-object"]), json.dumps({"accounts": "oops"})):
        client = mock_client(lambda _request, content=payload: httpx.Response(200, text=content))
        with pytest.raises(APIConnectionError):
            client.accounts()
        client.close()


def test_client_rejects_bad_account_id_before_network():
    client = mock_client(lambda request: (_ for _ in ()).throw(AssertionError("network called")))
    with pytest.raises(ValueError, match="Invalid account ID"):
        client.warehouses("../invalid")
    with pytest.raises(ValueError, match="Invalid account ID"):
        client.account_session("A")
    client.close()


def test_client_refuses_short_or_control_character_token():
    for token in ("short", "x" * 32 + "\n"):
        with pytest.raises(ValueError):
            DaedalusClient("http://localhost:8765", token)


def test_readonly_desktop_client_attached_engine_cities():
    def handler(request):
        if request.url.path == "/api/v1/engine/connected-accounts":
            return httpx.Response(200, json={"connected_account_ids": ["alpha"]})
        if request.url.path == "/api/v1/accounts/alpha/cities":
            return httpx.Response(200, json={"account_id": "alpha", "cities": [
                {"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}
            ]})
        return httpx.Response(404)

    with mock_client(handler) as client:
        assert client.connected_accounts() == ["alpha"]
        assert client.cities("alpha")[0]["name"] == "Athens"
        with pytest.raises(ValueError):
            client.cities("../invalid")


def test_desktop_start_list_stop_use_bearer_and_scoped_json():
    task_id = "f" * 24
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.url.path.endswith("/task-control"):
            return httpx.Response(200, json={"enabled": True, "requires_existing_session": True})
        if request.method == "POST" and request.url.path.endswith("/tasks"):
            payload = json.loads(request.content)
            assert payload == {
                "task": "alertAttacks", "config": {"minutes": 10},
                "request_id": "12345678-1234-4123-8123-123456789abc",
                "confirmed": True,
            }
            return httpx.Response(200, json={"task_id": task_id, "pid": 81001, "status": "started"})
        if request.method == "GET":
            return httpx.Response(200, json={
                "engine_tasks": [{"task_id": task_id, "task": "alertAttacks", "status": "running"}],
                "requests": [],
            })
        if request.method == "POST" and request.url.path.endswith("/stop"):
            return httpx.Response(200, json={"task_id": task_id, "status": "stopped"})
        return httpx.Response(404)

    with mock_client(handler) as client:
        assert client.task_control_status()["enabled"]
        started = client.start_task(
            "alpha", "alertAttacks", {"minutes": 10},
            "12345678-1234-4123-8123-123456789abc", confirmed=True,
        )
        assert started["task_id"] == task_id
        assert client.tasks("alpha")["engine_tasks"][0]["task_id"] == task_id
        assert client.stop_task("alpha", task_id)["status"] == "stopped"
    assert [entry[0] for entry in seen] == ["GET", "POST", "GET", "POST"]
    assert all(entry[2] == f"Bearer {TOKEN}" for entry in seen)
    assert seen[1][1] == "/api/v1/accounts/alpha/tasks"


def test_desktop_task_errors_redact_server_replies():
    body = "sensitive-cookie-do-not-display"
    with mock_client(lambda request: httpx.Response(503, text=body)) as client:
        with pytest.raises(APIConnectionError) as error:
            client.start_task("alpha", "alertAttacks", {},
                              request_id="12345678-1234-4123-8123-123456789abc", confirmed=True)
        assert body not in str(error.value)
        assert error.value.status_code == 503
        with pytest.raises(ValueError):
            client.stop_task("alpha", "-1")


def test_account_config_client_uses_authorized_revision_and_confirmation():
    import hashlib

    revision = hashlib.sha256(b"synthetic").hexdigest()
    rows = [{"id": "alpha", "world": "s301-en", "player": "Example",
             "label": "Example", "enabled": True}]
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.method == "GET":
            return httpx.Response(200, json={
                "enabled": True, "revision": revision, "accounts": rows,
            })
        assert json.loads(request.content) == {
            "revision": revision, "accounts": rows, "confirmed": True,
        }
        return httpx.Response(200, json={
            "enabled": True, "revision": "a" * 64, "accounts": rows,
        })

    with mock_client(handler) as client:
        assert client.account_config()["revision"] == revision
        assert client.replace_account_config(revision, rows, confirmed=True)["revision"] == "a" * 64
        with pytest.raises(ValueError):
            client.replace_account_config(revision, rows, confirmed=False)
    assert [method for method, _, _ in seen] == ["GET", "PUT"]
    assert all(token == f"Bearer {TOKEN}" for _, _, token in seen)


def test_account_editing_client_recognizes_old_backend_and_redacts_rejection():
    secret = "cookie-private-should-not-appear"

    def handler(request):
        if request.method == "GET":
            return httpx.Response(404, text=secret)
        return httpx.Response(409, text=secret)

    with mock_client(handler) as client:
        assert client.account_config()["enabled"] is False
        with pytest.raises(APIConnectionError) as error:
            client.replace_account_config("a" * 64, [], confirmed=True)
        assert error.value.status_code == 409
        assert secret not in str(error.value)


def test_assistance_client_reads_nonsecret_status_and_confirms_only_manual_step():
    from uuid import uuid4

    ticket_id = str(uuid4())
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.method == "GET":
            return httpx.Response(200, json={"enabled": True, "account_id": "alpha", "ticket": {
                "ticket_id": ticket_id, "reason": "manual_challenge",
                "state": "waiting_operator",
            }})
        assert json.loads(request.content) == {"confirmed": True}
        return httpx.Response(200, json={"enabled": True, "account_id": "alpha", "ticket": {
            "ticket_id": ticket_id, "reason": "manual_challenge",
            "state": "operator_ready",
        }})

    with mock_client(handler) as client:
        assert client.auth_assistance("alpha")["ticket"]["reason"] == "manual_challenge"
        assert client.approve_auth_assistance("alpha", ticket_id, confirmed=True)["ticket"][
            "state"
        ] == "operator_ready"
        with pytest.raises(ValueError):
            client.approve_auth_assistance("alpha", ticket_id, confirmed=False)
        with pytest.raises(ValueError):
            client.approve_auth_assistance("alpha", "invalid", confirmed=True)
        with pytest.raises(ValueError):
            client.auth_assistance("../bad")
    assert [item[0] for item in seen] == ["GET", "POST"]
    assert all(item[2] == f"Bearer {TOKEN}" for item in seen)


def test_assistance_client_handles_unsupported_and_redacted_errors():
    secret = "private-session-cookie"

    def handler(request):
        return httpx.Response(404 if request.method == "GET" else 409, text=secret)

    with mock_client(handler) as client:
        assert client.auth_assistance("alpha")["enabled"] is False
        with pytest.raises(APIConnectionError) as error:
            client.approve_auth_assistance(
                "alpha", "12345678-1234-4123-8123-123456789abc", confirmed=True,
            )
        assert error.value.status_code == 409
        assert secret not in str(error.value)


def test_monitoring_client_uses_bearer_and_separate_confirmation():
    import uuid

    ticket_id = str(uuid.uuid4())
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.method == "GET":
            return httpx.Response(200, json={
                "enabled": True,
                "tickets": [{
                    "account_id": "alpha", "ticket_id": ticket_id,
                    "reason": "session_expired", "state": "waiting_operator",
                }],
            })
        assert json.loads(request.content) == {"confirmed": True}
        return httpx.Response(200, json={
            "account_id": "alpha", "status": "monitoring_existing_session",
        })

    with mock_client(handler) as client:
        assert client.pending_assistance()["tickets"][0]["ticket_id"] == ticket_id
        assert client.monitor_existing_account("alpha", confirmed=True)["status"] == (
            "monitoring_existing_session"
        )
        with pytest.raises(ValueError):
            client.monitor_existing_account("alpha", confirmed=False)
        with pytest.raises(ValueError):
            client.monitor_existing_account("../other", confirmed=True)
    assert [row[0] for row in seen] == ["GET", "POST"]
    assert all(row[2] == f"Bearer {TOKEN}" for row in seen)


def test_monitor_client_detects_cross_account_notifications_and_error_redacts():
    fake_secret = "private_game_cookie"

    def invalid(request):
        if request.method == "GET":
            return httpx.Response(200, json={
                "enabled": True, "tickets": [{
                    "account_id": "alpha", "ticket_id": fake_secret,
                    "reason": "session_expired", "state": "waiting_operator",
                }],
            })
        return httpx.Response(409, text=fake_secret)

    with mock_client(invalid) as client:
        with pytest.raises(APIConnectionError, match="invalid assistance notification"):
            client.pending_assistance()
        with pytest.raises(APIConnectionError) as err:
            client.monitor_existing_account("alpha", confirmed=True)
        assert err.value.status_code == 409
        assert fake_secret not in str(err.value)


def test_monitoring_client_graceful_fallback_on_older_backend():
    with mock_client(lambda _req: httpx.Response(404)) as client:
        assert client.pending_assistance() == {"enabled": False, "tickets": []}


def test_only_fixed_task_prerequisite_errors_are_shown_to_user():
    def respond(req):
        if req.method == "GET":
            return httpx.Response(200, json={"account_id": "alpha", "task": "alertAttacks",
                    "ready": False, "reason": "notifications_required", "checked": ["notifications"],
                    "unresolved_request": False})
        return httpx.Response(409, json={"detail":
            "Configure Telegram or Discord notifications before starting this alert"})
    with mock_client(respond) as client:
        assert client.task_preflight("alpha", "alertAttacks")["ready"] is False
        with pytest.raises(APIConnectionError, match="Configure Telegram or Discord"):
            client.start_task("alpha", "alertAttacks", {},
                "12345678-1234-4123-8123-123456789abc", confirmed=True)
    with mock_client(lambda _r: httpx.Response(409,json={"detail": "private-secret-cookie"})) as c:
        with pytest.raises(APIConnectionError) as err:
            c.start_task("alpha", "alertAttacks", {},
                "12345678-1234-4123-8123-123456789abc", confirmed=True)
        assert "private-secret" not in str(err.value)


def test_readonly_building_api_client_refuses_wrong_account_and_synthetic_data():
    seen = []
    def handler(request):
        seen.append(request.url.path)
        if request.url.path.endswith("/cities/42/buildings"):
            return httpx.Response(200, json={
                "account_id": "alpha", "city_id": 42, "available": True,
                "buildings": [{"position": 1, "name": "Town Hall", "level": 12,
                              "building": "townHall", "busy": False, "can_upgrade": True}]
            })
        return httpx.Response(404)
    with mock_client(handler) as client:
        assert client.buildings("alpha", 42)[0]["level"] == 12
        with pytest.raises(ValueError, match="Invalid building inventory"):
            client.buildings("../other", 42)
        with pytest.raises(ValueError, match="Invalid building inventory"):
            client.buildings("alpha", -1)
        assert seen == ["/api/v1/accounts/alpha/cities/42/buildings"]

    def fake(_request):
        return httpx.Response(200, json={"account_id": "alpha", "city_id": 42,
                                         "available": False, "buildings": []})
    with mock_client(fake) as client:
        with pytest.raises(APIConnectionError, match="unavailable"):
            client.buildings("alpha", 42)
