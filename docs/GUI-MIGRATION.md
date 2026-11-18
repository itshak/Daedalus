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

Code has been adapted into `src/daedalus/desktop/`, with an independent, secure HTTP client (read-only by default; mutating calls explicitly gated) in `src/daedalus/client.py` and pure reporting utilities in `src/daedalus/reporting.py`. The original scraper, Selenium worker, legacy config.ini, token/cookie storage and private Git history were **not** copied into Daedalus.

## Current UI scope

The `daedalus-desktop` entry point opens the Fluent desktop with these pages:
- **Accounts:** protected metadata and backend-reported session status
- **Warehouses:** per-account unsecured counts, optional island grouping, 220K filter, copy CSV and save CSV/JSON/TXT
- **Operations:** read-only discovery of all built-in tasks/menu operations
- **Tasks:** opt-in, confirmed built-in background task launch/list/stop through an existing authenticated engine session; generic JSON configuration editor
- **Log:** local bounded UI diagnostics
- **Connection:** local or HTTPS/SSH-tunneled API URL and a masked bearer-token field

The Accounts page provides an explicit **Check IkaBot sessions** button; only configured identities with a unique matching existing engine session show Attached. The warehouse view can read live data after the backend is explicitly started with `--connect-existing-ipc` against a compatible, already-authenticated engine. Neither operation creates a login; see [existing engine attachment](EXISTING-IPC.md).

Backend requests run in a Qt worker thread. A connection may be replaced without restarting the app. Bearer tokens exist in process memory only; there is no settings file or implicit credentials import.

No game login or Selenium browser is launched by the GUI. Warehouse data can now come from the opt-in read-only existing-session IPC bridge when a compatible engine process already holds a valid authenticated session; otherwise the UI displays an explicit unavailable error. The Accounts page can also show which configured accounts have an attached engine session.

## UI parity still to complete

This is a **foundation**, not a complete port. The existing multi-account edit dialogs, browser login assistant, task-specific configuration forms, durable resume/reconciliation, notifications, persistent GUI settings and notarized distribution remain future changes. The objective remains reusing the original GUI while replacing Selenium-only reporting and bespoke interactive menus with backend APIs.

## License

Daedalus-original code is GPL-3.0-only. The proprietary author-owned legacy GUI code was adapted by its owner for this repo. `PySide6-Fluent-Widgets` carries separate terms; the chosen GPL approach must be reviewed together with its dependencies before binary distribution. See `docs/UPSTREAM.md`.

## Headless CI

The normal Python tests run without optional Qt dependencies; UI tests skip when those are absent. The dedicated macOS GitHub Actions workflow installs `daedalus[desktop,dev]` and uses `QT_QPA_PLATFORM=cocoa` for native Fluent window tests. The macOS frameless window needs a real NSWindow; forcing the offscreen plugin crashes the native window implementation. Linux smoke tests use `QT_QPA_PLATFORM=offscreen` instead.
