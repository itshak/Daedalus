"""Native report and preference parity checks using synthetic data only."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("qfluentwidgets")

from PySide6.QtWidgets import QApplication

from daedalus.desktop.app import MainWindow
from daedalus.desktop.pages import AccountsPage, WarehousesPage


@pytest.fixture(scope="module")
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


def _dispose(widget, app: QApplication) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()



def test_native_report_account_selection_preserves_choices_without_task_dispatch(qt_app):
    from PySide6.QtCore import Qt
    page = AccountsPage()
    accounts = [
        {"id": "alpha", "world": "s1-en", "player": "A", "enabled": True},
        {"id": "beta", "world": "s2-en", "player": "B", "enabled": True},
    ]
    selected = []
    writes = []
    page.report_selection_changed.connect(selected.append)
    page.account_change_requested.connect(lambda *args: writes.append(args))
    try:
        page.set_accounts(accounts)
        assert page.selected_report_account_ids() == ["alpha", "beta"]
        page.table.item(1, 6).setCheckState(Qt.Unchecked)
        assert page.selected_report_account_ids() == ["alpha"]
        assert page.report_exclusions() == {"beta"}
        page.set_accounts(list(reversed(accounts)))
        assert page.selected_report_account_ids() == ["alpha"]
        page.select_all_reports.setChecked(True)
        assert page.selected_report_account_ids() == ["beta", "alpha"]
        page.set_report_exclusions({"alpha"})
        assert page.selected_report_account_ids() == ["beta"]
        assert selected[-1] == ["beta"]
        assert writes == []
    finally:
        _dispose(page, qt_app)


def test_native_multi_account_warehouse_export_explicit_partial_failures(qt_app):
    from PySide6.QtGui import QGuiApplication
    page = WarehousesPage()
    accounts = [
        {"id": "alpha", "label": "North", "world": "s1-en", "player": "A"},
        {"id": "beta", "label": "South", "world": "s2-en", "player": "B"},
    ]
    try:
        page.set_accounts(accounts)
        page.set_selected_accounts(["alpha"])
        calls = []
        page.load_selected_requested.connect(calls.append)
        page._load_selected()
        assert calls == [["alpha"]]
        page.set_batch_snapshots([
            {"account_id": "alpha", "cities": [
                {"city_name": "Athens", "island": "12:34",
                 "island_resource": "wine", "resources": {
                    "unsecured": {"wood": 220000, "wine": 0}
                }}
            ]},
            {"account_id": "beta", "error": True},
        ])
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "Athens"
        assert page.table.item(0, 3).text() == "220000"
        assert page.table.item(0, 5).text() == "—"
        assert page.table.item(0, 11).text() == "North"
        assert "South" in page.status_label.text()
        assert "unavailable" in page.status_label.text()
        page._copy_islands()
        clipboard = QGuiApplication.clipboard().text()
        assert clipboard.startswith("===== 12:34 (Вино) =====\n\nAthens (—)\n============\n")
        assert "Лес:\t220,000" in clipboard
        assert "Вино:\t0" in clipboard
        assert "World s1-en" not in clipboard
        assert "North" not in clipboard
        assert "South" not in clipboard
        page.clear_reports()
        assert not page.copy_button.isEnabled()
        assert page.table.rowCount() == 0
    finally:
        _dispose(page, qt_app)


def test_batch_worker_uses_only_readonly_existing_session_snapshot_calls(qt_app):
    from daedalus.client import APIConnectionError
    from daedalus.desktop.app import APIWorker

    class Backend:
        def __init__(self):
            self.calls = []
        def warehouses(self, aid):
            self.calls.append(aid)
            if aid == "beta":
                raise APIConnectionError("Sanitized backend failure")
            return [{"city_name": "Athens", "resources": {}}]

    client = Backend()
    worker = APIWorker(client, "warehouses_batch", task_payload={"account_ids": ["alpha", "beta"]})
    responses, errors = [], []
    worker.completed.connect(lambda action, payload: responses.append((action, payload)))
    worker.failed.connect(lambda action, detail: errors.append((action, detail)))
    worker.run()
    assert errors == []
    assert client.calls == ["alpha", "beta"]
    assert responses[0][0] == "warehouses_batch"
    assert responses[0][1][0]["cities"][0]["city_name"] == "Athens"
    assert responses[0][1][1] == {"account_id": "beta", "error": True}
    bad = APIWorker(client, "warehouses_batch", task_payload={"account_ids": ["alpha"] * 33})
    bad.failed.connect(lambda action, detail: errors.append((action, detail)))
    bad.run()
    assert client.calls == ["alpha", "beta"]
    assert "32" in errors[0][1]


def test_native_appearance_preferences_and_scoped_selection(qt_app, monkeypatch):
    from PySide6.QtCore import Qt

    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    persisted = []
    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(module, "save_gui_preferences", lambda prefs: persisted.append(
        (prefs.theme, prefs.only_220k, prefs.group_by_island, dict(prefs.excluded_by_backend))
    ))
    # Avoid depending on the host OS theme in this regression.
    monkeypatch.setattr(module, "setTheme", lambda *_: None)
    window = MainWindow()
    try:
        window.appearance_page.theme_combo.setCurrentIndex(2)
        window.appearance_page.only_220k.setChecked(True)
        window.appearance_page.group_island.setChecked(True)
        assert window._gui_preferences.theme == "dark"
        assert window.warehouses_page.only_220k.isChecked()
        assert window.warehouses_page.group_island.isChecked()
        window._active_backend_url = "https://one.example"
        window._show_accounts([
            {"id": "alpha", "world": "s1-en", "player": "A", "enabled": True},
            {"id": "beta", "world": "s2-en", "player": "B", "enabled": True},
        ])
        window.accounts_page.table.item(1, 6).setCheckState(Qt.Unchecked)
        assert window._gui_preferences.excluded_for("https://one.example") == {"beta"}
        assert window._gui_preferences.excluded_for("https://two.example") == set()
        assert persisted
    finally:
        _dispose(window, qt_app)


def test_account_refresh_rebinds_report_selection_to_new_backend_accounts(qt_app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(module, "save_gui_preferences", lambda *_: None)
    window = MainWindow()
    try:
        window._show_accounts([
            {"id": "alpha", "world": "s1-en", "player": "A", "enabled": True},
        ])
        assert window.warehouses_page._included_ids == ["alpha"]
        window._show_accounts([
            {"id": "beta", "world": "s2-en", "player": "B", "enabled": True},
        ])
        assert window.warehouses_page._included_ids == ["beta"]
        assert "alpha" not in window.warehouses_page._accounts
    finally:
        _dispose(window, qt_app)



def test_dedicated_wine_and_construction_workflows_filter_registered_tasks(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from daedalus.desktop.task_page import TasksPage

    all_operations = [
        {"name": "alertLowWine", "kind": "background_task", "config_fields": [
            {"name": "threshold", "type": "integer", "required": True}
        ]},
        {"name": "constructionList", "kind": "background_task", "config_fields": []},
        {"name": "constructBuilding", "kind": "interactive_menu"},
        {"name": "alertAttacks", "kind": "background_task"},
    ]
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Yes)
    for kind, expected in (("wine", "alertLowWine"), ("construction", "constructionList")):
        seen = []
        page = TasksPage(workflow=kind)
        try:
            page.launch_requested.connect(lambda *args, captured=seen: captured.append(args))
            page.set_accounts([{
                "id": "alpha", "player": "Example", "world": "s1-en", "enabled": True,
            }])
            page.set_capabilities(all_operations, enabled=False)
            assert page._task_names == [expected]
            assert not page.start_button.isEnabled()
            page._start()
            assert seen == []
            page.set_capabilities(all_operations, enabled=True)
            assert page._task_names == [expected]
            assert not page.start_button.isEnabled()
            page.set_preflight({"account_id": "alpha", "task": expected,
                                "ready": True, "reason": "none"})
            assert page.start_button.isEnabled() is (kind == "wine")
            if kind == "wine":
                page._form_inputs["threshold"].setText("1000")
                assert page._form_config() == {"threshold": 1000}
            page.confirm_box.setChecked(True)
            page._start()
            if kind == "wine":
                assert seen[-1][0:2] == ("alpha", expected)
                assert seen[-1][2] == {"threshold": 1000}
            else:
                # No prepared plan was supplied; merely having an @task is not enough.
                assert seen == []
            assert "constructBuilding" not in page._task_names
        finally:
            _dispose(page, qt_app)


def test_native_navigation_uses_one_contextual_automation_workspace(qt_app, monkeypatch):
    import daedalus.desktop.app as module
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    window = MainWindow()
    try:
        assert window._task_views == (window.tasks_page,)
        operations = [
            {"name": "alertLowWine", "kind": "background_task"},
            {"name": "constructionList", "kind": "background_task"},
        ]
        window._show_accounts([{
            "id": "alpha", "player": "Example", "world": "s1-en", "enabled": True,
        }])
        window._show_capabilities({
            "operations": operations, "structured_engine_dispatch": False
        })
        page = window.tasks_page
        page.select_workflow("wine")
        assert page._task_names == ["alertLowWine"]
        assert not page.start_button.isEnabled()
        page.select_workflow("construction")
        assert page._task_names == ["constructionList"]
        assert not page.start_button.isEnabled()
        window._show_capabilities({
            "operations": operations, "structured_engine_dispatch": True
        })
        page.select_workflow("wine")
        assert not page.start_button.isEnabled()
        page.set_preflight({
            "account_id": "alpha", "task": "alertLowWine",
            "ready": True, "reason": "none"
        })
        assert page.start_button.isEnabled()
        page.select_workflow("construction")
        assert not page.start_button.isEnabled()  # no inherited preflight
        page.set_preflight({
            "account_id": "alpha", "task": "constructionList",
            "ready": True, "reason": "none"
        })
        assert not page.start_button.isEnabled()  # no reviewed construction plan
        window._on_completed("task_list", {
            "account_id": "alpha", "engine_tasks": [
                {"task": "alertLowWine", "status": "running", "pid": 1001,
                 "task_id": "a" * 24},
            ], "requests": [],
        })
        assert page.task_table.rowCount() == 1
    finally:
        _dispose(window, qt_app)


def test_protected_admin_settings_scope(qt_app):
    from daedalus.desktop.appearance_page import AppearancePage

    page = AppearancePage()
    try:
        page.set_admin_accounts([
            {"id": "a", "player": "Player A", "world": "s1-en", "enabled": True},
            {"id": "b", "player": "Player B", "world": "s2-en", "enabled": True},
            {"id": "c", "player": "Disabled", "world": "s3-en", "enabled": False},
        ])
        assert page.admin_account.count() == 3
        page.admin_account.setCurrentIndex(1)
        calls = []
        page.administrative_status_requested.connect(calls.append)
        page._request_admin_status()
        assert calls == ["a"]
        settings = {"telegram": "configured", "discord": "not_configured",
                    "proxy_enabled": True, "proxy_protocol": "socks5", "proxy_port": 9050,
                    "proxy_auth": True, "challenge_provider": "default", "registered_extensions": 1}
        page.set_admin_status({"account_id": "b", "settings": settings})
        assert not page.admin_rows.text()
        page.set_admin_status({"account_id": "a", "settings": settings})
        assert "Telegram: configured" in page.admin_rows.text()
        page.admin_account.setCurrentIndex(2)
        assert not page.admin_rows.text()
    finally:
        _dispose(page, qt_app)


def test_proxy_profile_editor_rejects_foreign_status_and_busy_account(qt_app):
    from daedalus.desktop.appearance_page import AppearancePage

    page = AppearancePage()
    try:
        page.set_admin_accounts([{"id":"alpha","player":"Player","world":"s1-en","enabled":True}])
        page.admin_account.setCurrentIndex(1)
        observed = {"account_id":"alpha","revision":"a"*64,"enabled":False,"current":None,
                    "allow_direct":True,"busy":False,"result":"observed",
                    "profiles":[{"id":"office","label":"Office network","protocol":"http"}]}
        page.set_proxy_profiles({**observed,"account_id":"beta"})
        assert page.proxy_picker.count() == 0
        page.set_proxy_profiles(observed)
        assert page.proxy_picker.count() == 3
        page.proxy_picker.setCurrentIndex(2)
        assert page.proxy_test.isEnabled() and page.proxy_save.isEnabled()
        page.set_proxy_profiles({**observed,"busy":True})
        page.proxy_picker.setCurrentIndex(2)
        assert not page.proxy_test.isEnabled() and not page.proxy_save.isEnabled()
    finally:
        _dispose(page, qt_app)


def test_native_scroll_surfaces_follow_runtime_theme(qt_app, monkeypatch):
    from PySide6.QtGui import QPalette
    from qfluentwidgets import Theme, setTheme

    import daedalus.desktop.app as module
    from daedalus.desktop.theme import apply_app_palette
    from daedalus.gui_preferences import GuiPreferences

    monkeypatch.setattr(module, "load_gui_preferences", lambda: GuiPreferences())
    monkeypatch.setattr(MainWindow, "_auto_reconnect_securely", lambda _: None)
    setTheme(Theme.LIGHT)
    apply_app_palette()
    window = MainWindow()
    try:
        for theme, expected in ((Theme.DARK, "#1c1c1e"), (Theme.LIGHT, "#f5f5f7")):
            setTheme(theme)
            apply_app_palette()
            qt_app.processEvents()
            for scroll in (window.home_page.content_scroll, window.tasks_page.discovery_scroll, window.tasks_page.parameter_scroll):
                for surface in (scroll, scroll.viewport(), scroll.widget()):
                    assert surface.palette().color(QPalette.Window).name() == expected
    finally:
        setTheme(Theme.LIGHT)
        apply_app_palette()
        _dispose(window, qt_app)
