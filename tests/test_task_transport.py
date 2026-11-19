"""Mock loopback IPC protocol tests for opt-in managed tasks."""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import contextmanager

import pytest

from daedalus.accounts import Account
from daedalus.engine_ipc import (
    ControlledIPCClient,
    EngineIPCUnavailable,
    EngineTaskRejected,
    ExistingIPCClient,
)

ACCOUNT = Account("alpha", "s301-en", "ExamplePlayer", "Primary", True)
KEY = "a" * 64


@contextmanager
def server(tmp_path, responder):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    sock.settimeout(0.5)
    stop = threading.Event()
    calls = []

    def run():
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                data = b""
                try:
                    while b"\n" not in data and len(data) < 32768:
                        data += conn.recv(8192)
                    msg = json.loads(data)
                    assert msg["authkey"] == KEY
                    calls.append({k: v for k, v in msg.items() if k != "authkey"})
                    conn.sendall((json.dumps(responder(msg)) + "\n").encode())
                except (OSError, ValueError):
                    continue

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    descriptor = tmp_path / "ipc.json"
    descriptor.write_text(json.dumps({
        "host": "127.0.0.1", "port": sock.getsockname()[1],
        "pid": os.getpid(), "authkey": KEY,
    }))
    if os.name != "nt":
        descriptor.chmod(0o600)
    try:
        yield descriptor, calls
    finally:
        stop.set()
        sock.close()
        thread.join(timeout=3)


def reply(message):
    action = message["action"]
    if action == "task_preflight_existing":
        return {"status": "ok", "world": ACCOUNT.world, "player": ACCOUNT.player,
                "task": message["task"], "ready": True, "reason": "none",
                "notifications_required": False, "checked": []}
    if action == "start_task_existing":
        return {"status": "ok", "world": ACCOUNT.world, "username": ACCOUNT.player,
                "task_id": "f" * 24, "pid": 4242}
    if action == "list_tasks_existing":
        return {"status": "ok", "world": ACCOUNT.world, "player": ACCOUNT.player,
                "tasks": [{"task_id": "f" * 24, "pid": 4242, "task": "alertAttacks",
                           "status": "running", "started_at": 1700000000}]}
    if action == "stop_task_existing":
        return {"status": "ok", "task_id": "f" * 24, "task_status": "stopped"}
    return {"status": "error", "error": "unsupported"}


def test_mutating_actions_are_restricted_to_opted_in_transport(tmp_path):
    with server(tmp_path, reply) as (path, calls):
        readonly = ExistingIPCClient(path)
        with pytest.raises(ValueError, match="read-only"):
            readonly.request("start_task_existing", account=ACCOUNT)
        with pytest.raises(ValueError, match="read-only"):
            readonly.request("stop_task_existing", account=ACCOUNT)
        assert calls == []

        controlled = ControlledIPCClient(path)
        receipt = controlled.start_managed_task(ACCOUNT, "alertAttacks", {"minutes": 20}, "12345678-1234-4123-8123-123456789abc")
        assert receipt == {"task_id": "f" * 24, "pid": 4242,
                           "task": "alertAttacks", "status": "running"}
        assert controlled.list_managed_tasks(ACCOUNT)[0]["task_id"] == "f" * 24
        assert controlled.stop_managed_task(ACCOUNT, "f" * 24)["status"] == "stopped"
        assert [call["action"] for call in calls] == [
            "start_task_existing", "list_tasks_existing", "stop_task_existing"
        ]
        assert calls[0]["world"] == ACCOUNT.world
        assert calls[0]["player"] == ACCOUNT.player
        assert "email" not in calls[0]


def test_invalid_managed_task_id_cannot_trigger_socket(tmp_path):
    with server(tmp_path, reply) as (path, calls):
        client = ControlledIPCClient(path)
        with pytest.raises(ValueError):
            client.stop_managed_task(ACCOUNT, "../123")
        with pytest.raises(ValueError):
            client.start_managed_task(ACCOUNT, "bad/task", {}, "12345678-1234-4123-8123-123456789abc")
        assert calls == []


def test_fake_engine_error_is_redacted_before_http_layer(tmp_path):
    with server(
        tmp_path,
        lambda _message: {"status": "error", "error": "sensitive-engine-session-material"},
    ) as (path, _calls):
        client = ControlledIPCClient(path)
        with pytest.raises(EngineIPCUnavailable) as result:
            client.start_managed_task(ACCOUNT, "alertAttacks", {}, "12345678-1234-4123-8123-123456789abc")
        assert "sensitive-engine" not in str(result.value)


def test_wrong_account_in_task_receipt_is_rejected(tmp_path):
    with server(
        tmp_path,
        lambda _message: {"status": "ok", "world": "s999-en",
                          "username": "WrongPlayer", "task_id": "f" * 24, "pid": 4242},
    ) as (path, _calls):
        client = ControlledIPCClient(path)
        with pytest.raises(EngineIPCUnavailable, match="receipt"):
            client.start_managed_task(ACCOUNT, "alertAttacks", {}, "12345678-1234-4123-8123-123456789abc")


def test_typed_pre_spawn_rejection_never_exposes_raw_engine_details(tmp_path):
    def responder(message):
        if message["action"] == "task_preflight_existing":
            return {"status": "ok", "world": ACCOUNT.world, "player": ACCOUNT.player,
                "task": message["task"], "ready": False,
                "reason": "notifications_required", "notifications_required": True,
                "checked": ["notifications"]}
        return {"status": "rejected", "reason": "invalid_configuration",
                "secret": "sensitive-engine-session-material"}
    with server(tmp_path, responder) as (path, calls):
        client = ControlledIPCClient(path)
        assert client.preflight_task(ACCOUNT, "alertAttacks")["ready"] is False
        with pytest.raises(EngineTaskRejected) as exc:
            client.start_managed_task(ACCOUNT, "alertAttacks", {"minutes": 2},
                                      "12345678-1234-4123-8123-123456789abc")
        assert exc.value.reason == "invalid_configuration"
        assert "sensitive" not in str(exc.value)
        assert [c["action"] for c in calls] == [
            "task_preflight_existing", "start_task_existing"]
