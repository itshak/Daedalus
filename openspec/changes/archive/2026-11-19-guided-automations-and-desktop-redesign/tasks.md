# Implementation tasks

- [x] Add a fail-closed, nonsecret, authenticated task-prerequisite IPC and REST endpoint.
- [x] Distinguish deterministic preflight rejection from an uncertain, possibly executed task and test both.
- [x] Redesign native Mac navigation and task configuration into guided GUI controls, with advanced JSON optional.
- [x] Add synthetic API, engine IPC and offscreen native GUI regression coverage for the redesigned workflow.
- [x] Provision and verify direct trusted HTTPS to the loopback-only backend, without Mac SSH, and test tokenless 401 and authorized account retrieval.
- [x] Make Keychain saving the default, add HTTPS-only automatic reconnect and prevent cross-origin saved-token reuse.
- [x] Update reference docs, verify offline tests and GitHub PR checks under `itshak`, and avoid affecting Monjo's active live session during development.

Implementation field note (2026-11-19): this change does not launch any game
operation, manipulate saved cookies, or count as owner acceptance of the native
macOS app. The previously unconfirmed Monjo alert request remains for manual
reconciliation; a future new task will require new user approval.
