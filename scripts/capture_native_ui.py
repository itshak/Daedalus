"""Capture strictly synthetic native desktop UI baselines (no game/API access).

Used by macOS Cocoa CI and available locally with QT_QPA_PLATFORM=offscreen.
All displayed identities and resources are invented fixtures. We deliberately
override connection loaders so this script never reads private preferences,
keychains, sessions, cookies or environment-provided access tokens.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolTip
from qfluentwidgets import Theme, setTheme

from daedalus.desktop import app as desktop_app
from daedalus.desktop.theme import apply_app_palette
from daedalus.gui_preferences import GuiPreferences
from daedalus.engine_registry import inspect_engine
from daedalus.operation_manifest import operation_workflow

SYNTHETIC_ACCOUNTS = [
    {
        "id": "synthetic-alpha", "label": "Orion (sample)",
        "world": "example-world", "player": "Demo Player A",
        "enabled": True, "session_status": "authenticated",
    },
    {
        "id": "synthetic-beta", "label": "Cassiopeia (sample)",
        "world": "example-world", "player": "Demo Player B",
        "enabled": True, "session_status": "needs_assistance",
    },
]

SYNTHETIC_REPORT = [
    {
        "account_id": "synthetic-alpha",
        "cities": [
            {
                "city_name": "Athena (sample)", "island": "12:34",
                "resources": {"unsecured": {
                    "wood": 255_000, "wine": 0, "marble": 1234,
                    "glass": 500, "sulfur": 800,
                }},
            },
            {
                "city_name": "Delphi (sample)", "island": "12:34",
                "resources": {"unsecured": {
                    "wood": 1000, "wine": 42, "marble": None,
                    "glass": 100, "sulfur": 120,
                }},
            },
        ],
    },
    {"account_id": "synthetic-beta", "error": True},
]

def synthetic_operations():
    # Static source AST inventory, no IkaBot imports or game networking.
    return [{**item.to_dict(), "workflow": operation_workflow(item.name)}
            for item in inspect_engine()]


def capture(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])

    # The screenshot command cannot look up a saved backend or other private
    # connection data. It never constructs DaedalusClient or starts an IPC task.
    with (
        patch.object(desktop_app, "load_gui_preferences", return_value=GuiPreferences()),
        patch.object(desktop_app.MainWindow, "_auto_reconnect_securely", lambda self: None),
        patch("daedalus.connection_prefs.load_connection_url", return_value=None),
        patch("daedalus.desktop.ssh_tunnel.load_ssh_destination", return_value=None),
        patch.object(desktop_app.MainWindow, "_request", lambda *args, **kwargs: None),
    ):
        setTheme(Theme.LIGHT)
        apply_app_palette()
        window = desktop_app.MainWindow()
        window.setWindowTitle("Daedalus — SYNTHETIC UI FIXTURES")
        window._show_accounts(SYNTHETIC_ACCOUNTS)
        window.home_page.set_connected(True, demo=True)
        window.connection_page.set_connected(True, demo=True)
        window.warehouses_page.set_demo(True)
        window.warehouses_page.set_batch_snapshots(SYNTHETIC_REPORT)
        window._show_capabilities({
            "operations": synthetic_operations(),
            "structured_engine_dispatch": True,
            "session_monitoring": False,
        })

        window.appearance_page.admin_account.setCurrentIndex(1)
        window.accounts_page.table.selectRow(0)
        window.tasks_page.select_task("alertAttacks")
        window.tasks_page.set_preflight({"account_id": "synthetic-alpha", "task": "alertAttacks", "ready": True})
        window.tasks_page.set_cities("synthetic-alpha", [{"id": 101, "name": "Athena (sample)"}, {"id": 102, "name": "Delphi (sample)"}])
        window.military_page.set_result("synthetic-alpha", "military_overview", {
            "account_id": "synthetic-alpha", "observed_at": 1795160000,
            "cities": [{"city_id": 101, "city_name": "Athena (sample)",
                        "troops": [{"unit": "Swordsman", "amount": 125}, {"unit": "Hoplite", "amount": 80}],
                        "fleet": [{"unit": "Ram ship", "amount": 12}]}],
        })
        window.military_page.set_result("synthetic-alpha", "military_movements", {
            "account_id": "synthetic-alpha", "observed_at": 1795160000,
            "movements": [{"origin": "Athena (sample)", "destination": "Delphi (sample)",
                           "mission": "Transport", "hostile": False, "returning": False,
                           "seconds_remaining": 600, "troops": 0, "ships": 6}],
        })
        window.military_page.set_unavailable("synthetic-beta", "military_overview")
        window.tasks_page.set_tasks({"engine_tasks": [{"task": "alertAttacks", "status": "running", "task_id": "a"*24, "started_at": "2026-11-26 10:00"}], "requests": [{"task": "alertAttacks", "status": "started", "task_id": "a"*24}]})
        window.tasks_page.set_batch_status([{"account_id": "synthetic-alpha", "engine_tasks": [{"status": "running"}], "requests": []}, {"account_id": "synthetic-beta", "error": True}])
        window.log_page.add_event("INFO", "Desktop ready")
        window.log_page.add_event("WARNING", "Synthetic request unavailable")
        destinations = [
            ("overview", window.home_page, None),
            ("accounts", window.accounts_page, None),
            ("warehouses", window.warehouses_page, None),
            *[("military-" + name, window.military_page, lambda i=i: window.military_page._select_mode(i))
              for i, name in enumerate(("troops", "fleet", "movements"))],
            *[("automations-" + name, window.tasks_page, lambda i=i: window.tasks_page._show_section(i))
              for i, name in enumerate(("configure", "running", "history", "accounts", "catalog"))],
            ("activity", window.log_page, None),
            ("connection", window.connection_page, None),
            *[("settings-" + name, window.appearance_page, lambda i=i: window.appearance_page.select_section(i))
              for i, name in enumerate(window.appearance_page.section_keys)],
        ]
        created: list[Path] = []
        window.show()
        app.processEvents()
        try:
            for theme, name in ((Theme.LIGHT, "light"), (Theme.DARK, "dark")):
                setTheme(theme)
                apply_app_palette()
                app.processEvents()
                for width, height in ((900, 650), (1200, 800)):
                    window.resize(width, height)
                    window.tasks_page.select_task("alertAttacks")
                    window.tasks_page.set_preflight({"account_id": "synthetic-alpha", "task": "alertAttacks", "ready": True})
                    app.processEvents()
                    for label, page, setup in destinations:
                        window.switchTo(page)
                        if setup is not None:
                            setup()
                        # Allow navigation/pivot animations and deferred layout to settle.
                        QToolTip.hideText()
                        QTest.qWait(350)
                        app.processEvents()
                        file = output_dir / f"{name}-{width}x{height}-{label}.png"
                        if not window.grab().save(str(file), "PNG"):
                            raise RuntimeError(f"Could not capture synthetic {label} screenshot")
                        created.append(file)
                    if width == 900:
                        window.switchTo(window.tasks_page)
                        window.tasks_page._show_section(0)
                        for task in list(window.tasks_page._all_task_names):
                            if not window.tasks_page.select_task(task):
                                raise RuntimeError(f"Could not select native editor {task}")
                            window.tasks_page.set_cities("synthetic-alpha", [{"id": 101, "name": "Athena (sample)"}, {"id": 102, "name": "Delphi (sample)"}])
                            QToolTip.hideText()
                            QTest.qWait(110)
                            file = output_dir / f"{name}-{width}x{height}-editor-{task}.png"
                            if not window.grab().save(str(file), "PNG"):
                                raise RuntimeError(f"Could not capture synthetic editor {task}")
                            created.append(file)
        finally:
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic native Daedalus UI screenshots")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    images = capture(args.output_dir)
    print(f"Captured {len(images)} synthetic Fluent UI screenshots")


if __name__ == "__main__":
    main()
