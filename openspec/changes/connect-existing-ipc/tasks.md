# Tasks

## Engine safety
- [x] Add distinct existing-session-only IPC actions without changing the stable upstream CLI actions.
- [x] Refuse missing/ambiguous identities before a saved-session restore.
- [x] Scrub raw warehouse HTML and return numeric-only resource data.

## Backend / GUI
- [x] Add owner-only, loopback-only, read-only IPC transport with bounded responses.
- [x] Expose opt-in authenticated connected-account and per-account city APIs.
- [x] Back warehouse snapshots with the attached, authenticated existing session.
- [x] Add native GUI attached-engine status without game login or secrets.

## Verification
- [x] Add synthetic socket, engine session and Qt/API integration tests.
- [x] Complete full local offline tests, lint, OpenSpec and source-security guard.
- [ ] Confirm GitHub CI and reviewer checks are green.
- [ ] Merge through itshak, archive completed OpenSpec change and sync documentation/specs.
