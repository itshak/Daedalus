"""Host-local E2E client contract tests. No live accounts, tokens or networking."""
import json
import runpy
from pathlib import Path

import pytest

pytest.importorskip("fcntl")

runner = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "warehouse_e2e.py"))
POLICY = {"player": "ExamplePlayer", "city": "ExampleCity", "resource": "wood", "useFreighters": False}
TASK = "fillCityWarehouse"


class FakeClient:
    def __init__(self):
        self.calls = []
        self.active = False
        self.uncertain = False
        self.lost = False

    def call(self, path, body=None):
        self.calls.append((path, body))
        if path == "health":
            return {"synthetic_demo": False, "mode": "task_control_opt_in", "authenticated_workers": 1}
        if path == "accounts":
            return {"accounts": [{"id": "alpha", "player": POLICY["player"], "enabled": True}]}
        if path.endswith("/tasks"):
            return {"requests": [], "engine_tasks": [{"status": "running"}] if self.active else []}
        if "preflight" in path:
            return {"ready": True, "unresolved_request": self.uncertain}
        if path.endswith("/cities"):
            return {"cities": [{"id": 42, "name": POLICY["city"]}]}
        if path.endswith("/reward-distribution-plan"):
            return {"account_id": "alpha", "task": TASK, "draft": body["draft"],
                    "observation": {"amount": 50}, "preview_id": "opaque-review", "expires_in": 120}
        if path.endswith("/fill-warehouse-start"):
            if self.lost:
                raise runner["Unavailable"]("lost response")
            return {"request_id": body["request_id"], "task": TASK, "status": "started",
                    "task_id": "f" * 24, "pid": 4242}
        raise AssertionError(path)


def test_preview_is_private_and_requires_exact_confirmation(tmp_path, capsys):
    client = FakeClient()
    path = tmp_path / "review.json"
    runner["run"](client, POLICY, "preview", preview_file=path)
    assert "opaque-review" not in capsys.readouterr().out
    rid = json.loads(path.read_text())["request_id"]
    with pytest.raises(runner["Unavailable"], match="confirmation mismatch"):
        runner["run"](client, POLICY, "start", "wrong", path)
    assert not any(p.endswith("/fill-warehouse-start") for p, _ in client.calls)
    client.lost = True
    runner["run"](client, POLICY, "start", rid, path)
    assert not path.exists()
    assert "check_receipt" in capsys.readouterr().out
    with pytest.raises(OSError):
        runner["run"](client, POLICY, "start", rid, path)
    assert sum(p.endswith("/fill-warehouse-start") for p, _ in client.calls) == 1


def test_unresolved_or_running_blocks_mutation(tmp_path):
    client = FakeClient()
    path = tmp_path / "review.json"
    client.uncertain = True
    with pytest.raises(runner["Unavailable"], match="preflight"):
        runner["run"](client, POLICY, "preview", preview_file=path)
    client.uncertain = False
    runner["run"](client, POLICY, "preview", preview_file=path)
    rid = json.loads(path.read_text())["request_id"]
    client.active = True
    with pytest.raises(runner["Unavailable"], match="active account tasks"):
        runner["run"](client, POLICY, "start", rid, path)
    assert not any(p.endswith("/fill-warehouse-start") for p, _ in client.calls)
