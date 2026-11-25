"""Managed piracy halts at a human challenge without solving or replay."""
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from ikabot.function import autoPirate
from ikabot.helpers import nativeChallengePolicy as worker

from daedalus.challenge_policy import validate_challenge_policy, validate_challenge_policy_draft


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(worker.sessionStorage, "session_data_lock", nullcontext)
    data = {"unrelated": "preserve", "shared": {}}
    session = Mock()
    session.getSessionData.side_effect = lambda: data.copy()

    def persist(value):
        assert "shared" not in value
        data.update(value)
    session.setSessionData.side_effect = persist
    return session


def test_policy_is_compare_and_set_and_requires_notification(session, monkeypatch):
    assert worker.status(session) == {"mode": "stop", "notification_ready": False}
    draft = {"mode": "notify_and_stop", "expected_mode": "stop", "confirmed": True}
    with pytest.raises(ValueError, match="destination"):
        worker.configure(session, draft)
    session.setSessionData.assert_not_called()
    monkeypatch.setattr(worker, "native_notification_ready", lambda *_: True)
    result = worker.configure(session, draft)
    assert result == {"mode": "notify_and_stop", "notification_ready": True}
    assert session.setSessionData.call_args.args[0]["unrelated"] == "preserve"
    with pytest.raises(ValueError, match="changed"):
        worker.configure(session, draft)
    assert validate_challenge_policy({"account_id": "alpha", **result}, "alpha")
    with pytest.raises(ValueError):
        validate_challenge_policy({"account_id": "alpha", **result}, "beta")
    with pytest.raises(ValueError):
        validate_challenge_policy_draft({**draft, "solver": "arbitrary"})
    with pytest.raises(ValueError):
        worker.configure(session, {**draft, "mode": []})


def test_fixed_notification_at_most_once(session, monkeypatch):
    accept = Mock()
    monkeypatch.setattr(worker, "_provider_accepts", accept)
    worker.stop_at_challenge(session)
    accept.assert_not_called()
    monkeypatch.setattr(worker, "native_notification_ready", lambda *_: True)
    monkeypatch.setattr(worker, "_native_notification_destination",
                        lambda *_: ("https://example.invalid", {"text": "test"}))
    worker.configure(session, {"mode": "notify_and_stop", "expected_mode": "stop", "confirmed": True})
    worker.stop_at_challenge(session)
    accept.assert_called_once_with("telegram", "https://example.invalid", {"text": worker._TEXT})
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_managed_piracy_stops_before_retrieval_or_submission(session, monkeypatch):
    city = {"id": "1"}
    monkeypatch.setattr(autoPirate, "getPiracyCityById", lambda *_: city)
    monkeypatch.setattr(worker, "stop_at_challenge", Mock())
    image = Mock(side_effect=AssertionError("Challenge retrieval forbidden"))
    monkeypatch.setattr(autoPirate, "extract_captcha_image", image)
    session.post.side_effect = ["city", "function=createCaptcha"]
    autoPirate.do_pirate_missions.__wrapped__(session, pirateCount=1, pirateMissionChoice=1,
                                            piracyCities=[city], manual_challenge=True)
    worker.stop_at_challenge.assert_called_once_with(session)
    image.assert_not_called()
    session.get.assert_not_called()
    assert session.post.call_count == 2
    assert session.post.call_args.kwargs == {"retry_on_failure": False}

def test_authenticated_policy_is_account_scoped(session, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from ikabot.helpers.ipc import IPCServer

    from daedalus.account_sessions import AccountSessionCoordinator
    from daedalus.accounts import load_accounts
    from daedalus.api import create_app
    from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
    from daedalus.task_control import TaskController

    server = IPCServer()
    monkeypatch.setattr(server, "_existing_session", lambda _: session)
    session.mundo = 1
    session.servidor = "en"
    session.username = "Player"
    ipc = ControlledIPCClient()

    def exchange(payload, **_kwargs):
        result = server.handle_request(payload)
        if result["status"] != "ok":
            raise EngineIPCUnavailable("Synthetic rejection")
        return result

    monkeypatch.setattr(ipc, "_exchange", exchange)
    monkeypatch.setattr(worker, "native_notification_ready", lambda *_: True)
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Player"\n')
    accounts = load_accounts(config)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path / "tasks.sqlite")
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=config, api_token=token, ipc_client=ipc,
                                   session_coordinator=owner, task_controller=controller))
    try:
        path = "/api/v1/accounts/alpha/challenge-policy"
        draft = {"mode": "notify_and_stop", "expected_mode": "stop", "confirmed": True}
        assert client.get(path).status_code == 401
        assert client.post(path, json=draft).status_code == 401
        assert client.get(path, headers=auth).json()["mode"] == "stop"
        assert client.post(path, headers=auth, json={**draft, "answer": "x"}).status_code == 422
        reply = client.post(path, headers=auth, json=draft)
        assert reply.status_code == 200 and reply.json()["mode"] == "notify_and_stop"
        assert client.post(path, headers=auth, json=draft).status_code == 503
        assert client.get("/api/v1/accounts/beta/challenge-policy", headers=auth).status_code == 404
    finally:
        controller.close()
