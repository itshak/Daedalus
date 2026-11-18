"""Synthetic server-side player attestation, not saved metadata claims."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ikabot.helpers.ipc import IPCServer
from ikabot.helpers.serverIdentity import attest_player_from_world_html
from ikabot.web.session import Session


@pytest.mark.parametrize("html", [
    '<div id="gameHeader"><span id="avatarName">ExamplePlayer</span></div>',
    '<div id="playerName"> ExamplePlayer </div>',
    ('<div id="gameHeader"><span id="avatarName">ExamplePlayer</span>'
     '<div id="playerName">ExamplePlayer</div></div>'),
    '<script>var game = {"avatarId":42,"avatarName":"ExamplePlayer"}</script>',
    '<script>window.game = {"avatarName":"ExamplePlayer"}</script>',
    ('<div class="GF_toolbar"><ul><li class="avatarName">'
     '<a id="avatarPictureSmall"><img src="/avatar.png"></a>'
     'ExamplePlayer</li></ul></div>'),
    ('<div id="other"><div class="GF_toolbar layout"><ul>'
     '<li class="status avatarName">ExamplePlayer</li>'
     '</ul></div></div>'),
])
def test_server_rendered_own_player_is_attested(html):
    assert attest_player_from_world_html(html, "ExamplePlayer")
    assert attest_player_from_world_html(html, "exampleplayer")
    assert not attest_player_from_world_html(html, "AnotherPlayer")


@pytest.mark.parametrize("html", [
    "",
    '<div>Welcome, ExamplePlayer</div>',
    '<div class="chat">ExamplePlayer</div>',
    '<script>const guessed = {"avatarName":"ExamplePlayer"}</script>',
    '<span id="avatarName">OtherPlayer</span>',
    '<span id="avatarName"></span>',
    ('<span id="avatarName">ExamplePlayer</span>'
     '<span id="avatarName">OtherPlayer</span>'),
    ('<script>var game = {"avatarName":"OtherPlayer"}</script>'
     '<span id="avatarName">ExamplePlayer</span>'),
    '<input type="hidden" id="playerName" value="ExamplePlayer">',
    '<span id="avatarName">ExamplePlayer</span><span id="playerName">OtherPlayer</span>',
    '<span id="avatarName">ExamplePlayer\\x00</span>',
    '<li class="avatarName">ExamplePlayer</li>',
    '<div class="toolbar"><li class="avatarName">ExamplePlayer</li></div>',
    '<div class="GF_toolbar"><li class="avatarName">OtherPlayer</li></div>',
    ('<div class="GF_toolbar"><li class="avatarName">ExamplePlayer</li></div>'
     '<span id="playerName">OtherPlayer</span>'),
    '<div class="GF_toolbar"><li class="avatarName"></li></div>',
    '<div class="GF_toolbar"><li class="avatarName">ExamplePlayer</div>',

])
def test_missing_wrong_or_ambiguous_server_identity_fails_closed(html):
    assert attest_player_from_world_html(html, "ExamplePlayer") is False


@pytest.mark.parametrize("expected", ["", "Example\\nPlayer", "X" * 1024, None])
def test_invalid_configured_player_is_rejected(expected):
    assert not attest_player_from_world_html(
        '<span id="avatarName">ExamplePlayer</span>', expected
    )


def _existing_session():
    session = MagicMock()
    session.username = "ExamplePlayer"  # Local identity is not authoritative.
    session.mundo = "301"
    session.servidor = "en"
    session.logged = True
    session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
    session.isExpired.return_value = False
    return session


@pytest.mark.parametrize("html", [
    '<div id="gameHeader">Game</div><input name="actionRequest">',
    '<span id="avatarName">OtherPlayer</span><input name="actionRequest">',
    ('<span id="avatarName">ExamplePlayer</span><span id="playerName">OtherPlayer</span>'
     '<input name="actionRequest">'),
])
def test_existing_ipc_cannot_attest_local_player_without_world_proof(html):
    session = _existing_session()
    session.s.get.return_value = MagicMock(
        status_code=200, url=session.urlBase, text=html,
    )
    server = IPCServer(default_session=session)
    with patch.object(Session, "from_saved", side_effect=AssertionError("Login attempted")):
        reply = server.handle_request({
            "action": "validate_session_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
    assert reply["status"] == "ok"
    assert reply["username"] == "ExamplePlayer"  # Not proof.
    assert reply["session_valid"] is False
    assert reply["player_attested"] is False
    assert "actionRequest" not in str(reply)
    session.s.get.assert_called_once()
