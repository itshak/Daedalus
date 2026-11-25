"""Managed world exports contain aggregate map rows only, scoped to one worker identity."""
import os
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.helpers import nativeWorldReports as worker
from ikabot.helpers.ipc import IPCServer

from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.world_reports import collect_report, report_csv, validate_world_page

RID = "a" * 24
SHALLOW = {"self_name": "not-exported", "name": "s1-en", "shallow": True, "partial": False,
           "islands": [{"x": "1", "y": "2", "id": "11", "name": "not-exported",
                        "resource_type": "1", "miracle_type": "2", "wood_lvl": "9", "players": "12"}]}


@pytest.fixture
def local_store(monkeypatch, tmp_path):
    monkeypatch.setattr(worker.sessionStorage, "get_ikabot_dir", lambda: str(tmp_path))
    monkeypatch.setattr(worker.sessionStorage, "session_data_lock", nullcontext)
    return Mock(mundo=1, servidor="en", username="Synthetic"), Mock(mundo=1, servidor="en", username="Other")


def test_private_report_projection_and_scope(local_store):
    alpha, beta = local_store
    worker.save_report(alpha, RID, SHALLOW)
    rows = worker.list_reports(alpha)
    assert rows[0]["island_count"] == 1
    page = worker.read_report(alpha, RID, 0)
    assert page["rows"] == [[1, 2, 11, 1, 2, 9, None, 12]]
    assert "not-exported" not in str(page)
    assert worker.list_reports(beta) == []
    with pytest.raises(OSError):
        worker.read_report(beta, RID, 0)
    with pytest.raises(ValueError):
        worker.read_report(alpha, "../arbitrary", 0)
    with pytest.raises(ValueError):
        worker.save_report(alpha, RID, SHALLOW)
    if os.name == "posix":
        assert (worker._directory(alpha)/(RID+".json")).stat().st_mode & 0o077 == 0
    report = collect_report(lambda offset: {"account_id":"alpha", **worker.read_report(alpha,RID,offset)}, "alpha", RID)
    assert report_csv(report).endswith("1,2,11,1,2,9,,12\r\n")
    with pytest.raises(ValueError):
        validate_world_page({"account_id":"beta", **page}, "alpha", RID, 0)


def test_deep_projection_excludes_player_fields_and_rejects_conflicts():
    item = {"x": 1, "y": 2, "id": 11, "tradegood": 1, "wonder": 2,
            "resourceLevel": 9, "tradegoodLevel": 8,
            "cities": [{"type": "city", "Name": "Synthetic name"}, {"type":"empty"}]}
    report = worker.project_world({"shallow": False, "partial": True, "islands": [item]}, RID, 100)
    assert report["rows"] == [[1,2,11,1,2,9,8,1]]
    assert "Synthetic name" not in str(report)
    with pytest.raises(ValueError, match="Conflicting"):
        worker.project_world({"shallow":False,"partial":True,"islands":[item,{**item,"id":12}]},RID,100)


def test_authenticated_report_endpoints_redact_scope(local_store, tmp_path, monkeypatch):
    alpha, _ = local_store
    worker.save_report(alpha, RID, SHALLOW)
    server = IPCServer()
    monkeypatch.setattr(server, "_existing_session", lambda _r: alpha)
    ipc = ControlledIPCClient()

    def exchange(payload, **_kwargs):
        result = server.handle_request(payload)
        if result["status"] != "ok":
            raise EngineIPCUnavailable("Synthetic rejection")
        return result

    monkeypatch.setattr(ipc, "_exchange", exchange)
    config = tmp_path/"accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Synthetic"\n')
    assert load_accounts(config)
    token = "x"*48
    auth = {"Authorization":"Bearer "+token}
    client = TestClient(create_app(accounts_path=config, api_token=token, ipc_client=ipc))
    path = "/api/v1/accounts/alpha/world-reports"
    assert client.get(path).status_code == 401
    result = client.get(path, headers=auth)
    assert result.status_code == 200 and result.json()["reports"][0]["report_id"] == RID
    result = client.get(path+"/"+RID+"?offset=0",headers=auth)
    assert result.status_code == 200 and result.json()["rows"][0][:3] == [1,2,11]
    assert client.get(path+"/"+RID+"?offset=10202",headers=auth).status_code == 422
    assert client.get("/api/v1/accounts/beta/world-reports",headers=auth).status_code == 404
    assert client.post(path,headers=auth,json={}).status_code == 405


def test_managed_dump_uses_aggregate_projection_and_zero_radius(monkeypatch):
    from ikabot.function import dumpWorld as engine

    session = Mock(mundo=1, servidor="en", username="Synthetic")
    session.post.return_value = '{"data":{"1":{"2":["11","Name","1","2","0","0","9","12"]},"3":{"4":["12","Name","1","2","0","0","9","12"]}}}'
    monkeypatch.setattr(engine.time, "sleep", lambda *_: None)
    raw = Mock(side_effect=AssertionError("Managed scan must not save raw dump"))
    monkeypatch.setattr(engine, "dump", raw)
    save = Mock()
    monkeypatch.setattr(worker, "save_report", save)
    observed = []

    def scan(shared, islands, delay, _session):
        observed.extend(islands)
        shared[5]["islands"].append({"x":1,"y":2,"id":11,"tradegood":1,"wonder":2,
                                     "resourceLevel":9,"tradegoodLevel":8,"cities":[]})

    monkeypatch.setattr(engine, "dump_islands", scan)
    import threading
    shared = ["", "", 0, threading.Event(), threading.Lock()]
    assert engine.do_it(session, 1, [1,2], 0, False, False, shared, managed_report_id=RID) is None
    assert observed == [(11,1,2)]
    assert save.call_args.args[2]["partial"] is True
    raw.assert_not_called()
