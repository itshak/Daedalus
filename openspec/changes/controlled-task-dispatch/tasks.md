# Tasks

## Engine task lifecycle
- [x] Add unique existing-authenticated-session-only start/list/stop actions.
- [x] Stop only child processes launched and tracked by the IPC server.
- [x] Preserve original public upstream CLI actions and their tests.

## Controller
- [x] Add explicit opt-in and bearer-protected task HTTP routes.
- [x] Acquire world/player host-local ownership before dispatch; never open a second login.
- [x] Use private persistent request-id deduplication; never persist task configs or credentials.
- [x] Expose manual reconciliation of unknown dispatch outcomes.
- [x] Reject task-creation attempts without explicit confirmation or valid task identity.

## Desktop
- [x] Add native Tasks page for account/task selection, JSON editor and lifecycle listing.
- [x] Require explicit confirmation before running, stopping or acknowledging.
- [x] Keep network requests off the Qt UI thread.

## Verification and release
- [x] Add engine, API, SQLite, socket and native Qt synthetic tests.
- [x] Run complete offline suites, lint, OpenSpec, build and credential guard.
- [ ] Confirm protected branch GitHub CI including native macOS app build.
- [ ] Merge as itshak, then complete tasks and archive OpenSpec with updated permanent specifications.
