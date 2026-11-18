# Tasks
- [x] Review and license-audit existing GUI sources and dependencies (see `docs/LEGACY-GUI-AUDIT.md`).
- [x] Port the reviewed Fluent navigation, read-only accounts/warehouse/operations views and CSV/JSON exports into `daedalus.desktop`.
- [x] Complete reviewed **nonsecret** legacy GUI parity: native protected account metadata editor, per-account report inclusion/select-all, multi-account warehouse report retrieval and island-grouped clipboard export, plus local System/Light/Dark theme and display settings. Authentication/browser controls remain with `validate-live-authentication`.
- [x] Implement versioned local/remote API client with masked in-memory bearer token and protected transport.
- [x] Add optional secure persistent connection preferences and reconnect UX.
- [x] Implement UI filtering and CSV/JSON exports with null distinct from zero, using backend snapshot contract.
- [x] Wire warehouse snapshots through the opt-in compatible existing-session IPC provider.
- [x] Add a dedicated Tasks workflow page with a generic JSON configuration editor and managed start/stop controls.
- [x] Implement task-specific parameter forms for native background operations (with advanced JSON fallback).
- [x] Test native GUI and .app packaging in macOS CI and validate OpenSpec.

## Final GUI parity evidence (2026-11-18)
- [x] Offline native Qt regression tests cover report-selection refresh, multi-account read-only queries, explicit partial failures, persistent appearance settings and backend isolation.
- [x] Secure settings tests cover schema/version restrictions, owner-only atomic storage, symlink rejection, per-backend scope hashing and credential-free contents.
- [x] Provide dedicated Wine and Construction task workflow pages with typed registered background-task forms and the original backend safety checks.
- [x] Preserve historical browser/credential separation: GUI never imports the legacy Selenium runner, passwords, profile data, or token stores; live recovery is tracked in `validate-live-authentication`.
