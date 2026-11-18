"""Synthetic end-to-end desktop HTTP client -> controller -> engine IPC TCP."""

from __future__ import annotations

import uuid

import httpx
from fastapi.testclient import TestClient
from test_task_transport import server

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.client import DaedalusClient
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.task_control import TaskController

TOKEN = "x" * 48
TASK_ID = "f" * 24


def synthetic_engine(msg):
    identity = {"world": "s301-en", "player": "ExamplePlayer"}
    action = msg["action"]
    if action == "list_sessions":
        return {"status": "ok", "sessions": [identity]}
    if action == "start_task_existing":
        assert msg["world"] == identity["world"]
        assert msg["player"] == identity["player"]
        assert msg["config"] == {"minutes": 20}
        return {"status": "ok", "world": identity["world"], "username": identity["player"],
                "task_id": TASK_ID, "pid": 4242}
    if action == "list_tasks_existing":
        return {"status": "ok", **identity, "tasks": [
            {"task_id": TASK_ID, "task": "alertAttacks", "pid": 4242,
             "status": "running", "started_at": 1700000000},
        ]}
    if action == "stop_task_existing":
        return {"status": "ok", "task_id": TASK_ID, "task_status": "stopped"}
    return {"status": "error", "error": "unsupported"}


def test_desktop_task_lifecycle_full_stack_without_real_game(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
                      'player = "ExamplePlayer"\n')
    accounts = load_accounts(config)
    with server(tmp_path, synthetic_engine) as (descriptor, ipc_calls):
        ipc = ControlledIPCClient(descriptor)
        owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "leases")
        tasks = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite3")
        app = create_app(
            accounts_path=config, api_token=TOKEN, ipc_client=ipc,
            session_coordinator=owner, task_controller=tasks,
        )
        api = TestClient(app)

        def forward(request):
            response = api.request(
                request.method, request.url.path, headers=dict(request.headers),
                content=request.content,
            )
            return httpx.Response(response.status_code, content=response.content)

        desktop = DaedalusClient(
            "http://127.0.0.1:8765", TOKEN, transport=httpx.MockTransport(forward)
        )
        try:
            assert desktop.health()["mode"] == "task_control_opt_in"
            assert desktop.accounts()[0]["id"] == "alpha"
            assert desktop.capabilities()["structured_engine_dispatch"] is True
            assert desktop.connected_accounts() == ["alpha"]
            request_id = str(uuid.uuid4())
            result = desktop.start_task(
                "alpha", "alertAttacks", {"minutes": 20}, request_id, confirmed=True,
            )
            assert result["status"] == "started"
            assert result["task_id"] == TASK_ID
            repeat = desktop.start_task(
                "alpha", "alertAttacks", {"minutes": 20}, request_id, confirmed=True,
            )
            assert repeat == result
            state = desktop.tasks("alpha")
            assert state["engine_tasks"][0]["status"] == "running"
            assert state["requests"][0]["status"] == "started"
            assert desktop.stop_task("alpha", TASK_ID)["status"] == "stopped"
            assert owner.status("alpha") == "authenticated"
        finally:
            desktop.close()
            tasks.close()

        assert [call["action"] for call in ipc_calls] == [
            "list_sessions", "list_sessions", "start_task_existing",
            "list_tasks_existing", "stop_task_existing",
        ]
        assert sum(call["action"] == "start_task_existing" for call in ipc_calls) == 1
        assert not any("email" in call for call in ipc_calls)
        assert not any("authkey" in call for call in ipc_calls)
