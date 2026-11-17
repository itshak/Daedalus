"""Daedalus-specific safety tests for the unreleased upstream IkaBot IPC patch.

Never contact Gameforge or restore saved sessions. Existing-only IPC actions
must not call Session.from_saved under any error or success path.
"""

from unittest.mock import MagicMock, patch

from ikabot.helpers.ipc import IPCServer


def make_session(player="ExamplePlayer", world="301", server="en", logged=True):
    session = MagicMock()
    session.mail = "synthetic@example.invalid"
    session.username = player
    session.mundo = world
    session.servidor = server
    session.login_servidor = server
    session.logged = logged
    return session


def test_list_sessions_reports_nonsecret_in_memory_identities():
    session = make_session()
    inactive = make_session(player="Other", logged=False)
    server = IPCServer(default_session=session)
    server._sessions.append(inactive)

    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        response = server.handle_request({"action": "list_sessions"})

    assert response["status"] == "ok"
    assert response["sessions"] == [{"world": "s301-en", "player": "ExamplePlayer"}]
    assert "email" not in str(response)
    assert "synthetic@example.invalid" not in str(response)


def test_existing_only_cities_use_matching_session_without_restoring():
    session = make_session()
    server = IPCServer(default_session=session)
    cities = {
        123: {"name": "Athens", "coords": "[1:2]", "tradegood": 1},
    }
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
        patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([123], cities)) as mocked,
    ):
        response = server.handle_request(
            {
                "action": "list_cities_existing",
                "world": "s301-en",
                "player": "ExamplePlayer",
            }
        )

    assert response["status"] == "ok"
    assert response["world"] == "s301-en"
    assert response["username"] == "ExamplePlayer"
    assert response["cities"][0] == {
        "id": 123,
        "name": "Athens",
        "coords": "1:2",
        "tradegood": "wine",
    }
    assert "email" not in response
    mocked.assert_called_once_with(session)


def test_missing_or_ambiguous_identity_never_launches_login():
    session = make_session()
    server = IPCServer(default_session=session)
    requests = [
        {"action": "list_cities_existing", "world": "s301-en"},
        {"action": "list_cities_existing", "player": "ExamplePlayer"},
        {"action": "list_cities_existing", "world": "s302-en", "player": "ExamplePlayer"},
        {"action": "list_cities_existing", "world": "s301-en", "player": "WrongPlayer"},
    ]
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        for request in requests:
            response = server.handle_request(request)
            assert response["status"] == "error"

        # Two matching sessions are unsafe; select neither.
        server._sessions.append(make_session())
        response = server.handle_request(
            {"action": "list_cities_existing", "world": "s301-en", "player": "ExamplePlayer"}
        )
        assert response["status"] == "error"


def test_original_list_cities_action_is_preserved_for_upstream_cli():
    session = make_session()
    server = IPCServer(default_session=session)
    cities = {1: {"name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([1], cities)):
        response = server.handle_request(
            {"action": "list_cities", "world": "s301-en", "player": "ExamplePlayer"}
        )
    assert response["status"] == "ok"
    assert response["email"] == "synthetic@example.invalid"


def test_existing_only_warehouse_uses_real_game_session_and_redacts_html():
    session = make_session()
    session.get.return_value = (
        '<html><input name="actionRequest" value="private-session-token">'
        '<span id="js_plunderable_wood">2.97M<div class="tooltip">2,970,123</div></span>'
        '<span id="js_plunderable_wine">17,254</span>'
        '<span id="js_capacity_wood">1,000,000</span></html>'
    )
    cities = {42: {"name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    server = IPCServer(default_session=session)
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
        patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([42], cities)),
    ):
        resp = server.handle_request(
            {"action": "warehouse_snapshots_existing", "world": "s301-en", "player": "ExamplePlayer"}
        )
    assert resp["status"] == "ok"
    assert resp["cities"][0]["unsecured"] == {"wood": "2,970,123", "wine": "17,254"}
    assert resp["cities"][0]["capacity"] == "1,000,000"
    assert "private-session-token" not in str(resp)
    assert "actionRequest" not in str(resp)
    assert "email" not in str(resp)
    session.get.assert_called_once_with("view=warehouse&cityId=42", noIndex=True)


def test_warehouse_missing_auth_does_not_open_session():
    server = IPCServer()
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        resp = server.handle_request(
            {"action": "warehouse_snapshots_existing", "world": "s301-en", "player": "ExamplePlayer"}
        )
    assert resp["status"] == "error"
