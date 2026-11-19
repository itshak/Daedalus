"""Offline trusted-host recovery integration; never contacts a real game account."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.auth_assistance import AssistanceBroker, AssistanceReason
from daedalus.browser_recovery import stage_with_human_browser
from daedalus.client import DaedalusClient
from daedalus.saved_session_recovery import (
    _COOKIE_SERVICE,
    _STAGED_COOKIE_SERVICE,
    SavedSessionUnavailable,
    _account_key,
    bind_saved_email,
    discard_staged_world_cookie,
    stage_world_cookie,
)
from daedalus.saved_worker import SavedCookieWorker, SavedWorkerUnavailable
from daedalus.session_monitor import ExistingSessionRecoveryMonitor
from daedalus.task_control import TaskController

TOKEN = "x" * 48


class Keys:
    def __init__(self):
        self.values = {}
    def set_password(self, service, username, value):
        self.values[(service, username)] = value
    def get_password(self, service, username):
        return self.values.get((service, username))
    def delete_password(self, service, username):
        del self.values[(service, username)]


class Browser:
    def __init__(self, cookie="S" * 48):
        self.cookie = cookie
        self.calls = []
    def open(self, lobby, world):
        self.calls.append(("open", lobby, world))
    def world_cookie(self, host):
        self.calls.append(("cookie", host))
        return self.cookie
    def close(self):
        self.calls.append(("close",))


class IPC:
    def __init__(self, account):
        self.account = account
        self.is_valid = True
        self.checks = []
        self.start_calls = []
    def validate_account(self, account):
        self.checks.append(account)
        return self.is_valid and account == self.account
    def has_account(self, account):
        return account == self.account
    def list_managed_tasks(self, _account):
        return []
    def preflight_task(self, account, task):
        return {"task": task, "ready": True, "reason": "none",
                "notifications_required": False, "checked": []}

    def start_managed_task(self, *args):
        self.start_calls.append(args)
        return {"task_id": "a" * 24, "pid": 42, "status": "running"}


@pytest.fixture
def system(tmp_path):
    account = Account("alpha", "s301-en", "ExamplePlayer", "A", True)
    config = tmp_path / "accounts.toml"
    config.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
        'player = "ExamplePlayer"\nlabel = "A"\n',
        encoding="utf-8",
    )
    owner = AccountSessionCoordinator([account], state_dir=tmp_path / "locks")
    keys = Keys()
    bind_saved_email(account, "synthetic@example.invalid", credential_store=keys)
    restored = []
    events = []
    def restore(_account, mail, cookie):
        assert mail == "synthetic@example.invalid"
        restored.append(cookie)
        connection = SimpleNamespace(closed=False)
        connection.close = lambda: setattr(connection, "closed", True)
        return SimpleNamespace(
            logged=True, mundo="301", servidor="en",
            username="ExamplePlayer", s=connection,
        )
    worker = SavedCookieWorker(
        account, owner, credential_store=keys, restore=restore,
        start_ipc=lambda session: (events.append(("ipc-start", session)), object())[1],
        stop_ipc=lambda: events.append(("ipc-stop",)),
    )
    ipc = IPC(account)
    controller = TaskController(
        [account], owner, ipc, ledger_path=tmp_path / "tasks.sqlite",
        active_validation=True,
    )
    broker = AssistanceBroker(owner)
    monitor = ExistingSessionRecoveryMonitor(controller, broker)
    yield SimpleNamespace(
        account=account, owner=owner, keys=keys, config=config,
        worker=worker, controller=controller, broker=broker,
        monitor=monitor, ipc=ipc, events=events, restored=restored,
    )
    if worker.lease is not None and not worker._recovery_uncertain:
        worker.close()
    controller.close()


def _owned(system):
    system.worker.start(confirmed=True)
    system.controller.adopt_verified_saved_worker(
        system.account.id, system.worker.lease,
    )
    return system.worker.lease


def _ticket(system):
    ticket = system.broker.request(
        system.worker.lease, AssistanceReason.SESSION_EXPIRED,
    )
    return ticket["ticket_id"]


def _api(system):
    return TestClient(create_app(
        accounts_path=system.config, api_token=TOKEN,
        session_coordinator=system.owner,
        task_controller=system.controller,
        assistance_broker=system.broker,
        recovery_monitor=system.monitor,
        saved_worker=system.worker,
    ))


def test_staging_never_creates_verified_cookie_or_game_session(system):
    account, keys = system.account, system.keys
    cookie = "S" * 48
    with pytest.raises(Exception, match="consent"):
        stage_world_cookie(
            account, cookie, credential_store=keys, confirmed=False,
        )
    assert keys.get_password(_COOKIE_SERVICE, _account_key(account)) is None
    receipt = stage_world_cookie(
        account, cookie, credential_store=keys, confirmed=True,
    )
    assert receipt == {
        "account_id": "alpha", "status": "world_cookie_staged_unverified",
    }
    assert cookie not in str(receipt)
    assert keys.get_password(_STAGED_COOKIE_SERVICE, _account_key(account)) == cookie
    assert keys.get_password(_COOKIE_SERVICE, _account_key(account)) is None
    assert system.owner.status("alpha") == "not_connected"
    assert discard_staged_world_cookie(account, credential_store=keys) == {
        "account_id": "alpha", "status": "staged_cookie_discarded",
    }
    assert keys.get_password(_STAGED_COOKIE_SERVICE, _account_key(account)) is None


@pytest.mark.parametrize("cookie,confirm", [("bad", True), (None, True), ("S" * 48, False)])
def test_staging_browser_rejects_unapproved_or_missing_cookie(system, cookie, confirm):
    browser = Browser(cookie)
    with pytest.raises(SavedSessionUnavailable):
        stage_with_human_browser(
            system.account, confirmed=True, human_confirm=lambda: confirm,
            browser=browser, credential_store=system.keys,
        )
    assert browser.calls[-1] == ("close",)
    assert system.keys.get_password(
        _STAGED_COOKIE_SERVICE, _account_key(system.account),
    ) is None


def test_staging_browser_stays_host_only_even_when_worker_owns_lease(system):
    _owned(system)
    with pytest.raises(SessionBusyError):
        system.owner.acquire("alpha")
    browser = Browser()
    result = stage_with_human_browser(
        system.account, confirmed=True, human_confirm=lambda: True,
        browser=browser, credential_store=system.keys,
    )
    assert result["status"] == "world_cookie_staged_unverified"
    assert browser.calls == [
        ("open", "https://lobby.ikariam.gameforge.com/",
         "https://s301-en.ikariam.gameforge.com/"),
        ("cookie", "s301-en.ikariam.gameforge.com"), ("close",),
    ]
    assert system.owner.status("alpha") == "authenticated"


def test_verified_staged_rebind_keeps_lease_and_does_not_restart_tasks(system):
    lease = _owned(system)
    with pytest.raises(SavedWorkerUnavailable, match="staging"):
        system.worker.recover_from_verified_cookie(
            system.controller, confirmed=True, require_staged=True,
        )
    assert system.events == [("ipc-start", system.worker._session)]
    stage_world_cookie(
        system.account, "S" * 48, confirmed=True,
        credential_store=system.keys,
    )
    result = system.worker.recover_from_verified_cookie(
        system.controller, confirmed=True, require_staged=True,
    )
    assert result["status"] == "worker_recovered"
    assert system.worker.lease is lease
    assert system.restored == [None, "S" * 48]
    assert len(system.ipc.start_calls) == 0
    assert [event[0] for event in system.events] == [
        "ipc-start", "ipc-stop", "ipc-start",
    ]
    assert system.keys.get_password(
        _COOKIE_SERVICE, _account_key(system.account),
    ) == "S" * 48
    assert system.keys.get_password(
        _STAGED_COOKIE_SERVICE, _account_key(system.account),
    ) is None


def test_rebind_rejects_wrong_player_before_ipc_stop_or_cookie_promotion(system):
    _owned(system)
    stage_world_cookie(
        system.account, "S" * 48, confirmed=True,
        credential_store=system.keys,
    )
    system.worker._restore = lambda *_: SimpleNamespace(
        logged=True, username="OtherPlayer", mundo="301", servidor="en",
        s=SimpleNamespace(close=lambda: None),
    )
    with pytest.raises(SavedWorkerUnavailable, match="did not verify"):
        system.worker.recover_from_verified_cookie(
            system.controller, confirmed=True, require_staged=True,
        )
    assert len(system.events) == 1
    assert system.keys.get_password(
        _COOKIE_SERVICE, _account_key(system.account),
    ) is None
    assert system.keys.get_password(
        _STAGED_COOKIE_SERVICE, _account_key(system.account),
    ) == "S" * 48


def test_read_only_recovery_guide_is_bearer_guarded_and_no_secret(system):
    _owned(system)
    ticket = _ticket(system)
    client = _api(system)
    endpoint = "/api/v1/accounts/alpha/recovery-guide"
    assert client.get(endpoint).status_code == 401
    result = client.get(endpoint, headers={"Authorization": f"Bearer {TOKEN}"})
    assert result.status_code == 200
    assert result.json()["ticket"]["ticket_id"] == ticket
    assert result.json()["mode"] == "host_local_only"
    assert result.json()["allow_http_cookie_transfer"] is False
    assert result.json()["dedicated_rebind_supported"] is True
    assert TOKEN not in result.text
    assert "synthetic@example.invalid" not in result.text
    assert "S" * 48 not in result.text
    unknown = client.get(
        "/api/v1/accounts/nope/recovery-guide",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert unknown.status_code == 404


def test_api_rebind_requires_ticket_ack_staged_cookie_then_new_attestation(system):
    lease = _owned(system)
    ticket = _ticket(system)
    client = _api(system)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    endpoint = f"/api/v1/accounts/alpha/recovery/{ticket}/rebind-worker"
    assert client.post(endpoint, json={"confirmed": True}).status_code == 401
    assert client.post(
        endpoint, headers=headers,
        json={"confirmed": True, "cookie": "S" * 48},
    ).status_code == 422
    assert client.post(
        endpoint, headers=headers, json={"confirmed": True},
    ).status_code == 409
    assert len(system.events) == 1

    # The API accepts only the operator's nonsecret acknowledgment.
    approval = client.post(
        f"/api/v1/accounts/alpha/auth-assistance/{ticket}/approve",
        headers=headers, json={"confirmed": True},
    )
    assert approval.status_code == 200
    assert approval.json()["ticket"]["state"] == "operator_ready"
    assert system.monitor.poll_once()[0].phase == "assisted_login"
    stage_world_cookie(
        system.account, "S" * 48, confirmed=True,
        credential_store=system.keys,
    )
    result = client.post(
        endpoint, headers=headers, json={"confirmed": True},
    )
    assert result.status_code == 200, result.text
    assert result.json() == {
        "account_id": "alpha", "status": "worker_recovered_verified",
    }
    assert system.worker.lease is lease
    assert system.owner.status("alpha") == "authenticated"
    assert len(system.ipc.checks) >= 1
    assert system.ipc.start_calls == []
    assert system.monitor.poll_once()[0].phase == "authenticated"
    assert client.post(
        endpoint, headers=headers, json={"confirmed": True},
    ).status_code == 409
    assert len(system.events) == 3


def test_remote_client_only_sends_account_ticket_and_confirmation(system):
    _owned(system)
    ticket = _ticket(system)
    api = create_app(
        accounts_path=system.config, api_token=TOKEN,
        session_coordinator=system.owner,
        task_controller=system.controller,
        assistance_broker=system.broker,
        recovery_monitor=system.monitor,
        saved_worker=system.worker,
    )
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={"account_id": "alpha", "status": "worker_recovered_verified"},
        ) if request.method == "POST" else httpx.Response(
            200, json=TestClient(api).get(
                str(request.url.path),
                headers={"Authorization": f"Bearer {TOKEN}"},
            ).json(),
        )
    with DaedalusClient(
        "http://127.0.0.1:8765", TOKEN,
        transport=httpx.MockTransport(handler),
    ) as client:
        guide = client.recovery_guide("alpha")
        assert guide["ticket"]["ticket_id"] == ticket
        receipt = client.rebind_dedicated_worker(
            "alpha", ticket, confirmed=True,
        )
        assert receipt["status"] == "worker_recovered_verified"
        with pytest.raises(ValueError):
            client.rebind_dedicated_worker("alpha", ticket, confirmed=False)
        with pytest.raises(ValueError):
            client.rebind_dedicated_worker("../cookie", ticket, confirmed=True)
    assert requests[-1].content == b'{"confirmed":true}'
    assert "S" * 48 not in str(requests)
    assert "/recovery-guide" in str(requests[0].url)
    assert all("cookie" not in str(request.url) for request in requests)


def test_owner_can_prepare_verified_idle_worker_without_waiting_for_expiry(system):
    lease = _owned(system)
    client = _api(system)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    endpoint = "/api/v1/accounts/alpha/recovery/prepare"
    assert client.post(endpoint, json={"confirmed": True}).status_code == 401
    assert client.post(endpoint, headers=auth, json={"confirmed": False}).status_code == 422
    assert client.post(
        endpoint, headers=auth,
        json={"confirmed": True, "cookie": "S" * 48},
    ).status_code == 422
    response = client.post(endpoint, headers=auth, json={"confirmed": True})
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["account_id"] == "alpha"
    assert receipt["status"] == "manual_recovery_prepared"
    ticket = receipt["ticket"]
    assert ticket["state"] == "waiting_operator"
    assert system.owner.status("alpha") == "needs_assistance"
    assert system.worker.lease is lease
    assert system.ipc.start_calls == []
    assert len(system.events) == 1
    assert client.post(endpoint, headers=auth, json={"confirmed": True}).status_code == 409
    assert client.get(
        "/api/v1/accounts/alpha/recovery-guide", headers=auth,
    ).json()["ticket"]["ticket_id"] == ticket["ticket_id"]
    approval = client.post(
        f"/api/v1/accounts/alpha/auth-assistance/{ticket['ticket_id']}/approve",
        headers=auth, json={"confirmed": True},
    )
    assert approval.status_code == 200
    stage_world_cookie(
        system.account, "S" * 48,
        confirmed=True, credential_store=system.keys,
    )
    rebind = client.post(
        f"/api/v1/accounts/alpha/recovery/{ticket['ticket_id']}/rebind-worker",
        headers=auth, json={"confirmed": True},
    )
    assert rebind.status_code == 200, rebind.text
    assert rebind.json()["status"] == "worker_recovered_verified"
    assert system.owner.status("alpha") == "authenticated"
    assert system.ipc.start_calls == []


def test_owner_cannot_prepare_recovery_during_running_tasks(system):
    _owned(system)
    system.ipc.list_managed_tasks = lambda _account: [
        {"status": "running", "task_id": "synthetic"},
    ]
    client = _api(system)
    response = client.post(
        "/api/v1/accounts/alpha/recovery/prepare",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"confirmed": True},
    )
    assert response.status_code == 409
    assert system.owner.status("alpha") == "authenticated"
    assert system.broker.snapshot("alpha")["ticket"] is None
    assert len(system.events) == 1
