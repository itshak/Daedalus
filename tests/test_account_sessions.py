"""No game network access: host-local leases and state transitions under test."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from daedalus.account_sessions import (
    AccountSessionCoordinator,
    SessionBusyError,
    SessionDisabledError,
    SessionPhase,
    SessionTransitionError,
    default_session_state_dir,
)
from daedalus.accounts import Account


def account(
    account_id: str = "alpha",
    *,
    world: str = "s301-en",
    player: str = "ExampleOne",
    enabled: bool = True,
) -> Account:
    return Account(id=account_id, world=world, player=player, label="Example", enabled=enabled)


def test_claim_starts_validating_without_authenticating(tmp_path: Path):
    coordinator = AccountSessionCoordinator([account()], state_dir=tmp_path / "locks")
    assert coordinator.status("alpha") == "not_connected"
    with coordinator.acquire("alpha") as owned:
        assert owned.phase is SessionPhase.VALIDATING_SESSION
        assert coordinator.status("alpha") == "validating_session"
        with pytest.raises(SessionBusyError):
            coordinator.acquire("alpha")
    assert coordinator.status("alpha") == "not_connected"
    assert owned.phase is SessionPhase.CLOSED


def test_active_game_session_is_not_displaced_by_assistance(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with manager.acquire("alpha") as owned:
        owned.transition(SessionPhase.NEEDS_ASSISTANCE)
        owned.transition(SessionPhase.ASSISTED_LOGIN)
        assert manager.status("alpha") == "assisted_login"
        with pytest.raises(SessionBusyError):
            AccountSessionCoordinator([account()], state_dir=tmp_path).acquire("alpha")
        owned.transition(SessionPhase.VALIDATING_HANDOFF)
        owned.transition(SessionPhase.AUTHENTICATED)
        assert manager.status("alpha") == "authenticated"
    assert manager.status("alpha") == "not_connected"


def test_authentication_requires_handoff_validation(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with manager.acquire("alpha") as owned:
        owned.transition(SessionPhase.NEEDS_ASSISTANCE)
        owned.transition(SessionPhase.ASSISTED_LOGIN)
        with pytest.raises(SessionTransitionError, match="Cannot change"):
            owned.transition(SessionPhase.AUTHENTICATED)
        assert owned.phase == SessionPhase.ASSISTED_LOGIN
        owned.transition(SessionPhase.VALIDATING_HANDOFF)
        owned.transition(SessionPhase.NEEDS_ASSISTANCE)
        assert owned.phase == SessionPhase.NEEDS_ASSISTANCE


def test_invalid_status_transition_does_not_change_state(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with manager.acquire("alpha") as owned:
        with pytest.raises(SessionTransitionError):
            owned.transition(SessionPhase.ASSISTED_LOGIN)
        assert owned.phase == SessionPhase.VALIDATING_SESSION
        with pytest.raises(SessionTransitionError, match="Expected"):
            owned.transition("authenticated")  # type: ignore[arg-type]


def test_failure_recovery_starts_by_validating_session(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with manager.acquire("alpha") as owned:
        owned.transition(SessionPhase.FAILED)
        with pytest.raises(SessionTransitionError):
            owned.transition(SessionPhase.AUTHENTICATED)
        owned.transition(SessionPhase.VALIDATING_SESSION)
        owned.transition(SessionPhase.AUTHENTICATED)
        owned.transition(SessionPhase.PAUSED)
        owned.transition(SessionPhase.VALIDATING_SESSION)
        assert owned.phase is SessionPhase.VALIDATING_SESSION


def test_close_twice_and_closed_session_cannot_transition(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    owned = manager.acquire("alpha")
    owned.close()
    owned.close()
    assert manager.status("alpha") == "not_connected"
    with pytest.raises(SessionTransitionError, match="closed"):
        owned.transition(SessionPhase.AUTHENTICATED)
    with manager.acquire("alpha"):
        pass


def test_exception_closes_lease(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with pytest.raises(RuntimeError, match="example"), manager.acquire("alpha"):
        raise RuntimeError("example")
    with manager.acquire("alpha") as owned:
        assert owned.phase is SessionPhase.VALIDATING_SESSION


def test_two_distinct_accounts_do_not_block_one_another(tmp_path: Path):
    manager = AccountSessionCoordinator(
        [account(), account("beta", world="s302-en", player="ExampleTwo")],
        state_dir=tmp_path,
    )
    with manager.acquire("alpha"), manager.acquire("beta"):
        assert manager.status("alpha") == "validating_session"
        assert manager.status("beta") == "validating_session"


def test_casefolded_identity_prevents_duplicate_host_ownership(tmp_path: Path):
    first = AccountSessionCoordinator([account()], state_dir=tmp_path)
    same_player = AccountSessionCoordinator(
        [account("beta", world="S301-EN", player="exampleone")],
        state_dir=tmp_path,
    )
    with first.acquire("alpha"), pytest.raises(
        SessionBusyError, match="already has a session owner"
    ):
        same_player.acquire("beta")
    with same_player.acquire("beta"):
        pass


def test_disabled_account_cannot_claim_lease(tmp_path: Path):
    manager = AccountSessionCoordinator([account(enabled=False)], state_dir=tmp_path)
    assert manager.status("alpha") == "disabled"
    with pytest.raises(SessionDisabledError):
        manager.acquire("alpha")
    assert not list(tmp_path.iterdir())


def test_unknown_account_rejected_without_leaking_identity(tmp_path: Path):
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    with pytest.raises(KeyError, match="Unknown account"):
        manager.status("different")
    with pytest.raises(KeyError, match="Unknown account"):
        manager.acquire("different")


def test_duplicate_config_id_and_world_player_fails(tmp_path: Path):
    with pytest.raises(ValueError, match="Duplicate account id"):
        AccountSessionCoordinator([account(), account()], state_dir=tmp_path)
    with pytest.raises(ValueError, match="Duplicate world/player"):
        AccountSessionCoordinator([account(), account("beta")], state_dir=tmp_path)


def test_file_names_do_not_contain_account_identifiers(tmp_path: Path):
    state_dir = tmp_path / "locks"
    manager = AccountSessionCoordinator([account()], state_dir=state_dir)
    with manager.acquire("alpha"):
        lock_files = list(state_dir.iterdir())
        assert len(lock_files) == 1
        name = lock_files[0].name
        assert name.endswith(".lock")
        assert "alpha" not in name
        assert "example" not in name
        if os.name != "nt":
            assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700
            assert stat.S_IMODE(lock_files[0].stat().st_mode) == 0o600


def test_default_path_is_outside_checkout(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    if os.name == "nt":
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_session_state_dir() == tmp_path / "daedalus" / "session-locks"
    assert not default_session_state_dir().exists()


def test_cross_process_lock_is_released_on_close(tmp_path: Path):
    """A separate Python interpreter is blocked while the owner holds its lock."""
    manager = AccountSessionCoordinator([account()], state_dir=tmp_path)
    child_code = """
import sys
from daedalus.accounts import Account
from daedalus.account_sessions import AccountSessionCoordinator, SessionBusyError
item = Account(id='child', world='s301-en', player='ExampleOne', label='Example', enabled=True)
manager = AccountSessionCoordinator([item], state_dir=sys.argv[1])
try:
    with manager.acquire('child'):
        pass
except SessionBusyError:
    sys.exit(33)
sys.exit(0)
"""
    with manager.acquire("alpha"):
        result = subprocess.run(
            [sys.executable, "-c", child_code, str(tmp_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 33, result.stderr
    result = subprocess.run(
        [sys.executable, "-c", child_code, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_symlink_lock_directory_is_rejected(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating directory symlinks requires additional privileges")
    manager = AccountSessionCoordinator([account()], state_dir=alias)
    with pytest.raises(RuntimeError, match="real directory"):
        manager.acquire("alpha")
