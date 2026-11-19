"""Release preflight refuses to infer owner acceptance or read credentials."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from daedalus.cli import main
from daedalus.deployment_readiness import deployment_preflight


def _ledger(path: Path, *statuses: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE requests (status TEXT)")
        db.executemany("INSERT INTO requests VALUES (?)", [(status,) for status in statuses])
    if os.name != "nt":
        path.chmod(0o600)


def test_missing_keyring_and_ledger_fail_closed_without_creating_files(tmp_path):
    ledger = tmp_path / "absent.db"
    keyring = tmp_path / "keyrings"
    before = sorted(tmp_path.iterdir())
    result = deployment_preflight(ledger_path=ledger, keyring_directory=keyring)
    assert result["status"] == "blocked"
    assert result["task_ledger"] == {"status": "absent", "unresolved_requests": None}
    assert result["production_cutover_authorized"] is False
    assert result["network_requests_performed"] == 0
    assert result["credential_values_read"] == 0
    assert sorted(tmp_path.iterdir()) == before


def test_unconfirmed_and_dispatching_request_counts_are_anonymous(tmp_path):
    ledger = tmp_path / "ledger.sqlite3"
    _ledger(ledger, "rejected", "started", "unconfirmed", "dispatching")
    keyring = tmp_path / "keyrings"
    keyring.mkdir(mode=0o700)
    (keyring / "default").write_text("session")
    content = ledger.read_bytes()
    result = deployment_preflight(ledger_path=ledger, keyring_directory=keyring)
    assert result["task_ledger"] == {"status": "unresolved", "unresolved_requests": 2}
    assert result["keyring_durability"] == "volatile_session_only_or_unprovisioned"
    assert result["status"] == "blocked"
    assert ledger.read_bytes() == content  # no DB writes
    assert "unconfirmed" not in json.dumps(result)  # no ledger details or raw IDs


def test_persistent_keyring_file_only_proves_possible_durability(tmp_path):
    keyring = tmp_path / "keyrings"
    keyring.mkdir(mode=0o700)
    file = keyring / "login.keyring"
    file.write_bytes(b"opaque test encryption metadata")
    if os.name != "nt":
        file.chmod(0o600)
    ledger = tmp_path / "tasks.db"
    _ledger(ledger, "started", "stopped", "rejected")
    result = deployment_preflight(ledger_path=ledger, keyring_directory=keyring)
    assert result["status"] == "requires_owner_acceptance"
    assert result["task_ledger"] == {"status": "clear", "unresolved_requests": 0}
    assert result["keyring_durability"] == "encrypted_collection_file_present_unverified"
    assert result["keyring_after_reboot"] == "owner_test_not_asserted"
    assert not result["production_cutover_authorized"]


def test_unsafe_file_and_symlink_fail_closed(tmp_path):
    ledger = tmp_path / "data.db"
    _ledger(ledger)
    link = tmp_path / "link.db"
    link.symlink_to(ledger)
    output = deployment_preflight(ledger_path=link, keyring_directory=tmp_path / "not-there")
    assert output["task_ledger"]["status"] == "unsafe_path"
    if os.name != "nt":
        ledger.chmod(0o644)
        output = deployment_preflight(ledger_path=ledger, keyring_directory=tmp_path)
        assert output["task_ledger"]["status"] == "unsafe_permissions"
    broken = tmp_path / "broken.db"
    broken.symlink_to(tmp_path / "does-not-exist")
    assert deployment_preflight(ledger_path=broken)["task_ledger"]["status"] == "unsafe_path"


def test_cli_deployment_check_is_separate_from_standard_secret_free_doctor(tmp_path, capsys):
    ledger = tmp_path / "state.db"
    keyrings = tmp_path / "keyrings"
    _ledger(ledger, "unconfirmed")
    assert main(["doctor", "--deployment-check", "--task-ledger", str(ledger),
                 "--keyring-directory", str(keyrings)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["deployment_preflight"]["task_ledger"]["unresolved_requests"] == 1
    assert result["deployment_preflight"]["status"] == "blocked"
    assert str(tmp_path) not in json.dumps(result)
    assert result["production_ready"] is False
    with pytest.raises(SystemExit) as exc:
        main(["doctor", "--task-ledger", str(ledger)])
    assert exc.value.code == 2


def test_invalid_ledger_does_not_expose_sqlite_error_or_create_journal(tmp_path):
    ledger = tmp_path / "bad.sqlite"
    ledger.write_text("private-token-material-never-appears")
    if os.name != "nt":
        ledger.chmod(0o600)
    state = deployment_preflight(ledger_path=ledger)
    assert state["task_ledger"]["status"] == "unavailable"
    assert "private-token" not in str(state)
    assert not (tmp_path / "bad.sqlite-journal").exists()


def test_encrypted_systemd_store_metadata_is_supported_without_reading_it(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.db"
    _ledger(ledger, "operator_reconciled")
    encrypted = tmp_path / "persistent"
    encrypted.mkdir(mode=0o700)
    blob = encrypted / "opaque.secret"
    blob.write_bytes(b"unencrypted-test-contents-are-never-read")
    blob.chmod(0o600)
    monkeypatch.setenv("DAEDALUS_PROTECTED_STORE_DIR", str(encrypted))
    result = deployment_preflight(ledger_path=ledger)
    assert result["status"] == "requires_owner_acceptance"
    assert result["task_ledger"]["status"] == "clear"
    assert result["keyring_durability"] == "host_encrypted_collection_present_unverified"
    assert "unencrypted-test-contents" not in json.dumps(result)
    assert not result["production_cutover_authorized"]
    blob.chmod(0o644)
    assert deployment_preflight(ledger_path=ledger)["status"] == "blocked"


def test_explicit_operator_directory_overrides_unrelated_shell_keyring(tmp_path, capsys, monkeypatch):
    ledger = tmp_path / "tasks.db"
    _ledger(ledger, "operator_reconciled")
    store = tmp_path / "encrypted"
    store.mkdir(mode=0o700)
    record = store / "opaque.secret"
    record.write_bytes(b"fictional-test-ciphertext")
    if os.name != "nt":
        record.chmod(0o600)
    monkeypatch.delenv("DAEDALUS_PROTECTED_STORE_DIR", raising=False)
    assert main(["doctor", "--deployment-check", "--task-ledger", str(ledger),
                 "--protected-store-directory", str(store)]) == 0
    result = json.loads(capsys.readouterr().out)["deployment_preflight"]
    assert result["status"] == "requires_owner_acceptance"
    assert result["task_ledger"]["unresolved_requests"] == 0
    assert result["keyring_durability"] == "host_encrypted_collection_present_unverified"
