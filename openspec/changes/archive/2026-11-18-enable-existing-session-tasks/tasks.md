# Tasks

## Engine
- [x] Add existing-session-only task start without saved-session restoration.
- [x] Restrict built-in task modules and validate JSON/task IDs.
- [x] Track and stop only exact Daedalus-launched child process objects.
- [x] Add UUID4 request idempotency for retries.
- [x] Add fake-process engine regression tests.

## Controller and GUI
- [x] Add separate task IPC client without weakening read-only actions.
- [x] Require explicit backend opt-in and authenticated, account-scoped routes.
- [x] Add native Fluent Tasks page and user confirmation of mutations.
- [x] Add API, IPC wire and Qt synthetic tests.

## Verification
- [x] Run full Daedalus/engine tests, lint, source guard and strict OpenSpec.
- [x] Confirm passing GitHub CI and Mac app build.
- [x] Merge via itshak, archive completed change and sync canonical specs.
