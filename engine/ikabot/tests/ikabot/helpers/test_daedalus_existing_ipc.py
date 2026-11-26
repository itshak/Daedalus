"""Daedalus-specific safety tests for the unreleased upstream IkaBot IPC patch.

Never contact Gameforge or restore saved sessions. Existing-only IPC actions
must not call Session.from_saved under any error or success path.
"""

from unittest.mock import MagicMock, call, patch

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


def test_existing_cities_normalize_live_string_ids_but_keep_legacy_cli_ids():
    session = make_session()
    server = IPCServer(default_session=session)
    cities = {"123": {"name": "Athens", "coords": "[1:2]", "tradegood": 1}}
    with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=(["123"], cities)):
        existing = server.handle_request({
            "action": "list_cities_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
        legacy = server.handle_request({
            "action": "list_cities", "world": "s301-en", "player": "ExamplePlayer",
        })
    assert existing["status"] == "ok"
    assert existing["cities"][0]["id"] == 123
    assert type(existing["cities"][0]["id"]) is int
    assert legacy["status"] == "ok"
    assert legacy["cities"][0]["id"] == "123"


def test_existing_cities_reject_malformed_string_ids():
    session = make_session()
    server = IPCServer(default_session=session)
    for bad in ("0", "-12", "1e2", "1.0", "000123", "123x", True):
        cities = {bad: {"name": "Athens", "coords": "[1:2]", "tradegood": 1}}
        with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([bad], cities)):
            result = server.handle_request({
                "action": "list_cities_existing", "world": "s301-en",
                "player": "ExamplePlayer",
            })
        assert result["status"] == "error"


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
    session.get.side_effect = [
        '<div class="position7 building warehouse level31"></div>',
        ('<html><input name="actionRequest" value="private-session-token">'
         '<span id="js_plunderable_wood">2.97M<div class="tooltip">2,970,123</div></span>'
         '<span id="js_plunderable_wine">17,254</span>'
         '<span id="js_capacity_wood">1,000,000</span></html>'),
    ]
    cities = {42: {"name": "Athens", "coords": "[1:2]", "tradegood": 2}}
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
    assert resp["cities"][0]["island_resource"] == "marble"
    assert "private-session-token" not in str(resp)
    assert "actionRequest" not in str(resp)
    assert "email" not in str(resp)
    assert session.get.call_args_list == [
        call("view=city&cityId=42", noIndex=True),
        call("view=warehouse&cityId=42&position=7", noIndex=True),
    ]


def test_live_warehouse_accepts_string_city_ids_as_typed_ipc_ints():
    session = make_session()
    session.get.side_effect = [
        '<div class="position7 building warehouse level31"></div>',
        '<span id="js_plunderable_wood">100</span>',
    ]
    cities = {"42": {"name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    server = IPCServer(default_session=session)
    with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=(["42"], cities)):
        result = server.handle_request({
            "action": "warehouse_snapshots_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
    assert result["status"] == "ok"
    assert result["cities"][0]["city_id"] == 42
    assert type(result["cities"][0]["city_id"]) is int
    assert result["cities"][0]["unsecured"]["wood"] == "100"
    assert session.get.call_args_list == [
        call("view=city&cityId=42", noIndex=True),
        call("view=warehouse&cityId=42&position=7", noIndex=True),
    ]


def test_current_warehouse_json_updates_are_numeric_and_secret_free():
    session = make_session()
    city_page = (
        '<div class="position8 building warehouse level10"></div>'
        '<div class="position7 building warehouse level31"></div>'
    )
    resource_update = (
        '<script>var resourceUpdater = {'
        '"js_plunderable_wood":{"text":"2.97M","tooltip":"2,970,123"},'
        '"js_plunderable_wine":{"text":"17,254","tooltip":"17,254"},'
        '"js_capacity_wood":{"text":"1,000,000","tooltip":"1,000,000"}'
        '}; var secretNeverReturned = "private-game-cookie";</script>'
    )
    session.get.side_effect = [city_page, resource_update]
    cities = {"42": {"name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    server = IPCServer(default_session=session)
    with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=(["42"], cities)):
        result = server.handle_request({
            "action": "warehouse_snapshots_existing", "world": "s301-en",
            "player": "ExamplePlayer",
        })
    assert result["status"] == "ok"
    city = result["cities"][0]
    assert city["unsecured"] == {"wood": "2,970,123", "wine": "17,254"}
    assert city["capacity"] == "1,000,000"
    assert "private-game-cookie" not in str(result)
    assert session.get.call_args_list == [
        call("view=city&cityId=42", noIndex=True),
        call("view=warehouse&cityId=42&position=7", noIndex=True),
    ]


def test_warehouse_untrusted_slot_or_nonnumeric_update_fails_closed():
    session = make_session()
    cities = {"42": {"name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    server = IPCServer(default_session=session)
    for city_page, page in [
        ('<div class="building warehouse"></div>',
         '<script>{"js_plunderable_wood":{"text":"100"}}</script>'),
        ('<div class="position7 building warehouse"></div>',
         '<script>{"js_plunderable_wood":{"text":"<img src=x>"}}</script>'),
        ('<div class="position7 building warehouse"></div>',
         '<script>{"js_plunderable_wood":{"text":"100"},'
         '"js_plunderable_wood":{"text":"200"}}</script>'),
    ]:
        session.get.side_effect = [city_page, page]
        with patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=(["42"], cities)):
            result = server.handle_request({
                "action": "warehouse_snapshots_existing", "world": "s301-en",
                "player": "ExamplePlayer",
            })
        assert result["status"] == "error"


def test_warehouse_malformed_coords_dont_leak_into_ipc():
    session = make_session()
    session.get.side_effect = [
        '<div class="position7 building warehouse level31"></div>',
        '<span id="js_plunderable_wood">0</span>',
    ]
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
        patch("ikabot.helpers.botComm.telegramDataIsValid", return_value=True),
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


def test_alert_prerequisites_are_scoped_nonsecret_and_do_not_start_tasks():
    session = make_session()
    server = IPCServer(default_session=session)
    with (
        patch("ikabot.helpers.botComm.telegramDataIsValid", return_value=False),
        patch("ikabot.helpers.botComm.discordDataIsValid", return_value=False),
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
    ):
        blocked = server.handle_request({
            "action": "task_preflight_existing", "world": "s301-en",
            "player": "ExamplePlayer", "task": "alertAttacks",
        })
    assert blocked == {"status": "ok", "world": "s301-en", "player": "ExamplePlayer",
                       "task": "alertAttacks", "ready": False,
                       "reason": "notifications_required", "notifications_required": True,
                       "checked": ["notifications"]}
    assert "secret" not in str(blocked)
    assert not server._daedalus_tasks

    with (
        patch("ikabot.helpers.botComm.telegramDataIsValid", return_value=True),
        patch("ikabot.helpers.botComm.discordDataIsValid", side_effect=AssertionError("unneeded")),
    ):
        ready = server.handle_request({
            "action": "task_preflight_existing", "world": "s301-en",
            "player": "ExamplePlayer", "task": "alertAttacks",
        })
    assert ready["ready"] is True
    assert ready["reason"] == "none"


def test_preflight_refuses_mismatched_identity_and_unknown_task():
    server = IPCServer(default_session=make_session())
    for task, world, player in [
        ("alertAttacks", "s301-en", "WrongPlayer"),
        ("alertAttacks", "s999-en", "ExamplePlayer"),
        ("not_a_real_task", "s301-en", "ExamplePlayer"),
        ("../../alertAttacks", "s301-en", "ExamplePlayer"),
    ]:
        reply = server.handle_request({
            "action": "task_preflight_existing", "world": world,
            "player": player, "task": task,
        })
        assert reply["status"] == "error"
        assert not server._daedalus_tasks


def test_known_alert_preflight_rejection_before_process_creation():
    from unittest.mock import MagicMock

    session = make_session()
    server = IPCServer(default_session=session)
    request = {
        "action": "start_task_existing", "world": "s301-en",
        "player": "ExamplePlayer", "task": "alertAttacks",
        "config": {"minutes": 20},
        "request_id": "12345678-1234-4123-8123-123456789abc",
    }
    with (
        patch("ikabot.helpers.botComm.telegramDataIsValid", return_value=False),
        patch("ikabot.helpers.botComm.discordDataIsValid", return_value=False),
        patch("ikabot.helpers.ipc.multiprocessing.Process", side_effect=AssertionError("spawn!")),
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login!")),
    ):
        reply = server.handle_request(request)
    assert reply == {"status": "rejected", "reason": "notifications_required"}
    assert not server._daedalus_tasks


def test_native_military_overview_is_read_only_and_does_not_restore_sessions():
    """The original army parser runs under a verified existing account only."""
    session = make_session()
    server = IPCServer(default_session=session)
    cities = {42: {"id": "42", "name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("restore")),
        patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([42], cities)),
        patch("ikabot.function.viewArmy.getCityMilitaryData",
              return_value="<synthetic army panel>") as military,
        patch("ikabot.function.viewArmy.parseUnits",
              return_value=({"Swordsman": 17}, {"Ballista Ship": 3})),
    ):
        result = server.handle_request({
            "action": "military_overview_existing",
            "world": "s301-en", "player": "ExamplePlayer",
        })
    assert result["status"] == "ok"
    assert result["cities"] == [{
        "city_id": 42, "city_name": "Athens",
        "troops": [{"unit": "Swordsman", "amount": 17}],
        "fleet": [{"unit": "Ballista Ship", "amount": 3}],
    }]
    military.assert_called_once_with(session, "42")
    assert "synthetic@example.invalid" not in str(result)
    session.post.assert_not_called()


def test_native_ship_movements_are_a_read_only_military_advisor_query():
    import json
    session = make_session()
    server = IPCServer(default_session=session)
    cities = {42: {"id": "42", "name": "Athens", "coords": "[1:2]", "tradegood": 0}}
    session.post.return_value = json.dumps([
        [None, {"time": 1000}],
        [None, [None, None, {
            "viewScriptParams": {"militaryAndFleetMovements": [{
                "origin": {"name": "Athens", "avatarName": "ExamplePlayer"},
                "target": {"name": "Sparta", "avatarName": "Other"},
                "event": {"isFleetReturning": False, "missionText": "Transport"},
                "eventTime": 1600, "army": {"amount": 0},
                "fleet": {"amount": 8}, "isHostile": False,
            }]}
        }]],
    ])
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("restore")),
        patch("ikabot.helpers.pedirInfo.getIdsOfCities", return_value=([42], cities)),
    ):
        result = server.handle_request({
            "action": "ship_movements_existing",
            "world": "s301-en", "player": "ExamplePlayer",
        })
    assert result["status"] == "ok"
    assert result["movements"][0]["seconds_remaining"] == 600
    assert result["movements"][0]["destination"] == "Sparta"
    assert result["movements"][0]["ships"] == 8
    assert session.post.call_count == 1
    url = session.post.call_args.args[0]
    assert url.startswith("view=militaryAdvisor&")
    assert "currentCityId=42" in url


def test_native_military_actions_reject_wrong_identity_before_game_queries():
    session = make_session()
    server = IPCServer(default_session=session)
    with patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("restore")):
        for action in ("military_overview_existing", "ship_movements_existing"):
            result = server.handle_request({
                "action": action,
                "world": "s302-en", "player": "ExamplePlayer",
            })
            assert result["status"] == "error"
    session.post.assert_not_called()


def test_active_validation_transient_http_failure_is_not_negative_session_evidence():
    for status in (429, 500, 502, 503):
        session = make_session()
        session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
        session.s.get.return_value = MagicMock(status_code=status, url=session.urlBase, text="Unavailable")
        reply = IPCServer(default_session=session).handle_request({
            "action": "validate_session_existing", "world": "s301-en", "player": "ExamplePlayer",
        })
        assert reply["status"] == "error"
        assert "session_valid" not in reply
    session = make_session()
    session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
    session.s.get.side_effect = OSError("synthetic timeout")
    reply = IPCServer(default_session=session).handle_request({
        "action": "validate_session_existing", "world": "s301-en", "player": "ExamplePlayer",
    })
    assert reply["status"] == "error"
    assert "session_valid" not in reply
