# Tasks
- [x] Record and import clean upstream engine revision with MIT license notices.
- [x] Reconcile pinned upstream fixes and six tracked production auth source changes without importing secrets: independently adapt bounded token API retries and detached-worker fail-fast, reject unsafe legacy auto-login, document per-file dispositions and reviewed patch fingerprint (see `docs/ENGINE-AUTH-RECONCILIATION.md`).
- [x] Test proposed JSON CLI/IPC and batch support with synthetic sessions.
- [x] Implement a validated existing-session task registry adapter with start/list/stop lifecycle responses.
- [x] Verify existing-session identity isolation, task ownership and failure paths offline.
- [x] Run lint, package build and OpenSpec validation after the JSON CLI/IPC integration.

## Completed baseline checks
- [x] Verify all 90 upstream file blobs match the public source commit.
- [x] Add a read-only engine capability registry with offline tests.
- [x] Run 99 upstream tests plus 30 subtests, 7 Daedalus tests, and strict OpenSpec validation.

## Final production-source review
- [x] Verify official upstream master and PR #499 match the pinned stable/proposed commit IDs, including reviewed #502/#511 fixes.
- [x] Review all six modified tracked production Python files without copying any code or reading account runtime secrets.
- [x] Add synthetic failure-path tests for bounded API retries, sanitized errors, interactive-only authorization and detached EOF.
- [x] Record explicit accept/reject/already-upstream decisions, attribution and scope boundaries; keep live auth gates in `validate-live-authentication`.
