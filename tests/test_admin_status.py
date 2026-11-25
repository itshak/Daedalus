"""Protected administration only projects a fixed set of nonsecret fields."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.helpers.ipc import IPCServer
from ikabot.helpers.nativeAdminStatus import administrative_status

from daedalus.accounts import Account
from daedalus.admin_status import scoped_admin_status, validate_admin_status
from daedalus.api import create_app
from daedalus.engine_ipc import EngineIPCUnavailable, ExistingIPCClient
from daedalus.recovery_runtime import RoutedAccountIPC


def fixture():
    session = Mock()
    session.mundo = 1
    session.servidor = "en"
    session.username = "Player"
    session.getSessionData.return_value = {
        "shared": {"telegram": {"botToken": "123456:" + "x" * 30, "chatId": "123"},
                   "discord": {"webhookUrl": "https://discord.com/api/webhooks/123/" + "x"*25},
                   "customModules": ["/private/path.py"]},
        "proxy": {"set": True, "conf": {"https": "socks5://private-user:private-pass@private-host:9050"}},
        "decaptcha": {"name": "custom", "endpoint": "private-endpoint", "relevant_data": {"secret": "private-key"}},
        "cookies": {"ikariam": "private-cookie"},
    }
    return session


def expected():
    return {"telegram": "configured", "discord": "configured", "proxy_enabled": True,
            "proxy_protocol": "socks5", "proxy_port": 9050, "proxy_auth": True,
            "challenge_provider": "custom", "registered_extensions": 1}


def test_worker_projection_no_secrets_and_no_writes(monkeypatch):
    session = fixture()
    assert administrative_status(session) == expected()
    server = IPCServer()
    monkeypatch.setattr(server, "_existing_session", lambda _: session)
    reply = server.handle_request({"action": "administrative_status_existing",
                                   "world": "s1-en", "player": "Player"})
    assert reply == {"status": "ok", "world": "s1-en", "username": "Player", "settings": expected()}
    assert "private" not in str(reply)
    session.setSessionData.assert_not_called()
    session.get.assert_not_called()
    session.post.assert_not_called()


def test_scope_strict_shape_and_route():
    account = Account("alpha", "s1-en", "Player", "A", True)
    response = {"world": "s1-en", "username": "Player", "settings": expected()}
    assert scoped_admin_status(account, response) == {"account_id": "alpha", "settings": expected()}
    with pytest.raises(ValueError):
        scoped_admin_status(account, {**response, "username": "Other"})
    with pytest.raises(ValueError):
        validate_admin_status({**expected(), "cookie": "synthetic"})
    with pytest.raises(ValueError):
        validate_admin_status({**expected(), "proxy_port": True})
    with pytest.raises(ValueError):
        validate_admin_status({**expected(), "proxy_enabled": False})
    client = ExistingIPCClient()
    client.request = Mock(return_value=response)
    assert client.administrative_status(account)["settings"] == expected()
    client.request.assert_called_once_with("administrative_status_existing", account=account)
    router = RoutedAccountIPC(client)
    assert router.administrative_status(account)["account_id"] == "alpha"
    client.request.return_value = {**response, "username": "Other"}
    with pytest.raises(EngineIPCUnavailable):
        client.administrative_status(account)


def test_invalid_proxy_does_not_echo_malformed_value():
    session = fixture()
    session.getSessionData.return_value["proxy"]["conf"]["https"] = "http://private:pw@host:invalid"
    session.getSessionData.return_value["decaptcha"]["name"] = "private-provider"
    row = administrative_status(session)
    assert row["proxy_protocol"] is None and row["proxy_port"] is None
    assert row["challenge_provider"] == "unknown"
    assert "private" not in str(row)


def test_read_only_api_scope(tmp_path):
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s1-en"\nplayer = "Player"\n')
    ipc = Mock()
    ipc.administrative_status.return_value = {"account_id": "alpha", "settings": expected()}
    token = "x" * 48
    auth = {"Authorization": "Bearer " + token}
    client = TestClient(create_app(accounts_path=config, api_token=token, ipc_client=ipc))
    path = "/api/v1/accounts/alpha/administrative-status"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=auth).json() == ipc.administrative_status.return_value
    assert client.get(path.replace("alpha", "other"), headers=auth).status_code == 404
    assert client.post(path, headers=auth, json={}).status_code == 405
    ipc.administrative_status.return_value = {"account_id": "other", "settings": expected()}
    assert client.get(path, headers=auth).status_code == 503
