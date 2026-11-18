"""Offline human-assistance broker and API behavior, with fake session owners only."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from daedalus.account_sessions import AccountSessionCoordinator, SessionPhase
from daedalus.accounts import Account
from daedalus.api import create_app
from daedalus.auth_assistance import (
    AssistanceBroker,
    AssistanceConflict,
    AssistanceReason,
)

TOKEN = "x" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def owner(tmp_path):
    accounts = [
        Account("alpha", "s301-en", "Alice", "Alpha", True),
        Account("beta", "s302-en", "Bob", "Beta", True),
    ]
    coordinator = AccountSessionCoordinator(accounts, state_dir=tmp_path / "locks")
    return coordinator


@pytest.fixture
def broker(owner):
    return AssistanceBroker(owner)


def test_manual_completion_does_not_assert_authenticated_state(owner, broker):
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.MANUAL_CHALLENGE)
        assert lease.phase is SessionPhase.NEEDS_ASSISTANCE
        assert ticket["state"] == "waiting_operator"
        receipt = broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        assert receipt["ticket"]["state"] == "operator_ready"
        assert lease.phase is SessionPhase.ASSISTED_LOGIN
        assert lease.phase is not SessionPhase.AUTHENTICATED
        broker.begin_validation(lease, ticket["ticket_id"])
        assert lease.phase is SessionPhase.VALIDATING_HANDOFF
        result = broker.complete_validation(lease, ticket["ticket_id"], valid=True)
        assert result["state"] == "verified_by_worker"
        assert lease.phase is SessionPhase.AUTHENTICATED


def test_failed_validation_requires_fresh_manual_confirmation(owner, broker):
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.LOGIN_REQUIRED)
        broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        broker.begin_validation(lease, ticket["ticket_id"])
        result = broker.complete_validation(lease, ticket["ticket_id"], valid=False)
        assert result["state"] == "retry_required"
        assert lease.phase is SessionPhase.NEEDS_ASSISTANCE
        with pytest.raises(AssistanceConflict):
            broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        next_ticket = broker.request(lease, AssistanceReason.SESSION_EXPIRED)
        assert next_ticket["ticket_id"] != ticket["ticket_id"]
        assert next_ticket["state"] == "waiting_operator"
        with pytest.raises(AssistanceConflict):
            broker.begin_validation(lease, ticket["ticket_id"])


def test_approval_is_per_account_one_time_and_requires_confirmation(owner, broker):
    with owner.acquire("alpha") as alpha, owner.acquire("beta") as beta:
        first = broker.request(alpha, AssistanceReason.SESSION_EXPIRED)
        second = broker.request(beta, AssistanceReason.LOGIN_REQUIRED)
        assert first["ticket_id"] != second["ticket_id"]
        with pytest.raises(ValueError):
            broker.approve("alpha", first["ticket_id"], confirmed=False)
        with pytest.raises(AssistanceConflict):
            broker.approve("beta", first["ticket_id"], confirmed=True)
        with pytest.raises(AssistanceConflict):
            broker.approve("alpha", second["ticket_id"], confirmed=True)
        assert alpha.phase is SessionPhase.NEEDS_ASSISTANCE
        broker.approve("alpha", first["ticket_id"], confirmed=True)
        with pytest.raises(AssistanceConflict):
            broker.approve("alpha", first["ticket_id"], confirmed=True)
        with pytest.raises(AssistanceConflict):
            broker.request(alpha, AssistanceReason.LOGIN_REQUIRED)
        assert beta.phase is SessionPhase.NEEDS_ASSISTANCE


def test_expiry_pauses_lease_and_rejects_stale_operator_approval(owner):
    current = [100.0]
    broker = AssistanceBroker(owner, ttl_seconds=30, clock=lambda: current[0])
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.LOGIN_REQUIRED)
        current[0] += 31.0
        assert broker.snapshot("alpha")["ticket"]["state"] == "expired"
        assert lease.phase is SessionPhase.PAUSED
        with pytest.raises(AssistanceConflict):
            broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        assert owner.status("alpha") == "paused"
        with pytest.raises(AssistanceConflict):
            broker.request(lease, AssistanceReason.LOGIN_REQUIRED)


def test_closed_or_unowned_worker_cannot_fake_assistance(owner, broker, tmp_path):
    unknown_coordinator = AccountSessionCoordinator(
        [Account("alpha", "s301-en", "Alice", "Alpha", True)],
        state_dir=tmp_path / "other-locks",
    )
    with unknown_coordinator.acquire("alpha") as impostor, pytest.raises(AssistanceConflict):
        broker.request(impostor, AssistanceReason.LOGIN_REQUIRED)
    lease = owner.acquire("alpha")
    lease.close()
    with pytest.raises(AssistanceConflict):
        broker.request(lease, AssistanceReason.LOGIN_REQUIRED)
    with pytest.raises(TypeError):
        broker.request(lease, "user supplied sensitive text")


def test_fixed_reasons_and_ticket_fields_are_nonsecret(owner, broker):
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.MANUAL_CHALLENGE)
        assert set(ticket) == {"ticket_id", "reason", "state"}
        uuid.UUID(ticket["ticket_id"])
        snapshot = broker.snapshot("alpha")
        assert snapshot["account_id"] == "alpha"
        assert snapshot["ticket"] == ticket
        assert "password" not in str(snapshot)
        assert "cookie" not in str(snapshot)
        assert "token" not in str(snapshot)


def _api(tmp_path):
    from pathlib import Path

    path = Path(tmp_path) / "accounts.toml"
    path.write_text(
        'schema = 1\n[[accounts]]\nid = "alpha"\nworld = "s301-en"\n'
        'player = "Alice"\nlabel = "Alice"\nenabled = true\n',
        encoding="utf-8",
    )
    from daedalus.accounts import load_accounts

    coordinator = AccountSessionCoordinator(load_accounts(path), state_dir=tmp_path / "lock")
    broker = AssistanceBroker(coordinator)
    client = TestClient(create_app(
        accounts_path=path, api_token=TOKEN,
        session_coordinator=coordinator, assistance_broker=broker,
    ))
    return client, coordinator, broker


def test_api_is_opt_in_bearer_protected_and_cannot_start_worker(tmp_path):
    client, owner, broker = _api(tmp_path)
    endpoint = "/api/v1/accounts/alpha/auth-assistance"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=AUTH).json() == {
        "enabled": True, "account_id": "alpha", "ticket": None,
    }
    assert client.get("/api/v1/accounts/other/auth-assistance", headers=AUTH).status_code == 404
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.MANUAL_CHALLENGE)
        url = endpoint + "/" + ticket["ticket_id"] + "/approve"
        assert client.post(url, json={"confirmed": True}).status_code == 401
        assert client.post(url, headers=AUTH, json={"confirmed": False}).status_code == 422
        assert client.post(url, headers=AUTH, json={
            "confirmed": True, "password": "private-credential",
        }).status_code == 422
        assert "private-credential" not in client.post(
            url, headers=AUTH, json={"confirmed": False},
        ).text
        assert client.post(url, headers=AUTH, json={"confirmed": True}).status_code == 200
        assert owner.status("alpha") == "assisted_login"
        assert client.post(url, headers=AUTH, json={"confirmed": True}).status_code == 409
        # HTTP has no route that can assert authenticated, resume a task or start a login.
        assert client.post(endpoint, headers=AUTH, json={}).status_code == 405
        assert owner.status("alpha") != "authenticated"
    assert broker.snapshot("alpha")["ticket"]["state"] == "operator_ready"


def test_api_disabled_default_and_rejects_mismatched_coordinator(tmp_path):
    client, owner, broker = _api(tmp_path)
    assert client.get("/api/v1/accounts/alpha/auth-assistance", headers=AUTH).status_code == 200
    path = tmp_path / "accounts.toml"
    read_only = TestClient(create_app(accounts_path=path, api_token=TOKEN))
    assert read_only.get("/api/v1/accounts/alpha/auth-assistance", headers=AUTH).json() == {
        "enabled": False, "account_id": "alpha", "ticket": None,
    }
    assert read_only.post(
        "/api/v1/accounts/alpha/auth-assistance/" + str(uuid.uuid4()) + "/approve",
        headers=AUTH, json={"confirmed": True},
    ).status_code == 503
    with pytest.raises(ValueError, match="authoritative"):
        create_app(accounts_path=path, api_token=TOKEN, assistance_broker=broker)
    with pytest.raises(ValueError, match="authoritative"):
        create_app(
            accounts_path=path, api_token=TOKEN, session_coordinator=owner,
            assistance_broker=broker, enable_account_editing=True,
        )


def test_api_replay_and_invalid_id_failure_paths(tmp_path):
    client, owner, broker = _api(tmp_path)
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.LOGIN_REQUIRED)
        path = "/api/v1/accounts/alpha/auth-assistance/"
        assert client.post(path + "not-a-uuid/approve", headers=AUTH,
                           json={"confirmed": True}).status_code == 422
        assert client.post(path + str(uuid.uuid4()) + "/approve", headers=AUTH,
                           json={"confirmed": True}).status_code == 409
        broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        broker.begin_validation(lease, ticket["ticket_id"])
        broker.complete_validation(lease, ticket["ticket_id"], valid=True)
        assert owner.status("alpha") == "authenticated"


@pytest.mark.parametrize("ttl", [0, 20, 3601, 1.5, True])
def test_bad_ttl_is_rejected(owner, ttl):
    with pytest.raises(ValueError):
        AssistanceBroker(owner, ttl_seconds=ttl)


def test_worker_phase_and_assertions_are_guarded(owner, broker):
    with owner.acquire("alpha") as lease:
        ticket = broker.request(lease, AssistanceReason.LOGIN_REQUIRED)
        with pytest.raises(AssistanceConflict):
            broker.begin_validation(lease, ticket["ticket_id"])
        with pytest.raises(AssistanceConflict):
            broker.complete_validation(lease, ticket["ticket_id"], valid=True)
        broker.approve("alpha", ticket["ticket_id"], confirmed=True)
        broker.begin_validation(lease, ticket["ticket_id"])
        with pytest.raises(TypeError):
            broker.complete_validation(lease, ticket["ticket_id"], valid="true")
