# Design — desktop migration

Review local `src/ikabot/gui`, `models.py`, `report.py` and settings file by file before porting. Rename the GUI package to avoid colliding with the upstream engine's `ikabot` import name. Preserve native PySide6 Fluent look and macOS window behavior; audit dependency licenses.

Replace the Selenium-only report runner with a typed Daedalus backend API client. Keep CSV, JSON, text, island-grouped exports and the 220K unsecured-resource filter. Provide generic task forms driven by engine schemas, with dedicated views for warehouses, wine and construction.

Handle backend login-required notifications without ever logging raw credentials or creating independent browser game sessions for reporting.

### Final nonsecret parity boundary
The Accounts view now retains per-account report inclusion across list refresh,
with Select All and a final report-selection column (independent of backend
enable/disable state). The Warehouses view can fetch up to 32 selected accounts
through sequential **read-only** existing API requests off the Qt thread, preserve
successful rows while explicitly naming failed accounts, and copy island-grouped
TXT as in the legacy Run page. It never launches a scraper or task.

The Appearance view persists System/Light/Dark theme and warehouse filter/grouping
in a separately versioned, private, atomic GUI preferences file. Exclusions
are keyed by a SHA-256 digest of a validated backend URL; no bearer, password,
cookie, email, browser profile or original config.ini is saved. Switching
backends clears previously loaded snapshots and restores only that backend's
selection. The native metadata editor remains explicitly opt-in and
backend-validated.

The remaining legacy password/browser fields and live Selenium recovery are
**not** desktop-migration parity: they are owned by `validate-live-authentication`.
Notarization and binary dependency-license compliance remain release gates,
not evidence of production authentication.
