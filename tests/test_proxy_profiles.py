"""Only explicit account-approved profiles may be checked or saved."""
import json
import os
from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pytest
from ikabot.helpers import nativeProxyProfiles as worker

from daedalus.proxy_profiles import validate_proxy_draft, validate_proxy_result


@pytest.fixture
def approved(monkeypatch, tmp_path):
    monkeypatch.setattr(worker.sessionStorage, "get_ikabot_dir", lambda: str(tmp_path))
    monkeypatch.setattr(worker.sessionStorage, "session_data_lock", nullcontext)
    session = Mock(mundo=1, servidor="en", username="Player")
    data = {"unrelated": "preserve", "shared": {}, "processList": []}
    session.getSessionData.side_effect = lambda: data.copy()

    def persist(value):
        assert "shared" not in value
        data.update(value)
    session.setSessionData.side_effect = persist
    path = worker._approved_path(session)
    path.parent.mkdir(mode=0o700)
    path.write_text(json.dumps({"version":1,"allow_direct":True,"profiles":[
        {"id":"office","label":"Office network","url":"http://proxy.example.invalid:8080"}]}))
    path.chmod(0o600)
    check = Mock()
    monkeypatch.setattr(worker, "_check_connectivity", check)
    return session, data, path, check


def draft(session, action="save", profile="office"):
    return {"action":action,"profile":profile,"revision":worker.status(session)["revision"],"confirmed":True}


def test_test_and_save_are_account_scoped_and_redacted(approved):
    session, data, _path, check = approved
    before = worker.status(session)
    assert before["profiles"] == [{"id":"office","label":"Office network","protocol":"http"}]
    assert "proxy.example" not in str(before)
    test = draft(session, "test")
    result = worker.configure(session, test)
    assert validate_proxy_result({"account_id":"alpha", **result}, "alpha", test)["result"] == "tested"
    session.setSessionData.assert_not_called()
    check.assert_called_once_with("http://proxy.example.invalid:8080")
    save = draft(session)
    saved = worker.configure(session, save)
    assert saved["enabled"] is True and saved["current"] == "office"
    assert data["unrelated"] == "preserve"
    assert validate_proxy_result({"account_id":"alpha", **saved}, "alpha", save)["result"] == "saved"
    with pytest.raises(ValueError, match="changed"):
        worker.configure(session, save)
    with pytest.raises(ValueError):
        validate_proxy_result({"account_id":"beta", **saved}, "alpha", save)
    assert worker.configure(session, draft(session, profile=None))["enabled"] is False
    other = Mock(mundo=1, servidor="en", username="Other")
    other.getSessionData.return_value = {}
    assert worker.status(other)["profiles"] == []
    assert worker.status(other)["allow_direct"] is False


def test_busy_unapproved_failed_and_stale_checks_never_write(approved, monkeypatch):
    session, data, path, check = approved
    review = draft(session)
    with pytest.raises(ValueError):
        worker.configure(session, {**review, "profile":"unknown"})
    with pytest.raises(ValueError):
        worker.configure(session, review, managed_busy=True)
    data["processList"] = [{"pid":os.getpid()+12345}]
    monkeypatch.setattr(worker.psutil, "pid_exists", lambda _pid: True)
    with pytest.raises(ValueError):
        worker.configure(session, review)
    check.assert_not_called()
    data["processList"] = []
    check.side_effect = RuntimeError("Synthetic test failure")
    with pytest.raises(RuntimeError):
        worker.configure(session, review)
    session.setSessionData.assert_not_called()
    check.side_effect = lambda _url: data.update(proxy={"set":False})
    with pytest.raises(ValueError, match="changed"):
        worker.configure(session, review)
    session.setSessionData.assert_not_called()
    check.side_effect = None
    document = json.loads(path.read_text())
    document["allow_direct"] = False
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        worker.configure(session, draft(session, profile=None))
    document["profiles"][0]["url"] = "http://synthetic:synthetic@proxy.example.invalid:8080"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="inline credentials"):
        worker.status(session)
    for invalid in ({**review,"url":"http://example.invalid:80"},{**review,"profile":"legacy"},
                    {**review,"profile":"http://example.invalid:80"},{**review,"confirmed":False}):
        with pytest.raises(ValueError):
            validate_proxy_draft(invalid)


def test_fixed_tls_check_uses_no_game_session(monkeypatch):
    connection = MagicMock()
    response = MagicMock(status_code=200)
    connection.get.return_value.__enter__.return_value = response
    factory = MagicMock()
    factory.return_value.__enter__.return_value = connection
    monkeypatch.setattr(worker.requests, "Session", factory)
    worker._check_connectivity("http://proxy.example.invalid:8080")
    assert connection.trust_env is False
    connection.get.assert_called_once_with("https://example.com/", timeout=(4,5), verify=True,
                                           allow_redirects=False, stream=True)
    response.status_code = 302
    with pytest.raises(ValueError):
        worker._check_connectivity(None)


def test_authenticated_controller_rejects_foreign_or_raw_proxy_configuration(approved, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from ikabot.helpers.ipc import IPCServer

    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.api import create_app
    from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
    from daedalus.task_control import TaskController

    session, _data, _path, check = approved
    server = IPCServer()
    monkeypatch.setattr(server, "_existing_session", lambda _: session)
    ipc = ControlledIPCClient()

    def exchange(payload, **_kwargs):
        result = server.handle_request(payload)
        if result["status"] != "ok":
            raise EngineIPCUnavailable("Synthetic rejection")
        return result

    monkeypatch.setattr(ipc, "_exchange", exchange)
    config = tmp_path/"accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Player"\n')
    accounts = load_accounts(config)
    coordinator = AccountSessionCoordinator(accounts, state_dir=tmp_path/"locks")
    controller = TaskController(accounts, coordinator, ipc, ledger_path=tmp_path/"tasks.sqlite")
    token = "x"*48
    auth = {"Authorization":"Bearer "+token}
    client = TestClient(create_app(accounts_path=config, api_token=token, ipc_client=ipc,
                                   session_coordinator=coordinator, task_controller=controller))
    path = "/api/v1/accounts/alpha/proxy-settings"
    review = draft(session)
    try:
        assert client.get(path).status_code == 401
        assert client.post(path, json=review).status_code == 401
        assert client.get(path, headers=auth).json()["profiles"][0]["id"] == "office"
        assert client.post(path, headers=auth, json={**review,"url":"http://example.invalid:80"}).status_code == 422
        assert client.post(path, headers=auth, json={**review,"profile":"foreign"}).status_code == 503
        check.assert_not_called()
        reply = client.post(path, headers=auth, json=review)
        assert reply.status_code == 200 and reply.json()["current"] == "office"
        assert "proxy.example" not in reply.text
        assert client.get("/api/v1/accounts/beta/proxy-settings",headers=auth).status_code == 404
    finally:
        controller.close()
