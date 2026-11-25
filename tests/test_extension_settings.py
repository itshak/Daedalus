"""Local approval, exact registration and redacted controller projection."""
import hashlib
import json
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from ikabot.helpers import nativeExtensions as worker
from ikabot.helpers.ipc import IPCServer

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import load_accounts
from daedalus.api import create_app
from daedalus.engine_ipc import ControlledIPCClient, EngineIPCUnavailable
from daedalus.extension_settings import validate_extension_status
from daedalus.task_control import TaskController


@pytest.fixture
def fixture(monkeypatch, tmp_path):
    directory = tmp_path / "approved-extensions"
    directory.mkdir(mode=0o700)
    source = b"raise AssertionError('Source must never be executed')\n"
    digest = hashlib.sha256(source).hexdigest()
    path = directory / "reviewed.py"
    path.write_bytes(source)
    path.chmod(0o600)
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "extensions": [
        {"id": "reviewed", "name": "Reviewed extension", "sha256": digest}]}))
    manifest.chmod(0o600)
    glob = tmp_path / "global.json"
    glob.write_text(json.dumps({"customModules": ["/legacy/private.py"], "unrelated": "preserve"}))
    user = tmp_path / "user.json"
    monkeypatch.setattr(worker.sessionStorage, "get_ikabot_dir", lambda: str(tmp_path))
    monkeypatch.setattr(worker.sessionStorage, "get_global_config_path", lambda: str(glob))
    monkeypatch.setattr(worker.sessionStorage, "get_user_file_path", lambda _: str(user))
    monkeypatch.setattr(worker.sessionStorage, "session_data_lock", nullcontext)
    session = Mock(mundo=1, servidor="en", username="Player", mail="synthetic")
    draft = {"id": "reviewed", "sha256": digest, "registered": True,
             "expected_registered": False, "confirmed_global": True}
    return session, path, glob, user, draft


def test_only_approved_file_can_be_registered_and_unregistered(fixture):
    session, path, glob, _, draft = fixture
    result = worker.status(session)
    assert result["unreviewed_count"] == 1
    assert result["extensions"][0]["verified"]
    assert not result["extensions"][0]["registered"]
    assert str(path) not in str(result) and "/legacy/private.py" not in str(result)
    validate_extension_status({"account_id": "alpha", **result}, "alpha")
    registered = worker.set_registration(session, draft)
    assert registered["extensions"][0]["registered"]
    assert json.loads(glob.read_text())["customModules"] == ["/legacy/private.py", str(path)]
    with pytest.raises(ValueError, match="changed"):
        worker.set_registration(session, draft)
    path.write_text("changed")
    assert not worker.status(session)["extensions"][0]["verified"]
    unregistered = worker.set_registration(session, {**draft, "registered": False, "expected_registered": True})
    assert not unregistered["extensions"][0]["registered"]
    assert path.exists()
    assert json.loads(glob.read_text())["customModules"] == ["/legacy/private.py"]
    assert json.loads(glob.read_text())["unrelated"] == "preserve"
    with pytest.raises(ValueError, match="not approved"):
        worker.set_registration(session, draft)


def test_legacy_override_and_arbitrary_file_request_rejected(fixture):
    session, _, glob, user, draft = fixture
    baseline = glob.read_bytes()
    user.write_text(json.dumps({"shared": {"customModules": ["/legacy/private.py"]}}))
    assert worker.status(session)["legacy_override"]
    with pytest.raises(ValueError):
        worker.set_registration(session, draft)
    with pytest.raises(ValueError):
        worker.set_registration(session, {**draft, "id": "../arbitrary"})
    with pytest.raises(ValueError):
        worker.set_registration(session, {**draft, "path": "/some/file.py"})
    assert glob.read_bytes() == baseline


def test_symlink_cannot_be_approved(fixture, tmp_path):
    session, path, glob, _, draft = fixture
    other = tmp_path/"other.py"
    other.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not available")
    assert not worker.status(session)["extensions"][0]["verified"]
    with pytest.raises(ValueError):
        worker.set_registration(session, draft)
    assert json.loads(glob.read_text())["customModules"] == ["/legacy/private.py"]


def test_authenticated_controller_checks_scope_and_expected_registration(fixture, tmp_path, monkeypatch):
    session, _, _, _, draft = fixture
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
    owner = AccountSessionCoordinator(accounts, state_dir=tmp_path/"locks")
    controller = TaskController(accounts, owner, ipc, ledger_path=tmp_path/"tasks.sqlite")
    token = "x"*48
    auth = {"Authorization":"Bearer "+token}
    client = TestClient(create_app(accounts_path=config, api_token=token, ipc_client=ipc,
                                   session_coordinator=owner, task_controller=controller))
    try:
        path = "/api/v1/accounts/alpha/extensions"
        assert client.get(path).status_code == 401
        assert client.post(path, json=draft).status_code == 401
        assert client.post(path, headers=auth, json={**draft,"source":"print('x')"}).status_code == 422
        result = client.get(path, headers=auth).json()
        assert result["account_id"] == "alpha"
        reply = client.post(path, headers=auth, json=draft)
        assert reply.status_code == 200 and reply.json()["extensions"][0]["registered"]
        assert client.post(path, headers=auth, json=draft).status_code == 503
    finally:
        controller.close()
