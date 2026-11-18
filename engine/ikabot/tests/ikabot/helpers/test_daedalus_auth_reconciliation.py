"""Reconciled production-authentication behaviors, with synthetic tokens only.

No account directory, world session or Gameforge/network endpoint is accessed.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ikabot import config
from ikabot.helpers import apiComm, pedirInfo
from ikabot.web import session as session_module
from ikabot.web.session import Session
from requests.exceptions import ConnectTimeout, ReadTimeout


def fake_session():
    return SimpleNamespace(
        api_user_agent=None,
        user_agent="SyntheticUserAgent",
        locale="en-GB",
        timezone_id="UTC",
    )


def reply(status, payload=None, text="SYNTHETIC-PRIVATE-RESPONSE-MUST-NOT-LEAK"):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=text)


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setattr(apiComm, "getAddress", lambda _domain: "https://token.invalid")
    sleeps = []
    monkeypatch.setattr(apiComm.time, "sleep", sleeps.append)
    return sleeps


def test_blackbox_retry_is_bounded_and_only_retries_transport_failures(fake_api, monkeypatch):
    sequence = [ConnectTimeout("hidden-connection-value"), ReadTimeout("hidden-response-value"),
                reply(200, payload="Abc123")]
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        item = sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(apiComm, "get", request)
    assert apiComm.getNewBlackBoxToken(fake_session(), retries=2, backoff=0.5) == "tra:Abc123"
    assert len(calls) == 3
    assert fake_api == [0.5, 1.0]
    assert all(call[0] == "https://token.invalid/v1/token" for call in calls)
    assert all(call[1]["timeout"] == config.blackboxTokenTimeout for call in calls)


def test_400_compatibility_fallback_preserved_without_extra_login(fake_api, monkeypatch):
    replies = [reply(422), reply(200, payload="tra:Aa1")]
    calls = []
    monkeypatch.setattr(apiComm, "get", lambda *_args, **kwargs: (
        calls.append(kwargs["params"]) or replies.pop(0)
    ))
    assert apiComm.getNewBlackBoxToken(fake_session(), retries=0) == "tra:Aa1"
    assert len(calls) == 2
    assert set(calls[0]) == {"user_agent", "locale", "timezone_id"}
    assert calls[1] == {"user_agent": "SyntheticUserAgent"}
    assert fake_api == []


def test_token_api_error_cannot_expose_secret_response_or_retry_unauthorized(fake_api, monkeypatch):
    calls = []
    monkeypatch.setattr(apiComm, "get", lambda *_args, **_kwargs: (
        calls.append(True) or reply(401, payload={"secret": "hidden"})
    ))
    with pytest.raises(RuntimeError, match="HTTP 401") as info:
        apiComm.getNewBlackBoxToken(fake_session(), retries=3)
    assert "SYNTHETIC-PRIVATE" not in str(info.value)
    assert "hidden" not in str(info.value)
    assert len(calls) == 1
    assert fake_api == []


def test_transport_error_suppresses_sensitive_exception_chain(fake_api, monkeypatch):
    def failing(*_args, **_kwargs):
        raise ReadTimeout("SYNTHETIC-SECRET-ERROR")
    monkeypatch.setattr(apiComm, "get", failing)
    with pytest.raises(RuntimeError, match="manual assistance") as info:
        apiComm.getNewBlackBoxToken(fake_session(), retries=0)
    assert "SYNTHETIC-SECRET" not in str(info.value)
    assert info.value.__cause__ is None


@pytest.mark.parametrize("retries,backoff", [(-1, 0), (4, 0), (True, 0), (1, -1),
                                          (1, float("nan")), (1, 6)])
def test_retry_configuration_rejected_before_network(fake_api, monkeypatch, retries, backoff):
    monkeypatch.setattr(apiComm, "get", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("Unexpected network call")
    ))
    with pytest.raises(ValueError):
        apiComm.getNewBlackBoxToken(fake_session(), retries=retries, backoff=backoff)


def test_token_api_malformed_payload_fails_closed(fake_api, monkeypatch):
    for payload in (None, {"status": "error", "message": "hidden"}, "", "a" * 8193):
        monkeypatch.setattr(apiComm, "get", lambda *_args, value=payload, **_kwargs: reply(200, value))
        with pytest.raises(RuntimeError):
            apiComm.getNewBlackBoxToken(fake_session(), retries=0)


def test_detached_input_eof_fails_fast_instead_of_reprompting(monkeypatch):
    monkeypatch.setattr(config, "predetermined_input", [])
    attempts = Mock(side_effect=EOFError("synthetic"))
    monkeypatch.setattr("builtins.input", attempts)
    monkeypatch.setattr(pedirInfo.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    with pytest.raises(EOFError, match="detached"):
        pedirInfo.read(msg="Synthetic prompt: ")
    assert attempts.call_count == 1


def test_detached_failed_token_api_never_requests_manual_cookie_or_blackbox(monkeypatch):
    probe = Session.__new__(Session)
    probe.padre = True
    probe.logger = Mock()
    probe.api_user_agent = None
    probe.user_agent = "SyntheticAgent"
    monkeypatch.setattr(session_module, "_can_request_manual_auth", lambda: False)
    monkeypatch.setattr(session_module, "getNewBlackBoxToken", Mock(side_effect=RuntimeError(
        "synthetic unsafe trace must never be printed"
    )))
    blocked = Mock(side_effect=AssertionError("Manual prompt reached"))
    monkeypatch.setattr(probe, "_Session__ask_manual_blackbox_payload", blocked)
    monkeypatch.setattr(probe, "_Session__ask_lobby_cookie", blocked)
    with pytest.raises(RuntimeError, match="Manual blackbox assistance required") as info:
        probe._Session__load_new_blackbox_token(allow_lobby_cookie_fallback=True)
    assert "unsafe trace" not in str(info.value)
    blocked.assert_not_called()


def test_detached_expired_login_never_prompts_for_password(monkeypatch):
    probe = Session.__new__(Session)
    probe.padre = True
    probe.password = ""
    probe.mail = "synthetic@example.invalid"
    monkeypatch.setattr(session_module, "_can_request_manual_auth", lambda: False)
    monkeypatch.setattr(session_module, "read", Mock(side_effect=AssertionError("prompt")))
    with pytest.raises(RuntimeError, match="no interactive terminal"):
        probe._Session__ask_password_if_needed()


def test_auth_config_has_private_bounded_network_defaults():
    assert 0 <= config.blackboxTokenRetries <= 3
    assert 0 < config.blackboxTokenTimeout[0] <= 30
    assert 0 < config.blackboxTokenTimeout[1] <= 120
