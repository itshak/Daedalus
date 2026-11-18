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
                     "wood": "2,970,123", "wine": "0", "glass": "1.2K"}, "capacity": "1,000,000", "island": "8:20"}
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
        assert snapshot.island == "8:20"
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


def test_current_task_transport_rejects_old_pid_action_names(tmp_path):
    """The legacy PID API is gone; only the ID-scoped control transport remains."""
    from daedalus.engine_ipc import ControlledIPCClient

    calls = []
    task_id = "f" * 24

    def respond(msg):
        calls.append(msg["action"])
        if msg["action"] == "start_task_existing":
            return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                    "task_id": task_id, "pid": 81001}
        if msg["action"] == "list_tasks_existing":
            return {"status": "ok", "world": ALPHA.world, "player": ALPHA.player,
                    "tasks": [{"task_id": task_id, "task": "alertAttacks",
                               "status": "running", "pid": 81001}]}
        if msg["action"] == "stop_task_existing":
            return {"status": "ok", "task_id": task_id, "task_status": "stopped"}
        return {"status": "error", "error": "unknown"}

    with fake_worker(tmp_path, responder=respond) as (readonly, _requests, descriptor):
        controller = ControlledIPCClient(descriptor)
        with pytest.raises(ValueError, match="read-only"):
            readonly.request("stop_managed_task")
        receipt = controller.start_managed_task(ALPHA, "alertAttacks", {"minutes": 10}, "12345678-1234-4123-8123-123456789abc")
        assert receipt["task_id"] == task_id
        assert controller.list_managed_tasks(ALPHA)[0]["task_id"] == task_id
        assert controller.stop_managed_task(ALPHA, task_id)["status"] == "stopped"
        with pytest.raises(ValueError):
            controller.stop_managed_task(ALPHA, "-1")
        assert calls == ["start_task_existing", "list_tasks_existing", "stop_task_existing"]


def test_warehouse_ipc_rejects_arbitrary_island_strings(tmp_path):
    def reply(request):
        if request["action"] == "list_sessions":
            return {"status": "ok", "sessions": [{"world": ALPHA.world, "player": ALPHA.player}]}
        return {"status": "ok", "world": ALPHA.world, "username": ALPHA.player,
                "cities": [{"city_id": 42, "city_name": "Athens",
                            "unsecured": {"wood": "0"}, "capacity": None,
                            "island": "secret-token-example"}]}

    with (
        fake_worker(tmp_path, responder=reply) as (client, _, _),
        pytest.raises(EngineIPCUnavailable, match="island"),
    ):
        client.warehouses(ALPHA)
