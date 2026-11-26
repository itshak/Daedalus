"""Task control over an existing session with fake child processes only.

The suite explicitly forbids login restoration and real subprocess creation.
"""

from unittest.mock import MagicMock, patch

import pytest

from ikabot.helpers.ipc import IPCServer

_REQUEST_ID = "12345678-1234-4123-8123-123456789abc"
_ACCOUNT = {"world": "s301-en", "player": "ExampleOne"}


def session():
    value = MagicMock()
    value.logged = True
    value.mundo = "301"
    value.servidor = "en"
    value.login_servidor = "en"
    value.username = "ExampleOne"
    value.mail = "dummy@example.invalid"
    return value


class FakeEvent:
    def wait(self, timeout=None):
        return True


class FakeProcess:
    created = []

    def __init__(self, *, target, args, name):
        self.pid = 81000 + len(self.created)
        self.target = target
        self.args = args
        self.name = name
        self.active = False
        self.terminated = False
        self.created.append(self)

    def start(self):
        self.active = True

    def is_alive(self):
        return self.active

    def terminate(self):
        self.terminated = True
        self.active = False

    def join(self, timeout=None):
        pass

    def kill(self):
        self.terminated = True
        self.active = False


def task_func(session, minutes):
    pass


task_func.__module__ = "ikabot.function.alertAttacks"
task_func.prepare = None


@pytest.fixture
def prepared():
    FakeProcess.created = []
    engine = IPCServer(default_session=session())
    with (
        patch("ikabot.helpers.ipc.Session.from_saved", side_effect=AssertionError("login called")),
        patch("ikabot.helpers.ipc._resolve_task", return_value=("alertAttacks", task_func)),
        patch("ikabot.helpers.ipc.multiprocessing.Process", FakeProcess),
        patch("ikabot.helpers.ipc.multiprocessing.Event", FakeEvent),
        patch("ikabot.helpers.ipc.updateProcessList") as update_processes,
        patch("ikabot.helpers.botComm.telegramDataIsValid", return_value=True),
    ):
        yield engine, update_processes


def command(**changes):
    return {
        "action": "start_task_existing",
        **_ACCOUNT,
        "task": "alertAttacks",
        "config": {"minutes": 10},
        "request_id": _REQUEST_ID,
        **changes,
    }


def test_start_list_stop_managed_child(prepared):
    engine, update = prepared
    start = engine.handle_request(command())
    assert start["status"] == "ok", start
    assert start["task"] == "alertAttacks"
    assert "email" not in start
    assert len(FakeProcess.created) == 1
    update.assert_called_once()
    listed = engine.handle_request({"action": "list_tasks_existing", **_ACCOUNT})
    assert listed["tasks"][0]["pid"] == start["pid"]
    assert listed["tasks"][0]["status"] == "running"
    assert "config" not in str(listed)
    stopped = engine.handle_request({
        "action": "stop_task_existing", **_ACCOUNT, "task_id": start["task_id"]
    })
    assert stopped["status"] == "ok"
    assert stopped["task_status"] == "stopped"
    assert FakeProcess.created[0].terminated
    assert engine.handle_request({"action": "list_tasks_existing", **_ACCOUNT})["tasks"][0][
        "status"
    ] == "stopped"


def test_repeated_idempotency_key_does_not_duplicate_task(prepared):
    engine, _ = prepared
    first = engine.handle_request(command())
    second = engine.handle_request(command())
    assert first == second
    assert len(FakeProcess.created) == 1
    different = engine.handle_request(command(config={"minutes": 20}))
    assert different["status"] == "error"
    assert len(FakeProcess.created) == 1


@pytest.mark.parametrize("change", [
    {"world": "s302-en"},
    {"player": "OtherPlayer"},
    {"world": ""},
    {"request_id": ""},
    {"request_id": "not-a-uuid"},
    {"config": ["bad"]},
    {"config": {"session": "forged"}},
    {"task": "nonexistentModule"},
    {"task": "../alertAttacks"},
])
def test_invalid_identity_config_or_task_does_not_spawn_child(prepared, change):
    engine, _ = prepared
    result = engine.handle_request(command(**change))
    assert result["status"] == "error"
    assert len(FakeProcess.created) == 0


def test_cannot_stop_or_list_another_accounts_tasks(prepared):
    engine, _ = prepared
    start = engine.handle_request(command())
    bad_stop = engine.handle_request({
        "action": "stop_task_existing", "world": "s302-en", "player": "OtherPlayer",
        "task_id": start["task_id"],
    })
    assert bad_stop["status"] == "error"
    assert FakeProcess.created[0].active
    other = engine.handle_request({
        "action": "list_tasks_existing", "world": "s302-en", "player": "OtherPlayer"
    })
    assert other["status"] == "ok"
    assert other["tasks"] == []
    arbitrary = engine.handle_request({
        "action": "stop_task_existing", **_ACCOUNT, "task_id": "0" * 24
    })
    assert arbitrary["status"] == "error"
    assert FakeProcess.created[0].active


def test_unrelated_upstream_restore_action_is_not_used(prepared):
    engine, _ = prepared
    start = engine.handle_request(command())
    assert start["status"] == "ok"
    assert "email" not in start


def test_process_list_failure_terminates_new_child_instead_of_orphaning(prepared):
    engine, update = prepared
    update.side_effect = RuntimeError("synthetic session write failure")
    response = engine.handle_request(command())
    assert response["status"] == "error"
    assert len(FakeProcess.created) == 1
    assert FakeProcess.created[0].terminated is True
    assert engine._daedalus_tasks == {}


def test_builtin_name_must_resolve_to_builtin_module(prepared):
    engine, _ = prepared
    with patch("ikabot.helpers.ipc._resolve_task") as resolve:
        def custom(session, minutes):
            pass
        custom.__module__ = "external.custom_plugin"
        resolve.return_value = ("alertAttacks", custom)
        response = engine.handle_request(command())
    assert response["status"] == "error"
    assert len(FakeProcess.created) == 0


def test_per_account_parallel_task_limit(prepared):
    from uuid import uuid4

    engine, _ = prepared
    for _ in range(16):
        response = engine.handle_request(command(request_id=str(uuid4())))
        assert response["status"] == "ok", response
    rejected = engine.handle_request(command(request_id=str(uuid4())))
    assert rejected["status"] == "error"
    assert len(FakeProcess.created) == 16


def test_warehouse_child_gate_released_only_after_registration(prepared):
    engine, update = prepared

    class Gate(FakeEvent):
        def __init__(self):
            self.released = False

        def set(self):
            self.released = True

    def fill(session, destination_city):
        pass

    fill.__module__ = "ikabot.function.fillCityWarehouse"
    fill.prepare = None

    def check_registration(*args, **kwargs):
        assert not FakeProcess.created[-1].args[4].released

    update.side_effect = check_registration
    with (patch("ikabot.helpers.ipc._resolve_task", return_value=("fillCityWarehouse", fill)),
          patch("ikabot.helpers.ipc.multiprocessing.Event", Gate)):
        reply = engine.handle_request(command(task="fillCityWarehouse", config={"destination_city": 42}))
    assert reply["status"] == "ok"
    assert FakeProcess.created[-1].args[4].released


def test_warehouse_registration_failure_never_releases_gate(prepared):
    engine, update = prepared

    class Gate(FakeEvent):
        def __init__(self):
            self.released = False

        def set(self):
            self.released = True

    def fill(session, destination_city):
        pass

    fill.__module__ = "ikabot.function.fillCityWarehouse"
    fill.prepare = None
    update.side_effect = RuntimeError("synthetic registration failure")
    with (patch("ikabot.helpers.ipc._resolve_task", return_value=("fillCityWarehouse", fill)),
          patch("ikabot.helpers.ipc.multiprocessing.Event", Gate)):
        reply = engine.handle_request(command(task="fillCityWarehouse", config={"destination_city": 42}))
    assert reply["status"] == "error"
    assert not FakeProcess.created[-1].args[4].released
    assert FakeProcess.created[-1].terminated
