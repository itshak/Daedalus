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
    assert resp["cities"][0]["island"] == "1:2"
    assert "private-session-token" not in str(resp)
    assert "actionRequest" not in str(resp)
    assert "email" not in str(resp)
    session.get.assert_called_once_with("view=warehouse&cityId=42", noIndex=True)


def test_warehouse_malformed_coords_dont_leak_into_ipc():
    session = make_session()
    session.get.return_value = '<span id="js_plunderable_wood">0</span>'
    cities = {42: {"name": "Athens", "coords": "[token-cookie-unsafe]", "tradegood": 0}}
    server = IPCServer(default_session=session)
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
        patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([42], cities)),
    ):
        response = server.handle_request({
            "action": "warehouse_snapshots_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
    assert response["status"] == "ok"
    assert response["cities"][0]["island"] is None
    assert "token-cookie-unsafe" not in str(response)


def test_warehouse_missing_auth_does_not_open_session():
    server = IPCServer()
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        resp = server.handle_request(
            {"action": "warehouse_snapshots_existing", "world": "s301-en", "player": "ExamplePlayer"}
        )
    assert resp["status"] == "error"


def test_managed_task_start_list_and_stop_for_existing_session_only():
    def synthetic_task(session, minutes=10):
        pass

    # The existing-session path accepts only built-in IkaBot tasks, never
    # dynamically registered external functions.
    synthetic_task.__module__ = "ikabot.function.alertAttacks"
    synthetic_task.prepare = None

    class FakeProcess:
        pid = 42424
        alive = True
        started = False

        def start(self):
            self.started = True

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.alive = False

        def join(self, timeout):
            assert timeout == 4.0

    proc = FakeProcess()

    def fake_process(*_args, **kwargs):
        kwargs["args"][3].set()
        return proc

    session = make_session()
    server = IPCServer(default_session=session)
    identity = {"world": "s301-en", "player": "ExamplePlayer"}
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
        patch("ikabot.helpers.ipc.updateProcessList"),
        patch("ikabot.helpers.ipc.multiprocessing.Process", side_effect=fake_process),
        patch("ikabot.helpers.ipc._resolve_task", return_value=("alertAttacks", synthetic_task)),
    ):
        started = server.handle_request({
            "action": "start_task_existing", **identity,
            "task": "alertAttacks", "config": {"minutes": 10},
            "request_id": "12345678-1234-4123-8123-123456789abc",
        })
        assert started["status"] == "ok"
        assert started["task"] == "alertAttacks"
        assert "email" not in started
        assert len(started["task_id"]) == 24
        assert proc.started
        task_id = started["task_id"]

        listed = server.handle_request({"action": "list_tasks_existing", **identity})
        assert listed["tasks"][0]["task_id"] == task_id
        assert listed["tasks"][0]["status"] == "running"
        assert listed["tasks"][0]["pid"] == proc.pid

        unauthorized = server.handle_request({
            "action": "stop_task_existing", "world": "s301-en", "player": "OtherPlayer",
            "task_id": task_id,
        })
        assert unauthorized["status"] == "error"
        assert proc.alive
        stopped = server.handle_request({
            "action": "stop_task_existing", **identity, "task_id": task_id,
        })
        assert stopped["status"] == "ok"
        assert stopped["task_status"] == "stopped"
        assert not proc.alive
        listed = server.handle_request({"action": "list_tasks_existing", **identity})
        assert listed["tasks"][0]["status"] == "stopped"


def test_managed_task_never_creates_missing_session():
    server = IPCServer()
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        response = server.handle_request({
            "action": "start_task_existing", "world": "s301-en", "player": "ExamplePlayer",
            "task": "alertAttacks", "config": {"minutes": 10},
        })
    assert response["status"] == "error"
    assert server._daedalus_tasks == {}


def test_active_session_validation_reads_exact_world_without_login():
    session = make_session()
    session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
    session.isExpired.return_value = False
    session.s.get.return_value = MagicMock(
        status_code=200,
        url="https://s301-en.ikariam.gameforge.com/index.php?",
        text='<div id="gameHeader">Ikariam</div><span id="avatarName">ExamplePlayer</span>'
             '<input name="actionRequest" value="private"/>',
    )
    server = IPCServer(default_session=session)
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("new login!")):
        response = server.handle_request({
            "action": "validate_session_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
    assert response == {
        "status": "ok", "world": "s301-en", "username": "ExamplePlayer",
        "session_valid": True, "player_attested": True,
    }
    assert "actionRequest" not in str(response)
    assert "private" not in str(response)
    session.s.get.assert_called_once_with(
        "https://s301-en.ikariam.gameforge.com/index.php?",
        timeout=8, verify=True, allow_redirects=False,
    )


def test_active_validation_rejects_expired_redirect_and_unexpected_html():
    for status_code, url, html in [
        (401, "https://s301-en.ikariam.gameforge.com/index.php?", "actionRequest"),
        (200, "https://lobby.ikariam.gameforge.com/", "actionRequest"),
        (200, "https://s301-en.ikariam.gameforge.com/index.php?", "Please sign in"),
        (200, "https://s301-en.ikariam.gameforge.com/index.php?", "actionRequest index.php?logout"),
    ]:
        session = make_session()
        session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
        session.isExpired.return_value = False
        session.s.get.return_value = MagicMock(
            status_code=status_code, url=url, text=html,
        )
        server = IPCServer(default_session=session)
        result = server.handle_request({
            "action": "validate_session_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
        assert result == {
            "status": "ok", "world": "s301-en", "username": "ExamplePlayer",
            "session_valid": False, "player_attested": False,
        }


def test_active_validation_wrong_identity_never_touches_game_network():
    session = make_session()
    session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
    server = IPCServer(default_session=session)
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")):
        response = server.handle_request({
            "action": "validate_session_existing", "world": "s301-en", "player": "Other",
        })
    assert response["status"] == "error"
    session.s.get.assert_not_called()


def test_active_validation_rejects_untrusted_session_url_without_network():
    session = make_session()
    session.urlBase = "https://example.invalid/"
    server = IPCServer(default_session=session)
    result = server.handle_request({
        "action": "validate_session_existing", "world": "s301-en",
        "player": "ExamplePlayer",
    })
    assert result["session_valid"] is False
    session.s.get.assert_not_called()


def test_dedicated_ipc_refuses_unverified_or_other_existing_owners():
    import ikabot.helpers.ipc as ipc

    session = make_session()
    with patch.object(ipc, "_LOCAL_SERVER", None):
        with patch.object(ipc, "ping_ipc_server", return_value=True):
            with patch.object(ipc, "IPCServer") as constructor:
                with patch.object(ipc, "_StartupLock") as lock:
                    lock.return_value.__enter__.return_value.acquired = True
                    with __import__("pytest").raises(RuntimeError, match="already running"):
                        ipc.start_dedicated_ipc_server(session)
                constructor.assert_not_called()

    session.logged = False
    with __import__("pytest").raises(ValueError, match="verified"):
        ipc.start_dedicated_ipc_server(session)


def test_dedicated_ipc_uses_exclusive_authenticated_session():
    import ikabot.helpers.ipc as ipc

    session = make_session()
    with patch.object(ipc, "_LOCAL_SERVER", None):
        with patch.object(ipc, "ping_ipc_server", return_value=False):
            with patch.object(ipc, "_StartupLock") as lock:
                lock.return_value.__enter__.return_value.acquired = True
                with patch.object(ipc, "IPCServer") as constructor:
                    fake = constructor.return_value
                    fake.start.return_value = fake
                    assert ipc.start_dedicated_ipc_server(session) is fake
                    constructor.assert_called_once_with(default_session=session)
                    assert ipc._LOCAL_SERVER is fake
                    with __import__("pytest").raises(RuntimeError, match="already running"):
                        ipc.start_dedicated_ipc_server(session)
