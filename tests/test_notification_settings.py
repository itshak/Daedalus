"""Offline encrypted worker-global provider configuration."""
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.helpers import nativeNotificationSettings as worker
from ikabot.helpers.ipc import IPCServer

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient
from daedalus.notification_settings import seal_notification_settings
from daedalus.task_control import TaskController

# Entirely synthetic values; no provider calls or real credentials.
SETTINGS = {"mode": "replace", "bot_token": "123456:" + "x"*30, "chat_id": "-123"}


@pytest.fixture
def system(monkeypatch, tmp_path):
    session = Mock(mundo=1, servidor="en", username="Player", mail="synthetic")
    server = IPCServer()
    monkeypatch.setattr(server, "_existing_session", lambda _: session)
    monkeypatch.setattr(worker.sessionStorage, "get_global_config_path", lambda: str(tmp_path/"global.json"))
    monkeypatch.setattr(worker.sessionStorage, "get_user_file_path", lambda _: str(tmp_path/"user.json"))
    from contextlib import nullcontext
    monkeypatch.setattr(worker.sessionStorage, "session_data_lock", nullcontext)
    provider = Mock(return_value=True)
    monkeypatch.setattr(worker, "_provider_accepts", provider)
    return session, server, provider, tmp_path


def test_encrypted_settings_use_single_ticket_and_fixed_provider(system):
    session, _, provider, root = system
    challenge = worker.begin(session, "alpha", "telegram")
    envelope = seal_notification_settings(challenge, "alpha", "telegram", SETTINGS)
    assert SETTINGS["bot_token"] not in str(envelope)
    with pytest.raises(ValueError):
        worker.complete(session, "beta", "telegram", envelope)
    with pytest.raises(ValueError):
        worker.complete(session, "alpha", "discord", envelope)
    provider.assert_not_called()
    receipt = worker.complete(session, "alpha", "telegram", envelope)
    assert receipt == {"account_id": "alpha", "provider": "telegram", "scope": "worker_global", "result": "configured"}
    assert SETTINGS["bot_token"] not in str(receipt)
    assert json.loads((root/"global.json").read_text())["telegram"] == {
        "botToken": SETTINGS["bot_token"], "chatId": SETTINGS["chat_id"]}
    if os.name == "posix":
        assert (root/"global.json").stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError):
        worker.complete(session, "alpha", "telegram", envelope)
    provider.assert_called_once()
    challenge = worker.begin(session, "alpha", "telegram")
    cleared = worker.complete(session, "alpha", "telegram",
        seal_notification_settings(challenge, "alpha", "telegram", {"mode": "clear"}))
    assert cleared["result"] == "cleared"
    assert json.loads((root/"global.json").read_text())["telegram"] == {}
    provider.assert_called_once()


def test_rejected_provider_and_invalid_url_preserve_configuration(system):
    session, _, provider, root = system
    initial = {"discord": {"webhookUrl": "synthetic"}, "other": "preserved"}
    (root/"global.json").write_text(json.dumps(initial))
    provider.return_value = False
    c = worker.begin(session, "alpha", "telegram")
    with pytest.raises(RuntimeError):
        worker.complete(session, "alpha", "telegram",
            seal_notification_settings(c, "alpha", "telegram", SETTINGS))
    assert json.loads((root/"global.json").read_text()) == initial
    c = worker.begin(session, "alpha", "discord")
    with pytest.raises(ValueError):
        worker.complete(session, "alpha", "discord", seal_notification_settings(c, "alpha", "discord",
            {"mode": "replace", "webhook_url": "https://127.0.0.1/private"}))
    provider.assert_called_once()
    (root/"user.json").write_text(json.dumps({"shared": {"telegram": {"botToken": "legacy"}}}))
    c = worker.begin(session, "alpha", "telegram")
    with pytest.raises(RuntimeError, match="Legacy"):
        worker.complete(session, "alpha", "telegram",
            seal_notification_settings(c, "alpha", "telegram", {"mode": "clear"}))
    assert json.loads((root/"global.json").read_text()) == initial


def test_expiry_and_tampered_ciphertext(system, monkeypatch):
    session, _, provider, _ = system
    now = [10.]
    monkeypatch.setattr(worker.time, "monotonic", lambda: now[0])
    challenge = worker.begin(session, "alpha", "telegram")
    envelope = seal_notification_settings(challenge, "alpha", "telegram", SETTINGS)
    now[0] += 120
    with pytest.raises(ValueError):
        worker.complete(session, "alpha", "telegram", envelope)
    c = worker.begin(session, "alpha", "telegram")
    e = seal_notification_settings(c, "alpha", "telegram", SETTINGS)
    e["ciphertext"] = ("A" if e["ciphertext"][0] != "A" else "B") + e["ciphertext"][1:]
    with pytest.raises(ValueError):
        worker.complete(session, "alpha", "telegram", e)
    provider.assert_not_called()


def test_api_and_ipc_only_accept_encrypted_configuration(system, monkeypatch, tmp_path):
    _, server, provider, _ = system
    path = tmp_path/"accounts.toml"
    path.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Player"\n')
    accounts = load_accounts(path)
    ipc = ControlledIPCClient()
    def exchange(payload, **_kwargs):
        answer = server.handle_request(payload)
        if answer["status"] != "ok":
            from daedalus.engine_ipc import EngineIPCUnavailable
            raise EngineIPCUnavailable("Synthetic rejection")
        return answer
    monkeypatch.setattr(ipc, "_exchange", exchange)
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path/"locks")
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path/"tasks.sqlite")
    token = "x"*48
    auth = {"Authorization": "Bearer "+token}
    client = TestClient(create_app(accounts_path=path, api_token=token, ipc_client=ipc,
                                   session_coordinator=owner, task_controller=controller))
    try:
        base = "/api/v1/accounts/alpha/notifications/telegram"
        assert client.post(base+"/begin", json={"confirmed_global":True}).status_code == 401
        assert client.post(base+"/begin", headers=auth, json={}).status_code == 422
        assert client.post(base+"/complete", headers=auth, json=SETTINGS).status_code == 422
        challenge = client.post(base+"/begin", headers=auth, json={"confirmed_global":True}).json()
        envelope = seal_notification_settings(challenge, "alpha", "telegram", SETTINGS)
        response = client.post(base+"/complete", headers=auth, json=envelope)
        assert response.status_code == 200 and response.json()["result"] == "configured"
        assert client.post(base+"/complete", headers=auth, json=envelope).status_code == 503
        provider.assert_called_once()
    finally:
        controller.close()


def test_browser_envelope_interoperates_with_python_worker(system):
    import shutil
    session, _, provider, _ = system
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    # Node versions before 22.18 lack built-in TS stripping by default.
    root = Path(__file__).resolve().parents[1]
    challenge = worker.begin(session, "alpha", "telegram")
    script = """import {sealNotificationSettings} from './apps/web/lib/notification-settings.ts';
const v=JSON.parse(process.argv[1]); console.log(JSON.stringify(await sealNotificationSettings(v.challenge,"alpha","telegram",v.settings)));"""
    result = subprocess.run([node, "--experimental-strip-types", "--input-type=module", "-e", script,
        json.dumps({"challenge": challenge, "settings": SETTINGS})], cwd=root,
        # Cold Node startup on hosted Windows can exceed 15s. Keep this
        # bounded below the actual 120s challenge lifetime.
        capture_output=True, text=True, timeout=60, check=False)
    if result.returncode and ("bad option" in result.stderr or "unknown option" in result.stderr):
        pytest.skip("Node.js does not support TypeScript stripping")
    assert result.returncode == 0, "Browser crypto interoperability failed"
    envelope = json.loads(result.stdout)
    assert worker.complete(session, "alpha", "telegram", envelope)["result"] == "configured"
    provider.assert_called_once()
