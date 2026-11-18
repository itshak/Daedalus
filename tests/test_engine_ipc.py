"""Real loopback socket tests with a synthetic IPC worker, never Gameforge."""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import contextmanager

import pytest

from daedalus.accounts import Account
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient

SECRET = "a" * 64  # synthetic, low-entropy test-only marker
ALPHA = Account("alpha", "s301-en", "ExamplePlayer", "Alpha", True)


@contextmanager
def fake_worker(tmp_path, responder=None):
    descriptor = tmp_path / "ipc.json"
    listen = socket.socket()
    listen.bind(("127.0.0.1", 0))
    listen.listen(5)
    listen.settimeout(0.5)
    stop = threading.Event()
    requested = []

    def reply(msg):
        if responder is not None:
            return responder(msg)
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": "s301-en", "player": "ExamplePlayer"}]}
        if msg["action"] == "list_cities_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer",
                    "cities": [{"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}]}
        if msg["action"] == "warehouse_snapshots_existing":
            return {"status": "ok", "world": "s301-en", "username": "ExamplePlayer", "cities": [
                {"city_id": 42, "city_name": "Athens", "unsecured": {
                    "wood": "2,970,123", "wine": "0", "glass": "1.2K"}, "capacity": "1,000,000"}
            ]}
        return {"status": "ok", "pid": os.getpid()}

    def run():
        while not stop.is_set():
            try:
                conn, _ = listen.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    data = b""
                    while b"\n" not in data:
                        data += conn.recv(8192)
                    msg = json.loads(data)
                    requested.append({key: val for key, val in msg.items() if key != "authkey"})
                    assert msg["authkey"] == SECRET
                    conn.sendall((json.dumps(reply(msg)) + "\n").encode())
                except (OSError, ValueError):
                    break

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    descriptor.write_text(json.dumps({
        "pid": os.getpid(), "port": listen.getsockname()[1], "host": "127.0.0.1",
        "authkey": SECRET,
    }), encoding="utf-8")
    if os.name != "nt":
        descriptor.chmod(0o600)
    try:
        yield ExistingIPCClient(descriptor), requested, descriptor
    finally:
        stop.set()
        listen.close()
        thread.join(timeout=3)


def test_real_socket_reads_existing_accounts_and_cities(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        assert client.has_account(ALPHA)
        assert client.cities(ALPHA) == [
            {"id": 42, "name": "Athens", "coords": "1:2", "tradegood": "wine"}
        ]
        assert [r["action"] for r in requests] == [
            "list_sessions", "list_sessions", "list_cities_existing"
        ]
        assert all(r.get("world") in (None, "s301-en") for r in requests)
        assert all("email" not in r for r in requests)


def test_no_engine_rpc_can_start_tasks_or_create_sessions(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        for action in ("start_task", "list_cities", "stop_task", "restore_session"):
            with pytest.raises(ValueError, match="read-only"):
                client.request(action)
        assert requests == []


def test_no_matching_session_refused_before_city_query(tmp_path):
    different = Account("beta", "s302-en", "Different", "Other", True)
    with fake_worker(tmp_path) as (client, requests, _):
        with pytest.raises(EngineIPCUnavailable, match="No unique"):
            client.cities(different)
        assert [x["action"] for x in requests] == ["list_sessions"]


def test_mismatched_identity_in_response_is_rejected(tmp_path):
    def responder(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": "s302-en", "username": ALPHA.player, "cities": []}

    with fake_worker(tmp_path, responder=responder) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="another account"
    ):
        client.cities(ALPHA)


def test_non_owner_file_mode_refused_before_connect(tmp_path):
    with fake_worker(tmp_path) as (client, requests, descriptor):
        if os.name == "nt":
            pytest.skip("POSIX file permissions")
        descriptor.chmod(0o644)
        with pytest.raises(EngineIPCUnavailable, match="owner-only"):
            client.list_sessions()
        assert requests == []


def test_symlink_descriptor_rejected(tmp_path):
    with fake_worker(tmp_path) as (_client, requests, path):
        link = tmp_path / "alias.json"
        try:
            link.symlink_to(path)
        except OSError:
            pytest.skip("Symlinks unavailable")
        with pytest.raises(EngineIPCUnavailable, match="symlink"):
            ExistingIPCClient(link).list_sessions()
        assert requests == []


@pytest.mark.parametrize("patch", [
    {"host": "192.0.2.1"}, {"port": 0}, {"pid": -3}, {"authkey": "short"}
])
def test_bad_descriptor_rejected_without_socket(tmp_path, patch):
    with fake_worker(tmp_path) as (client, requests, path):
        info = json.loads(path.read_text())
        info.update(patch)
        path.write_text(json.dumps(info))
        if os.name != "nt":
            path.chmod(0o600)
        with pytest.raises(EngineIPCUnavailable):
            client.list_sessions()
        assert requests == []


def test_missing_descriptor_rejected_without_creating_files(tmp_path):
    client = ExistingIPCClient(tmp_path / "does-not-exist" / "ipc.json")
    with pytest.raises(EngineIPCUnavailable):
        client.list_sessions()
    assert list(tmp_path.iterdir()) == []


def test_engine_error_contents_are_redacted(tmp_path):
    with fake_worker(
        tmp_path,
        responder=lambda _req: {"status": "error", "error": "game-secret-should-be-redacted"},
    ) as (client, _, _):
        with pytest.raises(EngineIPCUnavailable) as info:
            client.list_sessions()
        assert "game-secret" not in str(info.value)


def test_warehouse_resources_end_to_end_over_real_ipc_socket(tmp_path):
    with fake_worker(tmp_path) as (client, requests, _):
        snapshots = client.warehouses(ALPHA)
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert snapshot.city_id == 42
        assert snapshot.resources.unsecured["wood"] == 2_970_123
        assert snapshot.resources.unsecured["wine"] == 0
        assert snapshot.resources.unsecured["glass"] == 1200
        assert snapshot.resources.unsecured["marble"] is None
        assert snapshot.resources.capacity == 1_000_000
        assert [r["action"] for r in requests] == [
            "list_sessions", "warehouse_snapshots_existing"
        ]


def test_empty_or_bad_warehouse_ipc_data_refused(tmp_path):
    def bad_data(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                "cities": [{"city_id": 42, "city_name": "Athens", "unsecured": {
                    "wood": "raw-session-cookie-value"}, "capacity": None}]}

    with fake_worker(tmp_path, responder=bad_data) as (client, _, _), pytest.raises(
        EngineIPCUnavailable, match="numeric"
    ):
        client.warehouses(ALPHA)


def test_existing_task_ipc_is_explicit_and_scoped_with_real_loopback_socket(tmp_path):
    from daedalus.engine_ipc import ExistingTaskIPCClient

    calls = []

    def respond(msg):
        calls.append({k: v for k, v in msg.items() if k != "authkey"})
        action = msg["action"]
        if action == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        if action == "start_task_existing":
            assert msg["world"] == ALPHA.world
            assert msg["player"] == ALPHA.player
            assert msg["task"] == "alertAttacks"
            return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                    "task": "alertAttacks", "pid": 81001}
        if action == "list_managed_tasks":
            return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                    "tasks": [{"pid": 81001, "task": "alertAttacks", "status": "running",
                               "started_at": 1234567890.0}]}
        if action == "stop_managed_task":
            assert msg["pid"] == 81001
            return {"status": "ok", "pid": 81001, "task": "alertAttacks", "state": "stopped"}
        return {"status": "error", "error": "unknown"}

    with fake_worker(tmp_path, responder=respond) as (readonly, _requests, descriptor):
        controller = ExistingTaskIPCClient(descriptor)
        with pytest.raises(ValueError, match="read-only"):
            readonly.request("start_task_existing")
        result = controller.start_task(ALPHA, "alertAttacks", {"minutes": 10},
                                       "12345678-1234-4123-8123-123456789abc")
        assert result["pid"] == 81001
        tasks = controller.list_tasks(ALPHA)
        assert tasks[0]["status"] == "running"
        stopped = controller.stop_task(ALPHA, 81001)
        assert stopped == {"pid": 81001, "status": "stopped"}
        assert [row["action"] for row in calls] == [
            "list_sessions", "start_task_existing", "list_managed_tasks", "stop_managed_task"
        ]
        assert all("email" not in row for row in calls)
        assert all("authkey" not in row for row in calls)


def test_existing_task_ipc_rejects_wrong_identity_and_arbitrary_pid(tmp_path):
    from daedalus.engine_ipc import ExistingTaskIPCClient

    def respond(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        if msg["action"] == "start_task_existing":
            return {"status": "ok", "world": "s999-en", "username": ALPHA.player,
                    "task": "alertAttacks", "pid": 81001}
        return {"status": "error", "error": "not a controller task"}

    with fake_worker(tmp_path, responder=respond) as (_readonly, _, descriptor):
        controller = ExistingTaskIPCClient(descriptor)
        with pytest.raises(EngineIPCUnavailable, match="different account"):
            controller.start_task(ALPHA, "alertAttacks", {},
                                  "12345678-1234-4123-8123-123456789abc")
        with pytest.raises(ValueError, match="valid managed task PID"):
            controller.stop_task(ALPHA, -1)
        with pytest.raises(ValueError, match="disabled"):
            controller.start_task(
                Account(ALPHA.id, ALPHA.world, ALPHA.player, ALPHA.label, False),
                "alertAttacks", {}, "12345678-1234-4123-8123-123456789abc"
            )


def test_end_to_end_opt_in_http_api_to_authenticated_synthetic_engine(tmp_path):
    """Controller HTTP -> real loopback IPC protocol -> synthetic game worker."""
    from fastapi.testclient import TestClient

    from daedalus.api import create_app
    from daedalus.engine_ipc import ExistingTaskIPCClient

    accounts_file = tmp_path / "accounts.toml"
    accounts_file.write_text('schema = 1\n[[accounts]]\nid = "alpha"\n'
                             'world = "s301-en"\nplayer = "ExamplePlayer"')

    def response(msg):
        if msg["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        if msg["action"] == "start_task_existing":
            return {"status": "ok", "pid": 81001, "task": msg["task"],
                    "world": ALPHA.world, "username": ALPHA.player}
        if msg["action"] == "list_managed_tasks":
            return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                    "tasks": [{"pid": 81001, "task": "alertAttacks",
                               "status": "running", "started_at": 12345.0}]}
        if msg["action"] == "stop_managed_task":
            return {"status": "ok", "pid": msg["pid"], "state": "stopped"}
        return {"status": "error"}

    with fake_worker(tmp_path, responder=response) as (_readonly, requests, descriptor):
        api = TestClient(create_app(
            accounts_path=accounts_file,
            api_token="x" * 48,
            task_controller=ExistingTaskIPCClient(descriptor),
        ))
        auth = {"Authorization": "Bearer " + "x" * 48}
        assert api.get("/api/v1/task-control", headers=auth).json()["enabled"] is True
        started = api.post("/api/v1/accounts/alpha/tasks", headers=auth, json={
            "task": "alertAttacks", "config": {"minutes": 10},
            "request_id": "12345678-1234-4123-8123-123456789abc",
        })
        assert started.status_code == 200, started.text
        assert started.json()["pid"] == 81001
        assert api.get("/api/v1/accounts/alpha/tasks", headers=auth).json()["tasks"][0][
            "status"
        ] == "running"
        assert api.delete("/api/v1/accounts/alpha/tasks/81001", headers=auth).json()[
            "status"
        ] == "stopped"
        assert [req["action"] for req in requests] == [
            "list_sessions", "start_task_existing", "list_managed_tasks", "stop_managed_task"
        ]
        assert all("email" not in req and "authkey" not in req for req in requests)
