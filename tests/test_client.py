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
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        if request.url.path.endswith("/task-control"):
            return httpx.Response(200, json={"enabled": True})
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["task"] == "alertAttacks"
            assert payload["config"] == {"minutes": 10}
            assert payload["request_id"] == "12345678-1234-4123-8123-123456789abc"
            return httpx.Response(200, json={"pid": 81001, "status": "started"})
        if request.method == "GET":
            return httpx.Response(200, json={"tasks": [{"pid": 81001, "task": "alertAttacks"}]})
        if request.method == "DELETE":
            return httpx.Response(200, json={"pid": 81001, "status": "stopped"})
        return httpx.Response(404)

    with mock_client(handler) as client:
        assert client.task_control_status()["enabled"]
        started = client.start_task("alpha", "alertAttacks", {"minutes": 10},
                                    request_id="12345678-1234-4123-8123-123456789abc")
        assert started["pid"] == 81001
        assert client.tasks("alpha")[0]["pid"] == 81001
        assert client.stop_task("alpha", 81001)["status"] == "stopped"
    assert [entry[0] for entry in seen] == ["GET", "POST", "GET", "DELETE"]
    assert all(entry[2] == f"Bearer {TOKEN}" for entry in seen)
    assert seen[1][1] == "/api/v1/accounts/alpha/tasks"


def test_desktop_task_errors_redact_server_replies():
    body = "sensitive-cookie-do-not-display"
    with mock_client(lambda request: httpx.Response(503, text=body)) as client:
        with pytest.raises(APIConnectionError) as error:
            client.start_task("alpha", "alertAttacks", {},
                              request_id="12345678-1234-4123-8123-123456789abc")
        assert body not in str(error.value)
        assert error.value.status_code == 503
        with pytest.raises(ValueError):
            client.stop_task("alpha", -1)
