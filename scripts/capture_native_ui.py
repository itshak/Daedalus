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
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from daedalus.desktop import app as desktop_app
from daedalus.desktop.theme import apply_app_palette
from daedalus.gui_preferences import GuiPreferences


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

SYNTHETIC_OPERATIONS = [
    {"name": "alertAttacks", "kind": "background_task",
     "config_fields": [{"name": "minutes", "type": "integer", "default": 20}]},
    {"name": "alertLowWine", "kind": "background_task",
     "config_fields": [
         {"name": "hours", "type": "json", "required": True},
         {"name": "auto_transfer", "type": "boolean", "default": False},
         {"name": "transfer_amount", "type": "integer", "default": 0},
     ]},
    {"name": "tavernManager", "kind": "background_task",
     "config_fields": [{"name": "run_hours", "type": "json", "required": True}]},
    {"name": "constructionList", "kind": "background_task",
     "config_fields": [{"name": "city_id", "type": "json", "required": True}]},
    {"name": "research", "kind": "background_task",
     "config_fields": [{"name": "cities_ids", "type": "json", "default": None}]},
    {"name": "statusMenu", "kind": "interactive_menu"},
]


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
    ):
        window = desktop_app.MainWindow()
        window.setWindowTitle("Daedalus — SYNTHETIC UI FIXTURES")
        window._show_accounts(SYNTHETIC_ACCOUNTS)
        window.home_page.set_connected(True, demo=True)
        window.connection_page.set_connected(True, demo=True)
        window.warehouses_page.set_demo(True)
        window.warehouses_page.set_batch_snapshots(SYNTHETIC_REPORT)
        window._show_capabilities({
            "operations": SYNTHETIC_OPERATIONS,
            "structured_engine_dispatch": False,
            "session_monitoring": False,
        })

        destinations = [
            ("overview", window.home_page),
            ("accounts", window.accounts_page),
            ("warehouses", window.warehouses_page),
            ("automations", window.tasks_page),
            ("activity", window.log_page),
            ("connection", window.connection_page),
            ("settings", window.appearance_page),
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
                    app.processEvents()
                    for label, page in destinations:
                        window.switchTo(page)
                        app.processEvents()
                        file = output_dir / f"{name}-{width}x{height}-{label}.png"
                        if not window.grab().save(str(file), "PNG"):
                            raise RuntimeError(f"Could not capture synthetic {label} screenshot")
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
