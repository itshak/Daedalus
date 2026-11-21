"""Encrypted Mac-client world session handoff; fully synthetic, no real game login."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.client import DaedalusClient
from daedalus.native_browser_handoff import (
    NativeBrowserHandoff,
    NativeHandoffUnavailable,
    encrypt_mac_world_session,
)
from daedalus.saved_session_recovery import (
    _COOKIE_SERVICE,
    _SERVICE,
    _STAGED_COOKIE_SERVICE,
    _account_key,
    bind_saved_email,
)

TOKEN = "K" * 48
COOKIE = "C" * 48
EMAIL = "person@example.invalid"


class Keys:
    def __init__(self):
        self.entries = {}

    def get_password(self, service, key):
        return self.entries.get((service, key))

    def set_password(self, service, key, value):
        self.entries[(service, key)] = value

    def delete_password(self, service, key):
        del self.entries[(service, key)]


def session(player="ExamplePlayer"):
    http = SimpleNamespace(close=lambda: None)
    return SimpleNamespace(logged=True, username=player, mundo="301",
                           servidor="en", s=http)


@pytest.fixture
def env(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    config = tmp_path / "accounts.toml"
    config.write_text('schema = 1\n[[accounts]]\nid = "alpha"\n'
                      'world = "s301-en"\nplayer = "ExamplePlayer"\nlabel = "Example"\n')
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "locks")
    keys = Keys()
    seen = []
    def restore(row, email, cookie):
        seen.append((row.id, email, cookie))
        return session()
    broker = NativeBrowserHandoff([account], owner, credential_store=keys, restore=restore)
    api = TestClient(create_app(accounts_path=config, api_token=TOKEN,
                                session_coordinator=owner, native_browser_handoff=broker))
    return SimpleNamespace(account=account, owner=owner, keys=keys, seen=seen,
                           broker=broker, api=api)


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def _begin(env):
    result = env.api.post("/api/v1/accounts/alpha/browser-login/start",
                          json={"confirmed": True}, headers=_auth())
    assert result.status_code == 200, result.text
    return result.json()


def _complete(env, challenge, cookie=COOKIE, email=""):
    envelope = encrypt_mac_world_session(challenge, env.account, cookie, email=email)
    return env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{challenge['ticket_id']}/complete",
        json=envelope, headers=_auth(),
    ), envelope


def test_ephemeral_mac_handoff_verifies_exact_game_identity_and_stores_cookie_in_keyring(env):
    bind_saved_email(env.account, EMAIL, credential_store=env.keys)
    challenge = _begin(env)
    assert len(challenge["public_key"]) == 43
    response, envelope = _complete(env, challenge)
    assert response.status_code == 200, response.text
    assert response.json() == {"account_id": "alpha", "status": "world_cookie_bound"}
    assert env.seen == [("alpha", EMAIL, COOKIE)]
    assert env.keys.get_password(_COOKIE_SERVICE, _account_key(env.account)) == COOKIE
    assert COOKIE not in json.dumps(envelope)
    assert EMAIL not in json.dumps(envelope)
    assert COOKIE not in response.text and EMAIL not in response.text
    assert env.owner.status("alpha") == "not_connected"  # no new worker
    assert env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{challenge['ticket_id']}/complete",
        json=envelope, headers=_auth(),
    ).status_code == 409  # single-use challenge


def test_first_login_email_is_encrypted_and_never_logged_or_returned(env):
    challenge = _begin(env)
    before, _ = _complete(env, challenge)
    assert before.status_code == 409
    assert "email" in before.json()["detail"].lower()
    assert env.keys.entries == {}
    second = _begin(env)
    success, envelope = _complete(env, second, email=EMAIL)
    assert success.status_code == 200
    assert env.keys.get_password(_SERVICE, _account_key(env.account)) == EMAIL
    assert env.seen == [("alpha", EMAIL, COOKIE)]
    assert EMAIL not in json.dumps(envelope) and COOKIE not in json.dumps(envelope)


def test_invalid_auth_consent_and_raw_cookie_uploads_do_not_reach_keyring(env):
    endpoint = "/api/v1/accounts/alpha/browser-login/start"
    assert env.api.get("/api/v1/native-browser-login").status_code == 401
    assert env.api.get("/api/v1/native-browser-login", headers=_auth()).json()["enabled"]
    assert env.api.post(endpoint, json={"confirmed": True}).status_code == 401
    assert env.api.post(endpoint, json={"confirmed": False}, headers=_auth()).status_code == 422
    assert env.api.post(endpoint, json={"confirmed": True, "cookie": COOKIE},
                        headers=_auth()).status_code == 422
    challenge = _begin(env)
    assert env.api.post(endpoint, json={"confirmed": True}, headers=_auth()).status_code == 409
    invalid = env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{challenge['ticket_id']}/complete",
        json={"confirmed": True, "cookie": COOKIE}, headers=_auth(),
    )
    assert invalid.status_code == 409
    assert COOKIE not in invalid.text
    assert env.keys.entries == {}


def test_ciphertext_tamper_and_cross_world_binding_are_rejected_without_replay(env):
    challenge = _begin(env)
    changed = Account("alpha", "s301-en", "AnotherPlayer", "Other", True)
    envelope = encrypt_mac_world_session(challenge, changed, COOKIE)
    response = env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{challenge['ticket_id']}/complete",
        json=envelope, headers=_auth(),
    )
    assert response.status_code == 409
    assert env.seen == [] and env.keys.entries == {}
    assert env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{challenge['ticket_id']}/complete",
        json=envelope, headers=_auth(),
    ).status_code == 409
    with pytest.raises(NativeHandoffUnavailable, match="selected account"):
        encrypt_mac_world_session(challenge,
            Account("wrong", "s301-en", "ExamplePlayer", "Wrong", True), COOKIE)


def test_expiration_cancellation_and_owner_lease_reject_reuse(env):
    current = [1000.0]
    env.broker.clock = lambda: current[0]
    challenge = _begin(env)
    current[0] += 601
    response, _ = _complete(env, challenge, email=EMAIL)
    assert response.status_code == 409
    assert env.keys.entries == {}
    second = _begin(env)
    cancelled = env.api.post(
        f"/api/v1/accounts/alpha/browser-login/{second['ticket_id']}/cancel",
        headers=_auth(), json={"confirmed": True},
    )
    assert cancelled.status_code == 200
    assert _complete(env, second, email=EMAIL)[0].status_code == 409
    with env.owner.acquire("alpha"):
        refused = env.api.post("/api/v1/accounts/alpha/browser-login/start",
                               headers=_auth(), json={"confirmed": True})
        assert refused.status_code == 409
    assert env.seen == []


def test_wrong_player_attestation_rolls_back_new_email_and_never_promotes_cookie(env):
    env.broker.restore = lambda *args: session("Impostor")
    challenge = _begin(env)
    rejected, _ = _complete(env, challenge, email=EMAIL)
    assert rejected.status_code == 409
    assert env.keys.entries == {}
    assert env.owner.status("alpha") == "not_connected"
    assert COOKIE not in rejected.text and EMAIL not in rejected.text


def test_client_uses_opaque_envelope_only_and_requires_exact_https_origin():
    seen = []
    def transport(request):
        seen.append((request.url.path, request.content))
        if request.url.path == "/api/v1/native-browser-login":
            return httpx.Response(200, json={"enabled": True,
                "mode": "mac_ephemeral_encrypted"})
        if request.url.path.endswith("/complete"):
            return httpx.Response(200, json={"account_id": "alpha",
                "status": "world_cookie_bound"})
        return httpx.Response(404)
    client = DaedalusClient("https://controller.example.invalid", TOKEN,
                            transport=httpx.MockTransport(transport))
    assert client.native_browser_login_capabilities()["enabled"] is True
    envelope = {"confirmed": True, "client_key": "A" * 43,
                "nonce": "A" * 16, "ciphertext": "A" * 80}
    ticket = "00000000-0000-4000-8000-000000000000"
    receipt = client.finish_native_browser_login("alpha", ticket, envelope)
    assert receipt["status"] == "world_cookie_bound"
    assert COOKIE not in str(seen) and EMAIL not in str(seen)
    with pytest.raises(ValueError):
        client.finish_native_browser_login("alpha", ticket, {"cookie": COOKIE})
    client.close()


def test_disabled_or_demo_endpoint_not_create_handoff(env):
    app = TestClient(create_app(accounts_path=None, api_token=TOKEN, demo_mode=True))
    assert app.get("/api/v1/native-browser-login", headers=_auth()).json()["enabled"] is False
    assert app.post("/api/v1/accounts/demo_alpha/browser-login/start",
                    headers=_auth(), json={"confirmed": True}).status_code == 503


@pytest.fixture
def owned(tmp_path):
    """One isolated in-memory owned worker; no Gameforge or external processes."""
    from daedalus.auth_assistance import AssistanceBroker
    from daedalus.saved_worker import SavedCookieWorker
    from daedalus.session_monitor import ExistingSessionRecoveryMonitor
    from daedalus.task_control import TaskController

    row = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    owner = AccountSessionCoordinator([row], state_dir=tmp_path / "owned-leases")
    keys = Keys()
    bind_saved_email(row, EMAIL, credential_store=keys)
    keys.set_password(_COOKIE_SERVICE, _account_key(row), "O" * 48)
    events = []
    def restore(_row, _email, cookie):
        events.append(("restored", cookie))
        return session()
    worker = SavedCookieWorker(
        row, owner, credential_store=keys, restore=restore,
        start_ipc=lambda sess: (events.append(("ipc-start",)), object())[1],
        stop_ipc=lambda: events.append(("ipc-stop",)),
    )
    class IPC:
        def __init__(self):
            self.tasks = []
            self.valid = True
        def has_account(self, row):
            return True
        def list_managed_tasks(self, row):
            return self.tasks
        def validate_account(self, row):
            return self.valid
        def start_managed_task(self, *args):
            events.append(("task-start",))
            raise AssertionError("No operation may start during login")
    ipc = IPC()
    controller = TaskController(
        [row], owner, ipc, ledger_path=tmp_path / "task-ledger.sqlite",
        active_validation=True,
    )
    broker = AssistanceBroker(owner)
    monitor = ExistingSessionRecoveryMonitor(controller, broker)
    worker.start(confirmed=True)
    controller.adopt_verified_saved_worker(row.id, worker.lease)
    monitor.attach_dedicated_worker(worker)
    native = NativeBrowserHandoff(
        [row], owner, monitor=monitor, dedicated_worker=worker,
        credential_store=keys,
    )
    try:
        yield SimpleNamespace(row=row, keys=keys, owner=owner,
                              native=native, monitor=monitor, broker=broker,
                              worker=worker, ipc=ipc, events=events)
    finally:
        if not worker._recovery_uncertain:
            worker.close()
        controller.close()


def test_dedicated_worker_native_browser_login_rebinds_only_after_worker_attestation(owned):
    initial_lease = owned.worker.lease
    ticket = owned.native.start("alpha", confirmed=True)
    assert owned.owner.status("alpha") == "needs_assistance"
    assert owned.worker.lease is initial_lease
    assert owned.events == [("restored", "O" * 48), ("ipc-start",)]
    envelope = encrypt_mac_world_session(ticket, owned.row, COOKIE)
    result = owned.native.complete("alpha", ticket["ticket_id"], envelope)
    assert result == {"account_id": "alpha", "status": "worker_recovered_verified"}
    assert owned.owner.status("alpha") == "authenticated"
    assert owned.worker.lease is initial_lease
    assert owned.keys.get_password(_COOKIE_SERVICE, _account_key(owned.row)) == COOKIE
    assert owned.keys.get_password(_STAGED_COOKIE_SERVICE, _account_key(owned.row)) is None
    assert owned.events == [
        ("restored", "O" * 48), ("ipc-start",),
        ("restored", COOKIE), ("ipc-stop",), ("ipc-start",),
    ]
    assert not any(event[0] == "task-start" for event in owned.events)
    with pytest.raises(NativeHandoffUnavailable, match="already consumed"):
        owned.native.complete("alpha", ticket["ticket_id"], envelope)


def test_busy_worker_and_cancelled_native_browser_never_force_session_recovery(owned):
    owned.ipc.tasks = [{"status": "running", "task_id": "T"}]
    with pytest.raises(NativeHandoffUnavailable, match="uncertain task"):
        owned.native.start("alpha", confirmed=True)
    assert owned.owner.status("alpha") == "authenticated"
    owned.ipc.tasks = []
    first = owned.native.start("alpha", confirmed=True)
    assert owned.native.cancel("alpha", first["ticket_id"], confirmed=True)["status"] == (
        "browser_login_cancelled"
    )
    assert owned.owner.status("alpha") == "needs_assistance"
    assert owned.worker.lease is not None
    retry = owned.native.start("alpha", confirmed=True)
    assert retry["ticket_id"] != first["ticket_id"]
    assert owned.native.cancel("alpha", retry["ticket_id"], confirmed=True)["status"] == (
        "browser_login_cancelled"
    )
    assert owned.keys.get_password(_COOKIE_SERVICE, _account_key(owned.row)) == "O" * 48


def test_wrong_world_session_cannot_replace_running_owned_worker(owned):
    old_restore = owned.worker._restore
    owned.worker._restore = lambda row, email, cookie: session(
        "WrongPlayer" if cookie == COOKIE else "ExamplePlayer"
    )
    try:
        challenge = owned.native.start("alpha", confirmed=True)
        envelope = encrypt_mac_world_session(challenge, owned.row, COOKIE)
        with pytest.raises(NativeHandoffUnavailable, match="did not verify"):
            owned.native.complete("alpha", challenge["ticket_id"], envelope)
        assert owned.keys.get_password(_COOKIE_SERVICE, _account_key(owned.row)) == "O" * 48
        assert owned.worker.lease is not None
        assert not any(event[0] == "task-start" for event in owned.events)
    finally:
        owned.worker._restore = old_restore

def test_native_login_survives_monitor_without_restored_worker(tmp_path):
    """An expired saved cookie must not disable Mac login for all ten accounts."""
    from daedalus.auth_assistance import AssistanceBroker
    from daedalus.session_monitor import ExistingSessionRecoveryMonitor
    from daedalus.task_control import TaskController

    row = Account("alpha", "s301-en", "ExamplePlayer", "Example", True)
    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\n'
        'world = "s301-en"\nplayer = "ExamplePlayer"\nlabel = "Example"\n'
    )
    owner = AccountSessionCoordinator([row], state_dir=tmp_path / "locks")

    class UnattachedIPC:
        def has_account(self, _account):
            return False

    controller = TaskController(
        [row], owner, UnattachedIPC(),
        ledger_path=tmp_path / "requests.sqlite3",
        active_validation=True,
    )
    broker = AssistanceBroker(owner)
    monitor = ExistingSessionRecoveryMonitor(controller, broker)
    handoff = NativeBrowserHandoff([row], owner, credential_store=Keys())
    try:
        app = create_app(
            accounts_path=config, api_token=TOKEN, session_coordinator=owner,
            task_controller=controller, assistance_broker=broker,
            recovery_monitor=monitor, native_browser_handoff=handoff,
        )
        client = TestClient(app)
        response = client.get("/api/v1/native-browser-login", headers=_auth())
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        start = client.post(
            "/api/v1/accounts/alpha/browser-login/start",
            json={"confirmed": True}, headers=_auth(),
        )
        assert start.status_code == 200, start.text
        assert start.json()["status"] == "browser_login_ready"
        assert owner.status("alpha") == "not_connected"
    finally:
        controller.close()
