"""Offline native GUI wiring for protected host-only recovery."""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from daedalus.desktop.app import APIWorker, MainWindow
from daedalus.desktop.pages import AccountsPage


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _dispose(widget, app):
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _guide(ticket=None):
    return {
        "enabled": True, "account_id": "alpha",
        "mode": "host_local_only",
        "requires_trusted_host_session": True,
        "allow_http_cookie_transfer": False,
        "dedicated_rebind_supported": True,
        "session_status": "assisted_login",
        "ticket": ticket,
    }


def _ticket():
    return {
        "ticket_id": str(uuid.uuid4()), "reason": "session_expired",
        "state": "operator_ready",
    }


def test_native_host_guide_rebind_requires_explicit_ticket_and_confirmation(qt_app, monkeypatch):
    page = AccountsPage()
    guide = _guide(_ticket())
    info = []
    approvals = []
    rebinds = []
    guide_requests = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: info.append(args))
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: (approvals.append(args), QMessageBox.Yes)[1],
    )
    try:
        page.set_accounts([
            {"id": "alpha", "world": "s301-en", "player": "ExamplePlayer",
             "enabled": True},
            {"id": "beta", "world": "s302-en", "player": "OtherPlayer",
             "enabled": True},
        ])
        page.table.selectRow(0)
        assert not page.rebind_button.isEnabled()
        page.recovery_guide_requested.connect(guide_requests.append)
        page.rebind_requested.connect(lambda aid, tid: rebinds.append((aid, tid)))
        page.recovery_guide_button.click()
        assert guide_requests == ["alpha"]
        page.set_recovery_guide(guide)
        assert page.rebind_button.isEnabled()
        assert len(info) == 1
        text = str(info[0][-1])
        assert "AUTHORITATIVE WORKER HOST" in text
        assert "stage-playwright-login" in text
        assert "confirm" in text.lower()
        assert "password" in text.lower()
        page.rebind_button.click()
        assert len(approvals) == 1
        assert rebinds == [("alpha", guide["ticket"]["ticket_id"])]
        page.table.selectRow(1)
        assert not page.rebind_button.isEnabled()
        page.set_recovery_guide(guide)  # Stale account response ignored.
        assert rebinds == [("alpha", guide["ticket"]["ticket_id"])]
        page.table.selectRow(0)
        page.set_accounts([{
            "id": "alpha", "world": "s301-en", "player": "ExamplePlayer",
            "enabled": True,
        }])
        assert not page.rebind_button.isEnabled()
    finally:
        _dispose(page, qt_app)


def test_native_rebind_refuses_unverified_or_wrong_ticket(qt_app, monkeypatch):
    page = AccountsPage()
    approvals = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: (approvals.append(True), QMessageBox.Yes)[1],
    )
    try:
        page.set_accounts([{"id": "alpha", "enabled": True, "world": "s301-en"}])
        page.table.selectRow(0)
        guide = _guide(_ticket())
        guide["ticket"]["state"] = "waiting_operator"
        page.set_recovery_guide(guide)
        assert not page.rebind_button.isEnabled()
        page._request_worker_rebind()
        assert approvals == []
        guide["ticket"]["state"] = "operator_ready"
        guide["dedicated_rebind_supported"] = False
        page.set_recovery_guide(guide)
        assert not page.rebind_button.isEnabled()
        page._request_worker_rebind()
        assert approvals == []
    finally:
        _dispose(page, qt_app)


def test_native_worker_sends_only_nonsecret_recovery_identifiers(qt_app):
    class Backend:
        def __init__(self):
            self.calls = []
        def recovery_guide(self, aid):
            self.calls.append(("guide", aid))
            return _guide()
        def rebind_dedicated_worker(self, aid, tid, *, confirmed):
            self.calls.append(("rebind", aid, tid, confirmed))
            return {"account_id": aid, "status": "worker_recovered_verified"}

    client = Backend()
    ticket_id = str(uuid.uuid4())
    receipt = []
    worker = APIWorker(client, "recovery_guide", account_id="alpha")
    worker.completed.connect(lambda a, payload: receipt.append((a, payload)))
    worker.run()
    assert receipt[0][0] == "recovery_guide"
    worker = APIWorker(
        client, "worker_rebind", account_id="alpha",
        task_payload={"ticket_id": ticket_id},
    )
    worker.completed.connect(lambda a, payload: receipt.append((a, payload)))
    worker.run()
    assert receipt[1][1] == {
        "account_id": "alpha", "status": "worker_recovered_verified",
    }
    assert client.calls == [
        ("guide", "alpha"),
        ("rebind", "alpha", ticket_id, True),
    ]


def test_fluent_main_window_connects_live_auth_controls_without_backend(qt_app):
    window = MainWindow()
    try:
        assert window.client is None
        assert not window.accounts_page.rebind_button.isEnabled()
        assert not window.accounts_page.recovery_guide_button.isEnabled()
    finally:
        _dispose(window, qt_app)


def test_native_prepare_requires_safe_guide_and_explicit_yes(qt_app, monkeypatch):
    page = AccountsPage()
    ticket = []
    answers = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: (
            answers.append(args), QMessageBox.Yes
        )[1],
    )
    try:
        page.set_accounts([
            {"id": "alpha", "world": "s301-en", "player": "ExamplePlayer",
             "enabled": True},
        ])
        page.table.selectRow(0)
        page.recovery_prepare_requested.connect(ticket.append)
        assert not page.recovery_prepare_button.isEnabled()
        page._prepare_worker_recovery()
        assert answers == []
        available = _guide()
        available["session_status"] = "authenticated"
        page.set_recovery_guide(available)
        assert page.recovery_prepare_button.isEnabled()
        page.recovery_prepare_button.click()
        assert ticket == ["alpha"]
        assert len(answers) == 1
        available["ticket"] = _ticket()
        page.set_recovery_guide(available)
        assert not page.recovery_prepare_button.isEnabled()
        page._prepare_worker_recovery()
        assert ticket == ["alpha"]
        assert len(answers) == 1
    finally:
        _dispose(page, qt_app)



def test_recovery_status_refresh_waits_for_finished_worker(qt_app, monkeypatch):
    window = MainWindow()
    requests = []
    notices = []
    monkeypatch.setattr(window, "_request", lambda action, **kw: requests.append((action, kw)))
    monkeypatch.setattr(window, "_notice", lambda *args: notices.append(args))
    try:
        window.client = object()  # Synthetic connected sentinel; no HTTP client.
        window._show_accounts([
            {"id": "alpha", "world": "s301-en", "player": "ExamplePlayer",
             "enabled": True},
        ])
        window.accounts_page.table.selectRow(0)
        receipt = {
            "account_id": "alpha", "status": "manual_recovery_prepared",
            "ticket": {
                "ticket_id": str(uuid.uuid4()), "reason": "manual_challenge",
                "state": "waiting_operator",
            },
        }
        window._on_completed("recovery_prepare", receipt)
        assert requests == []  # No QTimer race while the old APIWorker exists.
        assert window._recovery_followup == ("recovery_guide", "alpha")
        window._on_worker_finished()
        assert requests == [("recovery_guide", {"account_id": "alpha"})]
        assert window._recovery_followup is None
        window._on_completed("auth_assistance_approve", {
            "enabled": True, "account_id": "alpha", "ticket": {
                **receipt["ticket"], "state": "operator_ready",
            },
        })
        assert requests == [("recovery_guide", {"account_id": "alpha"})]
        window._on_worker_finished()
        assert requests[-1] == ("recovery_guide", {"account_id": "alpha"})
        window._on_completed("worker_rebind", {
            "account_id": "alpha", "status": "worker_recovered_verified",
        })
        window._on_worker_finished()
        assert requests[-1] == ("accounts", {"account_id": None})
    finally:
        window.client = None
        _dispose(window, qt_app)


def test_native_mac_browser_cookie_policy_is_present_in_standard_macos_ci():
    """Run on the existing macOS GUI workflow without workflow-file edits."""
    from PySide6.QtCore import QUrl
    from PySide6.QtNetwork import QNetworkCookie

    from daedalus.desktop.native_login_dialog import (
        allowed_gameforge_navigation,
        exact_world_cookie,
    )

    assert allowed_gameforge_navigation(QUrl("https://lobby.ikariam.gameforge.com"), True)
    assert not allowed_gameforge_navigation(QUrl("https://gameforge.com.attacker.example"), True)
    correct = QNetworkCookie(b"ikariam", b"S" * 48)
    correct.setDomain("s301-en.ikariam.gameforge.com")
    correct.setSecure(True)
    assert exact_world_cookie(correct, "s301-en.ikariam.gameforge.com") == "S" * 48
    assert exact_world_cookie(correct, "s302-en.ikariam.gameforge.com") is None
