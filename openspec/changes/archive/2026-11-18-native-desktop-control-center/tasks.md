# Tasks

## Desktop transport
- [x] Add read-only, bearer-authenticated HTTP client with local/TLS restrictions.
- [x] Add synthetic mock-transport tests for status, accounts, capabilities and warehouses.
- [x] Prevent tokens and raw HTTP response bodies from reaching logs or exceptions.

## Preserve the native design
- [x] Port Fluent sidebar and Mac titlebar conventions from the existing GUI.
- [x] Port theme, scrollable table, bounded log and queued-signal patterns.
- [x] Add Accounts, Operations, Warehouses and Connection pages.
- [x] Fetch API data on a Qt worker thread rather than blocking the UI.
- [x] Preserve the 220K warehouse filter and CSV/JSON exports.

## Verification and documentation
- [x] Record reviewed GUI source provenance and intentionally excluded legacy files.
- [x] Add headless Qt smoke tests and a dedicated macOS desktop workflow.
- [x] Verify desktop dependencies actually install and Qt smoke tests run in CI.
- [x] Run all basic tests, linting, OpenSpec and security checks.
- [x] Merge only after clean GitHub CI under the itshak identity.
