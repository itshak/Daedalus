"""Provider-specific, secret-free notification test dispatch."""
from unittest.mock import Mock

import pytest
from ikabot.function import testDiscordBot, testTelegramBot
from ikabot.helpers import botComm
from ikabot.helpers.ipc import IPCServer

from daedalus.accounts import Account
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.recovery_reconcile import restart_class_for


def synthetic_session():
    session = Mock()
    session.getSessionData.return_value = {"shared": {
        "telegram": {"botToken": "123456:" + "x"*30, "chatId": "123"},
        "discord": {"webhookUrl": "https://discord.com/api/webhooks/123/" + "x"*25},
    }}
    return session


@pytest.mark.parametrize(("provider", "module", "status"), [
    ("telegram", testTelegramBot, 200), ("discord", testDiscordBot, 204),
])
def test_notification_single_provider_no_replay(monkeypatch, provider, module, status):
    session = synthetic_session()
    response = Mock(status_code=status)
    response.json.return_value = {"ok": True}
    post = Mock(return_value=response)
    monkeypatch.setattr(botComm, "requests_post", post)
    assert module.prepare_native_test(session) == {}
    assert not post.called
    module.native_test.__wrapped__(session)
    post.assert_called_once()
    assert post.call_args.kwargs["allow_redirects"] is False
    assert post.call_args.kwargs["timeout"] == 10
    assert ("api.telegram.org" if provider == "telegram" else "discord.com") in post.call_args.args[0]
    assert restart_class_for("testTelegramBot" if provider == "telegram" else "testDiscordBot", {}) == "manual"
    post.reset_mock(side_effect=True)
    post.side_effect = RuntimeError("private provider URL")
    with pytest.raises(RuntimeError, match="^Notification test failed or outcome uncertain$"):
        module.native_test.__wrapped__(session)
    post.assert_called_once()


def test_notification_rejects_arbitrary_webhook_and_wrong_provider(monkeypatch):
    session = synthetic_session()
    session.getSessionData.return_value["shared"]["discord"]["webhookUrl"] = "https://example.test/webhook"
    post = Mock()
    monkeypatch.setattr(botComm, "requests_post", post)
    assert botComm.native_notification_ready(session, "telegram")
    assert not botComm.native_notification_ready(session, "discord")
    with pytest.raises(ValueError):
        testDiscordBot.prepare_native_test(session)
    with pytest.raises(RuntimeError):
        testDiscordBot.native_test.__wrapped__(session)
    assert not post.called
    server = IPCServer.__new__(IPCServer)
    monkeypatch.setattr(server, "_existing_session", lambda _r: session)
    session.mundo, session.servidor, session.username = 1, "en", "Test"
    assert server._task_preflight_existing({"task": "testTelegramBot"})["ready"]
    assert not server._task_preflight_existing({"task": "testDiscordBot"})["ready"]


def test_notification_result_only_exposes_safe_outcome(monkeypatch):
    account = Account("a", "s1-en", "Test", "Test", True)
    ipc = ControlledIPCClient()
    result = {"status": "ok", "world": "s1-en", "player": "Test", "tasks": [
        {"task_id": "a"*24, "task": "testDiscordBot", "status": "finished",
         "pid": 1, "started_at": 1.0, "outcome": "accepted", "private": "not displayed"}
    ]}
    monkeypatch.setattr(ipc, "_exchange", lambda *_a, **_kw: result)
    assert ipc.list_managed_tasks(account)[0]["outcome"] == "accepted"
    assert "private" not in ipc.list_managed_tasks(account)[0]
