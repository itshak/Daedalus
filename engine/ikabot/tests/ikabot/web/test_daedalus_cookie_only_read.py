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
