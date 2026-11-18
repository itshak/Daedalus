"""Daedalus cookie-only restore regressions: zero Gameforge network traffic.

Synthetic account data and mocked HTTP responses only. In real operation the
single GET probes a saved world cookie; it never requests a lobby loginLink.
"""

from unittest.mock import MagicMock, patch

import pytest

from ikabot.web.session import Session


@pytest.fixture
def prepared_saved_session():
    data = {
        "email": "synthetic@example.invalid",
        "shared": {"lobby": {"gf-token-production": "lobby-synthetic-should-never-be-used"}},
        "players": {
            "ExamplePlayer": {"301": {"en": {
                "cookies": {"ikariam": "saved-synthetic-cookie", "PHPSESSID": "fake"},
            }}},
        },
    }
    with (
        patch("ikabot.web.session.find_user_file_for_email", return_value=("/fake", False)),
        patch("ikabot.web.session.read_json_file", return_value=data),
        patch("ikabot.web.session.AESCipher", return_value=object()),
        patch("ikabot.web.session.get_session_data", return_value={}),
        patch.object(Session, "_Session__update_proxy", return_value=None),
    ):
        yield


def _response(
    host="s301-en.ikariam.gameforge.com",
    status=200,
    html='<div>City overview</div><span id="avatarName">ExamplePlayer</span>'
         '<input name="actionRequest" value="fake"/>',
):
    return MagicMock(
        url=f"https://{host}/index.php?",
        status_code=status,
        text=html,
        history=[],
    )


def test_cookies_only_restores_exact_identity_without_lobby(prepared_saved_session):
    visited = []

    def get(self, url, **kwargs):
        visited.append((url, kwargs))
        assert url == "https://s301-en.ikariam.gameforge.com/index.php?"
        assert kwargs.get("timeout") == 12
        assert kwargs.get("verify") is True
        assert kwargs.get("allow_redirects") is False
        return _response()

    with (
        patch("ikabot.web.session.requests.Session.get", autospec=True, side_effect=get),
        patch.object(Session, "_Session__test_lobby_cookie", side_effect=AssertionError("lobby!")),
        patch("ikabot.web.session.getNewBlackBoxToken", side_effect=AssertionError("blackbox!")),
    ):
        session = Session.from_saved(
            mail="synthetic@example.invalid", world="s301-en",
            player="ExamplePlayer", cookies_only=True,
        )
    assert session.logged
    assert session.username == "ExamplePlayer"
    assert str(session.mundo) == "301"
    assert session.servidor == "en"
    assert len(visited) == 1


@pytest.mark.parametrize("response", [
    _response(status=500),
    _response(host="lobby.ikariam.gameforge.com"),
    _response(html='<a class="logout" href="?logout">Please log in</a>'),
    _response(html="index.php?logout"),
    _response(html="<div>Public page without a game action token</div>"),
    _response(html='<span id="avatarName">OtherPlayer</span>'
                    '<input name="actionRequest" value="fake"/>'),
])
def test_cookie_only_rejects_failed_world_validation_without_new_login(
    prepared_saved_session, response,
):
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        assert "lobby" not in url
        return response

    with (
        patch("ikabot.web.session.requests.Session.get", autospec=True, side_effect=get),
        patch.object(Session, "_Session__test_lobby_cookie", side_effect=AssertionError("lobby!")),
        patch("ikabot.web.session.getNewBlackBoxToken", side_effect=AssertionError("blackbox!")),
    ):
        with pytest.raises(RuntimeError, match="no new login was attempted"):
            Session.from_saved(
                mail="synthetic@example.invalid", world="s301-en",
                player="ExamplePlayer", cookies_only=True,
            )
    assert len(calls) == 1


def test_wrong_player_never_sends_requests(prepared_saved_session):
    with patch("ikabot.web.session.requests.Session.get",
               side_effect=AssertionError("network!")):
        with pytest.raises(RuntimeError, match="Manual login recovery"):
            Session.from_saved(
                mail="synthetic@example.invalid", world="s301-en",
                player="OtherPlayer", cookies_only=True,
            )


def test_default_engine_contract_still_accepts_existing_cli_signature():
    import inspect

    signature = inspect.signature(Session.from_saved)
    assert "cookies_only" in signature.parameters
    assert signature.parameters["cookies_only"].default is False


def test_manual_cookie_override_uses_only_in_memory_cookie_and_fixed_world(prepared_saved_session):
    imported = "A" * 64
    observed = []

    def get(self, url, **kwargs):
        observed.append((url, self.cookies.get("ikariam")))
        return _response()

    with (
        patch("ikabot.web.session.requests.Session.get", autospec=True, side_effect=get),
        patch.object(Session, "_Session__test_lobby_cookie", side_effect=AssertionError("lobby!")),
        patch("ikabot.web.session.getNewBlackBoxToken", side_effect=AssertionError("blackbox!")),
    ):
        session = Session.from_saved(
            mail="synthetic@example.invalid", world="s301-en",
            player="ExamplePlayer", cookies_only=True,
            world_cookie_override=imported,
        )
    assert session.logged
    assert observed == [("https://s301-en.ikariam.gameforge.com/index.php?", imported)]


@pytest.mark.parametrize("invalid", [
    "", "short", "contains space", "a;cookie", "a\\cookie", "line\nfeed",
    "Ä" * 40, "A" * 4097,
])
def test_invalid_manual_cookie_is_rejected_before_any_network(invalid):
    with patch("ikabot.web.session.requests.Session.get",
               side_effect=AssertionError("network!")):
        with pytest.raises(ValueError, match="Invalid protected world cookie"):
            Session.from_saved(
                mail="synthetic@example.invalid", world="s301-en",
                player="ExamplePlayer", cookies_only=True,
                world_cookie_override=invalid,
            )


def test_manual_cookie_needs_exact_world_and_player_and_opt_in():
    for kwargs in (
        {"cookies_only": False, "world": "s301-en", "player": "ExamplePlayer"},
        {"cookies_only": True, "world": None, "player": "ExamplePlayer"},
        {"cookies_only": True, "world": "s301-en", "player": None},
    ):
        with pytest.raises(ValueError):
            Session.from_saved(
                mail="synthetic@example.invalid",
                world_cookie_override="A" * 48, **kwargs,
            )
