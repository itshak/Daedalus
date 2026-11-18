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

The [legacy GUI source and dependency audit](LEGACY-GUI-AUDIT.md) records the file-by-file parity matrix, license metadata, deliberately excluded secrets and remaining acceptance gates. The source/license review task is complete; functional parity is not.

## Current UI scope

The `daedalus-desktop` entry point opens the Fluent desktop with these pages:
- **Accounts:** protected metadata and backend-reported session status
- **Warehouses:** per-account unsecured counts, optional island grouping, 220K filter, copy CSV and save CSV/JSON/TXT
- **Operations:** read-only discovery of all built-in tasks/menu operations
- **Tasks:** opt-in, confirmed built-in background task launch/list/stop through an existing authenticated engine session; parameter-aware forms generated from upstream public task signatures, plus an advanced JSON editor
- **Log:** local bounded UI diagnostics
- **Connection:** local or HTTPS/SSH-tunneled API URL and a masked bearer-token field
- **Appearance:** local-only theme and reporting defaults, no game credentials

The Accounts page offers confirmed **Add/Edit/Enable/Disable/Remove** account metadata controls only when the backend is separately started with `--enable-account-editing`; the controls never accept credentials or launch authentication. It also provides an explicit **Check IkaBot sessions** button; only configured identities with a unique matching existing engine session show Attached. The warehouse view can read live data after the backend is explicitly started with `--connect-existing-ipc` against a compatible, already-authenticated engine. Neither operation creates a login; see [existing engine attachment](EXISTING-IPC.md).

Backend requests run in a Qt worker thread. A connection may be replaced without restarting the app. Bearer tokens remain in memory by default. Users may explicitly opt in to saving a validated backend URL in owner-private settings and its bearer token in the operating-system keyring. The GUI also offers user-directed reconnect and Forget saved connection controls. No legacy credentials are imported.

No game login or Selenium browser is launched by the GUI. Warehouse data can now come from the opt-in read-only existing-session IPC bridge when a compatible engine process already holds a valid authenticated session; otherwise the UI displays an explicit unavailable error. The Accounts page can also show which configured accounts have an attached engine session.

## Completed nonsecret legacy GUI parity

The reviewed native Fluent desktop now contains the owner's original safe
account/report/settings interactions, backed by a single Daedalus API client:

- **Accounts:** opt-in Add/Edit/Enable/Disable/Remove for secret-free metadata,
  per-account inclusion checkboxes and Select All for warehouse reporting.
  Report inclusion never changes account enablement or starts game tasks.
- **Warehouses:** single-account or **Load selected accounts** (up to 32),
  including per-account labels, 220K filter, null-not-zero values, grouping by
  validated island, Copy CSV, **Copy by island**, and TXT/CSV/JSON exports.
  Partial backend failures remain conspicuous; successful rows can still be
  copied or saved without pretending failed accounts returned zero.
- **Appearance:** System/Light/Dark themes, 220K default and island grouping
  default, stored in a separate versioned owner-private
  `~/.config/daedalus/gui.json` file (or `XDG_CONFIG_HOME`).
  Report exclusions are keyed by the SHA-256 of the validated backend URL,
  so a different backend never reuses the last backend's account selection.
  The file has no game credentials, session cookies or API bearer tokens.
- **Connection:** switching to another successfully authenticated backend
  clears all previously loaded warehouse reports.

The original `config.ini` username/email/password, direct Selenium runner,
browser-choice/headless/retry/tokens settings and automatic login are
**intentionally not ported**. Manual browser/CAPTCHA recovery, remote
assistance and server-side player attestation are tracked separately under
`validate-live-authentication`. Native Mac notarization, production testing
and third-party binary redistribution obligations are also separate release
gates. The completed **nonsecret** migration does not imply a production login.


## License

Daedalus-original code is GPL-3.0-only. The proprietary author-owned legacy GUI code was adapted by its owner for this repo. `PySide6-Fluent-Widgets` carries separate terms; the chosen GPL approach must be reviewed together with its dependencies before binary distribution. See `docs/UPSTREAM.md`.

## Headless CI

The normal Python tests run without optional Qt dependencies; UI tests skip when those are absent. The dedicated macOS GitHub Actions workflow installs `daedalus[desktop,dev]` and uses `QT_QPA_PLATFORM=cocoa` for native Fluent window tests. The macOS frameless window needs a real NSWindow; forcing the offscreen plugin crashes the native window implementation. Linux smoke tests use `QT_QPA_PLATFORM=offscreen` instead.
