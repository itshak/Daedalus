"""Host-secret import tests use only fake IkaBot registry and fake keyring."""
from __future__ import annotations

import pytest

from daedalus.accounts import Account
from daedalus.recovery_credentials import (
    RecoveryCredentials,
    RecoveryCredentialsUnavailable,
)


class MemoryStore:
    def __init__(self):
        self.values={}
    def set_password(self,service,username,value):
        self.values[(service,username)]=value
    def get_password(self,service,username):
        return self.values.get((service,username))
    def delete_password(self,service,username):
        self.values.pop((service,username),None)


@pytest.fixture
def fixture(monkeypatch):
    from ikabot.helpers import sessionStorage
    entries={
        "monjo@example.invalid":{
            "email":"monjo@example.invalid",
            "players":{"monjo":{"53":{"ru":{}}}},
            "shared":{"lobby":{"gf-token-production":"fake-lobby-token-with-enough-length"}},
        },
    }
    monkeypatch.setattr(sessionStorage,"get_saved_users",lambda:list(entries))
    monkeypatch.setattr(sessionStorage,"find_user_file_for_email",
                        lambda email:(email,False) if email in entries else (None,False))
    monkeypatch.setattr(sessionStorage,"read_json_file",
                        lambda path,default:entries.get(path,default))
    acc=Account("acct","s53-ru","monjo","Monjo",True)
    store=MemoryStore()
    return acc,RecoveryCredentials(store),store,entries


def test_exact_local_migration_binds_email_and_encrypts_token_without_returning_it(fixture):
    acc,creds,store,_entries=fixture
    assert not creds.available(acc)
    assert creds.import_saved(acc,confirmed=True) is True
    assert creds.available(acc)
    email,token=creds.retrieve(acc)
    assert email=="monjo@example.invalid"
    assert token=="fake-lobby-token-with-enough-length"
    assert len(store.values)==2
    assert token not in str({"imported": True})
    creds.forget(acc,confirmed=True)
    assert not creds.available(acc)


def test_import_requires_opt_in(fixture):
    acc,creds,store,_entries=fixture
    with pytest.raises(RecoveryCredentialsUnavailable):
        creds.import_saved(acc,confirmed=False)
    assert store.values=={}


def test_wrong_world_player_or_ambiguous_saved_accounts_fail_closed(fixture,monkeypatch):
    acc,creds,store,entries=fixture
    other=Account("acct","s53-ru","NotMonjo","No",True)
    with pytest.raises(RecoveryCredentialsUnavailable):
        creds.import_saved(other,confirmed=True)
    entries["other@example.invalid"]={
        "email":"other@example.invalid","players":{"monjo":{"53":{"ru":{}}}},
        "shared":{"lobby":{"gf-token-production":"another-fake-lobby-token"}},
    }
    with pytest.raises(RecoveryCredentialsUnavailable,match="unambiguously"):
        creds.import_saved(acc,confirmed=True)
    assert store.values=={}


def test_bad_saved_token_never_creates_email_binding(fixture):
    acc,creds,store,entries=fixture
    entries["monjo@example.invalid"]["shared"]["lobby"]["gf-token-production"]="short"
    with pytest.raises(RecoveryCredentialsUnavailable,match="format"):
        creds.import_saved(acc,confirmed=True)
    assert store.values=={}


def test_identity_reassignment_does_not_reuse_protected_token(fixture):
    acc,creds,_store,_entries=fixture
    creds.import_saved(acc,confirmed=True)
    changed=Account("acct","s53-ru","Other","Other",True)
    assert not creds.available(changed)
    with pytest.raises(RecoveryCredentialsUnavailable):
        creds.retrieve(changed)


def test_invalid_secret_not_printed_on_import_failure(fixture,capsys):
    acc,creds,_store,entries=fixture
    secret="PRIVATE-secret-password"
    entries["monjo@example.invalid"]["shared"]["lobby"]["gf-token-production"]=secret
    creds.import_saved(acc,confirmed=True)
    assert secret not in capsys.readouterr().out
