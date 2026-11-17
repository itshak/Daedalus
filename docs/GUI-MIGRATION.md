# Native GUI migration — first preview

## Source provenance

This Daedalus desktop is an **adaptation of the owner's existing private PySide6/Fluent GUI**, not a rewritten web application.

Reviewed legacy files:
- `src/ikabot/gui/main_window.py`: Fluent navigation, Mac traffic-light placement, queued-signal logging, safe worker shutdown
- `src/ikabot/gui/theme.py`: matching Fluent and native Qt widget palette
- `src/ikabot/gui/widgets.py`: scrollable Fluent tables and opaque card backgrounds
- `src/ikabot/gui/log_page.py`: bounded read-only log
- `src/ikabot/gui/accounts_page.py`: account-list visual organization
- `src/ikabot/gui/run_page.py`: warehouse resource table and 220K unsecured-resource filtering
- `src/ikabot/report.py`: CSV/JSON report/export patterns

Code has been adapted into `src/daedalus/desktop/`, with an independent, read-only HTTP client in `src/daedalus/client.py` and pure reporting utilities in `src/daedalus/reporting.py`. The original scraper, Selenium worker, legacy config.ini, token/cookie storage and private Git history were **not** copied into Daedalus.

## Current UI scope

The `daedalus-desktop` entry point opens the Fluent desktop with these pages:
- **Accounts:** protected metadata and backend-reported session status
- **Warehouses:** per-account unsecured counts, 220K filter, copy/save CSV and JSON
- **Operations:** all discovered engine tasks/menu operations; **read-only, no start button yet**
- **Log:** local bounded UI diagnostics
- **Connection:** local or HTTPS/SSH-tunneled API URL and a masked bearer-token field

Backend requests run in a Qt worker thread. A connection may be replaced without restarting the app. Bearer tokens exist in process memory only; there is no settings file or implicit credentials import.

No game login or Selenium browser is launched by the GUI. Warehouse data requires a real server-side authenticated session snapshot provider; until one exists, the UI should display an explicit unavailable error.

## UI parity still to complete

This is a **foundation**, not a complete port. The existing multi-account edit dialogs, island-grouped text exports, browser login assistant, task-specific editors, start/stop/pause flows, notifications, persistent GUI settings and native .app packaging remain future changes. The objective remains reusing the original GUI while replacing Selenium-only reporting and bespoke interactive menus with backend APIs.

## License

Daedalus-original code is GPL-3.0-only. The proprietary author-owned legacy GUI code was adapted by its owner for this repo. `PySide6-Fluent-Widgets` carries separate terms; the chosen GPL approach must be reviewed together with its dependencies before binary distribution. See `docs/UPSTREAM.md`.

## Headless CI

The normal Python tests run without optional Qt dependencies; UI tests skip when those are absent. The dedicated macOS GitHub Actions workflow installs `daedalus[desktop,dev]` and uses `QT_QPA_PLATFORM=cocoa` for native Fluent window tests. The macOS frameless window needs a real NSWindow; forcing the offscreen plugin crashes the native window implementation. Linux smoke tests use `QT_QPA_PLATFORM=offscreen` instead.
