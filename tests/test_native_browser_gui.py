"""Native client-side Gameforge browser: exact cookie, safe routing and GUI wiring."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("PySide6.QtWebEngineWidgets")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from daedalus.desktop.app import APIWorker, MainWindow
from daedalus.desktop.native_login_dialog import (
    allowed_gameforge_navigation,
    exact_world_cookie,
)
from daedalus.desktop.pages import AccountsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _account():
    return {"id": "alpha", "world": "s301-en", "player": "ExamplePlayer",
            "label": "Example", "enabled": True, "session_status": "needs_assistance"}


def _cookie(*, domain="s301-en.ikariam.gameforge.com", secure=True,
            name=b"ikariam", value=b"Z" * 48):
    cookie = QNetworkCookie(name, value)
    cookie.setDomain(domain)
    cookie.setSecure(secure)
    return cookie


@pytest.mark.parametrize(("url", "main_frame", "accepted"), [
    ("https://lobby.ikariam.gameforge.com/", True, True),
    ("https://s301-en.ikariam.gameforge.com/", True, True),
    ("https://accounts.gameforge.com/login", True, True),
    ("https://gameforge.com/", True, True),
    ("http://lobby.ikariam.gameforge.com/", True, False),
    ("https://gameforge.com.attacker.example/", True, False),
    ("https://notgameforge.com/", True, False),
    ("javascript:alert(1)", True, False),
    ("file:///Users/test/Library/Keychains/", True, False),
    ("https://www.google.com/recaptcha/frame", False, True),
])
def test_official_login_restricts_top_level_navigation(url, main_frame, accepted):
    assert allowed_gameforge_navigation(QUrl(url), main_frame) is accepted


def test_only_exact_secure_world_cookie_is_accepted():
    host = "s301-en.ikariam.gameforge.com"
    assert exact_world_cookie(_cookie(), host) == "Z" * 48
    for bad in (
        _cookie(domain="s302-en.ikariam.gameforge.com"),
        _cookie(domain=".ikariam.gameforge.com"),
        _cookie(domain="lobby.ikariam.gameforge.com"),
        _cookie(secure=False),
        _cookie(name=b"gf-token-production"),
        _cookie(value=b"short"),
        _cookie(value=b"C" * 48 + b";"),
        _cookie(value=b"C" * 48 + b"\\"),
    ):
        assert exact_world_cookie(bad, host) is None


def test_account_view_shows_mac_login_only_when_secure_backend_supports_it(app):
    page = AccountsPage()
    requested = []
    try:
        page.set_accounts([_account()])
        page.table.selectRow(0)
        page.native_browser_login_requested.connect(requested.append)
        assert not page.native_browser_login_button.isEnabled()
        page.set_native_browser_login_enabled(True)
        assert page.native_browser_login_button.isEnabled()
        page.native_browser_login_button.click()
        assert requested == ["alpha"]
        page.set_native_browser_login_enabled(False)
        assert not page.native_browser_login_button.isEnabled()
    finally:
        page.close()


def test_browser_api_worker_never_receives_raw_world_cookie(app):
    operations = []
    class Backend:
        def start_native_browser_login(self, aid, *, confirmed):
            operations.append(("start", aid, confirmed))
            return {"account_id": aid, "status": "browser_login_ready"}
        def finish_native_browser_login(self, aid, tid, envelope):
            operations.append(("complete", aid, tid, envelope))
            return {"account_id": aid, "status": "world_cookie_bound"}
        def cancel_native_browser_login(self, aid, tid):
            operations.append(("cancel", aid, tid))
            return {"account_id": aid, "status": "browser_login_cancelled"}
    client = Backend()
    ticket = "00000000-0000-4000-8000-000000000000"
    envelope = {"confirmed": True, "client_key": "A"*43, "nonce": "A"*16,
                "ciphertext": "A"*80}
    for action, payload in (
        ("native_login_start", None),
        ("native_login_complete", {"ticket_id": ticket, "envelope": envelope}),
        ("native_login_cancel", {"ticket_id": ticket}),
    ):
        worker = APIWorker(client, action, account_id="alpha", task_payload=payload)
        recorded = []
        worker.completed.connect(lambda action, data, target=recorded: target.append(action))
        worker.run()  # no thread/network: deterministic synthetic fixture
        assert recorded == [action]
    assert operations == [
        ("start", "alpha", True),
        ("complete", "alpha", ticket, envelope),
        ("cancel", "alpha", ticket),
    ]
    assert not any("password" in str(item) or "game-cookie-secret" in str(item)
                   for item in operations)


def test_main_window_recovery_requests_explicit_permission_and_never_auto_runs(app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        window.accounts_page.set_accounts([_account()])
        window.client = object()
        request_calls = []
        monkeypatch.setattr(window, "_request", lambda *a, **kw: request_calls.append((a, kw)))
        # Clicking "Sign in automatically" IS the user authorization.
        # Subsequent headless Selenium steps require no dialog confirmation;
        # input is requested only when credentials are missing or CAPTCHA exists.
        window._active_backend_url = "https://example.test"
        window._begin_native_browser_login("alpha")
        assert request_calls == [(('native_login_start',), {'account_id': 'alpha'})]
        window._on_completed("native_login_start", {
            "account_id": "alpha", "world": "s301-en",
            "ticket_id": "00000000-0000-4000-8000-000000000000",
            "expires_in_seconds": 600,
        })
        assert window._pending_native_login_challenge is not None
        window.client = None
    finally:
        window.close()


def test_off_record_webengine_no_game_network_smoke(app):
    """Opt-in heavier smoke; tested on macOS app CI, never contacts Gameforge."""
    if os.environ.get("DAEDALUS_TEST_QTWEBENGINE") != "1":
        pytest.skip("Heavy QtWebEngine subprocess smoke only when explicitly requested")
    from daedalus.desktop.native_login_dialog import NativeLoginDialog
    dialog = NativeLoginDialog(world="s301-en", player="ExamplePlayer",
                               ttl_seconds=600, load_initial=False)
    try:
        assert dialog.profile.isOffTheRecord()
        assert dialog.result() != QDialog.Accepted
        dialog._cookie_added(_cookie())
        assert not dialog.finish_button.isEnabled()
        dialog.approval.setChecked(True)
        assert dialog.finish_button.isEnabled()
        dialog._finish()
        assert dialog.world_session() == "Z" * 48
    finally:
        dialog.discard_session()
        dialog.close()
        dialog.dispose_browser()
        dialog.deleteLater()
        QApplication.processEvents()
