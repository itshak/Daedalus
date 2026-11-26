"""Cookie-only IkaBot reads never spawn a new login or kill the IPC worker.

This test exercises the real Session.get path which was crashing the live
browser-cookie child on its first cities/warehouse read. No external traffic.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ikabot.web.session import Session


class FakeHTTP:
    def __init__(self, *, status=200, text="<html>city</html>", host="s301-en.ikariam.gameforge.com"):
        self.calls = []
        self.status = status
        self.text = text
        self.host = host

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return SimpleNamespace(
            url=f"https://{self.host}/index.php?view=city",
            status_code=self.status, text=self.text,
            content=self.text.encode(), history=[],
        )


def session_with_existing_cookie(http):
    session = Session.__new__(Session)
    session.urlBase = "https://s301-en.ikariam.gameforge.com/index.php?"
    session.host = "s301-en.ikariam.gameforge.com"
    session.s = http
    session._daedalus_cookies_only = True
    return session


def test_cookie_only_city_read_skips_legacy_relogin_and_keeps_worker_alive():
    http = FakeHTTP()
    session = session_with_existing_cookie(http)
    with patch.object(Session, "_Session__checkCookie",
                      side_effect=AssertionError("Never try a Gameforge login")):
        result = session.get("view=city&cityId=123")
    assert result == "<html>city</html>"
    assert http.calls == [(
        "https://s301-en.ikariam.gameforge.com/index.php?view=city&cityId=123",
        {"params": {}, "allow_redirects": False, "verify": True, "timeout": 12},
    )]


def test_cookie_only_warehouse_noindex_request_remains_same_world():
    http = FakeHTTP()
    session = session_with_existing_cookie(http)
    assert session.get("view=warehouse&cityId=123&position=10", noIndex=True)
    assert http.calls[0][0] == (
        "https://s301-en.ikariam.gameforge.com/?view=warehouse&cityId=123&position=10"
    )
    assert http.calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize("status,body,host", [
    (302, "<html>redirect</html>", "s301-en.ikariam.gameforge.com"),
    (200, "index.php?logout", "s301-en.ikariam.gameforge.com"),
    (200, "<html>not our world</html>", "lobby.ikariam.gameforge.com"),
])
def test_cookie_only_bad_or_rotated_page_fails_closed_not_sys_exit(status, body, host):
    http = FakeHTTP(status=status, text=body, host=host)
    session = session_with_existing_cookie(http)
    with pytest.raises(RuntimeError, match="no longer available"):
        session.get("view=city&cityId=123")


def test_cookie_only_request_rejects_cross_origin_override():
    http = FakeHTTP()
    session = session_with_existing_cookie(http)
    with pytest.raises(ValueError, match="Unsupported"):
        session.get("https://other-site.example/?view=city")
    assert http.calls == []


def test_reviewed_cookie_transport_attests_identity_and_posts_once():
    from ikabot.config import actionRequest
    from unittest.mock import Mock

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> currentCityId: 123, actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    http.post = Mock(return_value=SimpleNamespace(
        url=session.urlBase, status_code=200, text="[]", content=b"[]", history=[]))
    params = {"action": "transportOperations", "function": "loadTransportersWithFreight",
              "actionRequest": actionRequest, "cargo_resource": 50, "currentCityId": "123"}
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")):
        assert session.post(params=params, retry_on_failure=False) == "[]"
    http.post.assert_called_once_with(session.urlBase, data={}, params=dict(params, actionRequest="abcdefgh1234"),
                                     allow_redirects=False, verify=True, timeout=12)
    assert params["actionRequest"] == actionRequest


def test_reviewed_cookie_transport_never_retries_timeout_or_wrong_identity():
    import requests
    from ikabot.config import actionRequest
    from unittest.mock import Mock

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    http.post = Mock(side_effect=requests.Timeout("private details"))
    params = {"action": "header", "function": "changeCurrentCity", "actionRequest": actionRequest}
    with pytest.raises(RuntimeError, match="uncertain"):
        session._daedalus_reviewed_transport_post(params)
    assert http.post.call_count == 1
    session.username = "DifferentPlayer"
    with pytest.raises(RuntimeError, match="verification failed"):
        session._daedalus_reviewed_transport_post(params)
    assert http.post.call_count == 1


def test_reviewed_cookie_transport_refuses_changed_source_before_post():
    from ikabot.config import actionRequest
    from unittest.mock import Mock
    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> currentCityId: 456, actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    http.post = Mock()
    with pytest.raises(RuntimeError, match="source context changed"):
        session._daedalus_reviewed_transport_post({
            "action": "transportOperations", "function": "loadTransportersWithFreight",
            "actionRequest": actionRequest, "currentCityId": "123"})
    http.post.assert_not_called()


def test_cookie_transport_standard_post_refuses_implicit_retry():
    from ikabot.config import actionRequest
    from unittest.mock import Mock

    http = FakeHTTP()
    session = session_with_existing_cookie(http)
    http.post = Mock()
    with pytest.raises(ValueError, match="one bounded standard POST"):
        session.post(params={"action": "transportOperations",
                             "function": "loadTransportersWithFreight",
                             "actionRequest": actionRequest})
    http.post.assert_not_called()


def test_upstream_advisor_ajax_post_is_read_only_and_never_reauthenticates():
    from unittest.mock import Mock
    from ikabot.config import actionRequest
    from ikabot.helpers.fleetAdvisor import advisor_data

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    http.post = Mock(return_value=SimpleNamespace(
        url=session.urlBase, status_code=200, text="[]", content=b"[]", history=[]))
    url = ("view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city"
           f"&currentCityId=123&actionRequest={actionRequest}&ajax=1")
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")):
        assert advisor_data(session, 123, ajax=True) == []
        http.post.assert_called_once_with(
            session.urlBase + url.replace(actionRequest, "abcdefgh1234"),
            data={}, params={}, verify=True, timeout=12, allow_redirects=False)
        with pytest.raises(ValueError, match="Unsupported cookie-only advisor request"):
            session.post(url + "&action=transportOperations")
        with pytest.raises(ValueError, match="Unsupported cookie-only advisor options"):
            session.post(url, params={"action": "transportOperations"})
    assert http.post.call_count == 1


@pytest.mark.parametrize("troops,view", [(True, "barracks"), (False, "shipyard")])
def test_actual_upstream_training_wait_through_cookie_session(troops, view):
    import json
    from unittest.mock import Mock
    from ikabot.function import trainArmy
    from ikabot.config import actionRequest

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    reply = json.dumps([["updateGlobalData", {"time": 1000}],
                        ["changeView", [None, "'buildProgress', 1120,"]]])
    http.post = Mock(return_value=SimpleNamespace(
        url=session.urlBase, status_code=200, text=reply, content=reply.encode(), history=[]))
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")), \
         patch.object(trainArmy, "wait") as wait:
        trainArmy.waitForTraining(session, {"id": "123", "pos": "4"}, troops)
    wait.assert_called_once_with(125)
    expected = {"view": view, "cityId": "123", "position": "4", "backgroundView": "city",
                "currentCityId": "123", "actionRequest": "abcdefgh1234", "ajax": "1"}
    http.post.assert_called_once_with(session.urlBase, data={}, params=expected,
                                     verify=True, timeout=12, allow_redirects=False)
    with pytest.raises(ValueError, match="Unsupported cookie-only queue view"):
        session.post(params={**expected, "action": "CityScreen", "actionRequest": actionRequest})
    assert http.post.call_count == 1


def test_actual_upstream_workshop_wait_through_cookie_session():
    import json
    from unittest.mock import Mock
    from ikabot.function import UpgradeUnits

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    session.setStatus = Mock()
    busy = json.dumps([["updateTemplateData", {"inProgress": {"endTime": 1120}, "currentdate": 1000}]])
    ready = json.dumps([["updateTemplateData", {"currentdate": 1120}]])
    http.post = Mock(side_effect=[SimpleNamespace(url=session.urlBase, status_code=200,
        text=x, content=x.encode(), history=[]) for x in (busy, ready)])
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")), \
         patch.object(UpgradeUnits.time, "sleep") as wait:
        UpgradeUnits.wait_for_upgrade_completion(session, "123", "4", "tabUnits")
    wait.assert_called_once_with(120)
    assert http.post.call_count == 2
    assert all(c.kwargs["params"]["view"] == "workshop" for c in http.post.call_args_list)


def test_actual_upstream_miracle_wait_through_cookie_session():
    import json
    from unittest.mock import Mock
    from ikabot.function import activateMiracle

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    session.setStatus = Mock()
    cooldown = json.dumps([[], [], ["updateTemplateData", {"timer": {
        "countdown": {"enddate": 1120, "currentdate": 1000}}}]])
    ready = json.dumps([[], [], ["updateTemplateData", {"js_WonderViewButton": {"buttonState": "enabled"}}]])
    http.post = Mock(side_effect=[SimpleNamespace(url=session.urlBase, status_code=200,
        text=x, content=x.encode(), history=[]) for x in (cooldown, ready)])
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")), \
         patch.object(activateMiracle, "wait") as wait, \
         patch.object(activateMiracle, "sendToBotDebug"):
        activateMiracle.wait_for_miracle(session, {"ciudad": {"id": "123", "pos": "4"}, "wonderName": "Example"})
    wait.assert_called_once_with(125)
    assert http.post.call_count == 2
    assert all(c.kwargs["params"]["view"] == "temple" for c in http.post.call_args_list)


@pytest.mark.parametrize("view,extra,no_index", [
    ("buildingGround", {"position": 4}, True),
    ("branchOffice", {"position": 4, "activeTab": "bargain", "type": 444,
                      "searchResource": "resource", "range": 3, "templateView": "branchOffice",
                      "currentTab": "bargain"}, False),
    ("branchOfficeOwnOffers", {"position": 4, "activeTab": "tab_branchOfficeOwnOffers",
                               "templateView": "branchOfficeOwnOffers",
                               "currentTab": "tab_branchOfficeOwnOffers"}, True),
])
def test_audited_upstream_inventory_forms_preserve_endpoint_and_parameters(view, extra, no_index):
    from unittest.mock import Mock
    from ikabot.config import actionRequest

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    base = session.urlBase.replace("index.php", "") if no_index else session.urlBase
    http.post = Mock(return_value=SimpleNamespace(
        url=base, status_code=200, text="[]", content=b"[]", history=[]))
    params = {"view": view, "cityId": "123", "currentCityId": "123",
              "backgroundView": "city", "actionRequest": actionRequest, "ajax": "1", **extra}
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("legacy login")):
        assert session.post(params=params, noIndex=no_index) == "[]"
        with pytest.raises(ValueError, match="Unsupported"):
            session.post(params={**params, "action": "unexpected"}, noIndex=no_index)
        with pytest.raises(ValueError, match="Unsupported"):
            session.post(params={**params, "currentCityId": "456"}, noIndex=no_index)
    http.post.assert_called_once_with(base, data={}, params=dict(params, actionRequest="abcdefgh1234"),
                                     verify=True, timeout=12, allow_redirects=False)


@pytest.mark.parametrize("form,no_index", [
    ("view=saveCityBuildingsPositions&cityId=123&backgroundView=city&currentCityId=123", True),
    ("view=researchAdvisor&oldView=updateGlobalData&cityId=123&backgroundView=city&currentCityId=123&templateView=researchAdvisor", False),
    ("view=academy&cityId=123&position=4&backgroundView=city&currentCityId=123", False),
    ("view=temple&cityId=123&position=4&backgroundView=city&currentCityId=123", False),
    ("view=branchOffice&cityId=123&position=4&currentCityId=123&backgroundView=city", False),
    ("view=finances&backgroundView=city&currentCityId=123&templateView=finances", False),
    ("view=tradegood&type=1&islandId=5&cityId=123&backgroundView=island&currentIslandId=5", False),
    ("view=resource&type=resource&islandId=5&backgroundView=island&currentIslandId=5", False),
    ("view=takeOffer&destinationCityId=456&oldView=branchOffice&activeTab=bargain&cityId=123&position=4&type=444&resource=resource&backgroundView=city&currentCityId=123&templateView=branchOffice", False),
])
def test_audited_upstream_url_reads_retain_original_form(form, no_index):
    from unittest.mock import Mock
    from ikabot.config import actionRequest

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    base = session.urlBase.replace("index.php", "") if no_index else session.urlBase
    http.post = Mock(return_value=SimpleNamespace(
        url=base, status_code=200, text="[]", content=b"[]", history=[]))
    url = form + f"&actionRequest={actionRequest}&ajax=1"
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("legacy login")):
        assert session.post(url, noIndex=no_index) == "[]"
        with pytest.raises(ValueError, match="Unsupported"):
            session.post(url + "&action=unexpected", noIndex=no_index)
        with pytest.raises(ValueError, match="Unsupported"):
            session.post(url + "&ajax=1", noIndex=no_index)
    http.post.assert_called_once_with(base + url.replace(actionRequest, "abcdefgh1234"),
                                     data={}, params={}, verify=True, timeout=12, allow_redirects=False)


def test_shared_deployment_inventory_uses_original_read_form():
    from unittest.mock import Mock
    from ikabot.config import actionRequest
    from ikabot.function import stationArmy

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    http.post = Mock(return_value=SimpleNamespace(
        url=session.urlBase, status_code=200, text="[]", content=b"[]", history=[]))
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("legacy login")):
        assert stationArmy._deployment_view(session, True, "456", "123") == "[]"
    http.post.assert_called_once_with(
        session.urlBase, data={}, params={"view": "deployment", "deploymentType": "army",
        "destinationCityId": "456", "backgroundView": "city", "currentCityId": "123",
        "actionRequest": "abcdefgh1234", "ajax": 1},
        verify=True, timeout=12, allow_redirects=False)
    with pytest.raises(ValueError):
        session.post(params={"view": "deployment", "deploymentType": "army",
                             "destinationCityId": "456", "backgroundView": "city",
                             "currentCityId": "123", "actionRequest": actionRequest, "ajax": 1,
                             "function": "unexpected"})
    assert http.post.call_count == 1


def test_actual_upstream_military_inventory_uses_protected_read_transport():
    import json
    from unittest.mock import Mock
    from ikabot.config import actionRequest
    from ikabot.function.viewArmy import getCityMilitaryData

    http = FakeHTTP(text='<span id="avatarName">ExamplePlayer</span> actionRequest: "abcdefgh1234"')
    session = session_with_existing_cookie(http)
    session.username = "ExamplePlayer"
    reply = json.dumps([["updateGlobalData", {}], ["changeView", [None, "inventory"]]])
    http.post = Mock(return_value=SimpleNamespace(
        url=session.urlBase, status_code=200, text=reply, content=reply.encode(), history=[]))
    with patch.object(Session, "_Session__checkCookie", side_effect=AssertionError("relogin")):
        assert getCityMilitaryData(session, "123") == "inventory"
        expected = {"view": "cityMilitary", "activeTab": "tabUnits", "cityId": "123",
                    "currentTab": "tabUnits", "currentCityId": "123", "templateView": "cityMilitary",
                    "actionRequest": "abcdefgh1234", "ajax": "1"}
        http.post.assert_called_once_with(session.urlBase, data={}, params=expected,
                                         verify=True, timeout=12, allow_redirects=False)
        with pytest.raises(ValueError, match="Unsupported cookie-only military inventory view"):
            session.post(params={**expected, "actionRequest": actionRequest, "action": "CityScreen"})
        with pytest.raises(ValueError, match="Unsupported cookie-only military inventory view"):
            session.post(params={**expected, "actionRequest": actionRequest, "currentCityId": "456"})
    assert http.post.call_count == 1
