# Connect the read-only controller to already-authenticated IkaBot IPC

## Why
The native desktop can display account metadata but cannot yet receive real city and warehouse records. The current upstream candidate IPC launcher may restore a saved session when it cannot find one. Daedalus must never silently create a second account login while attaching to a worker.

## What Changes
- Extend the vendored IkaBot IPC server with nonsecret, **existing-session-only** identity, city and warehouse-read actions; preserve upstream CLI behavior separately.
- Add a strictly read-only local IPC transport that validates its owner-only descriptor, binds the connection to loopback, and never permits `start_task` or other mutating actions.
- Make backend connection explicitly opt-in via `--connect-existing-ipc`; add authenticated `connected-accounts` and `cities` HTTP reads.
- Route the existing warehouse API through the attached engine session, parsing only numeric resource values and never returning raw game HTML.
- Expose existing-engine attachment status in the native Accounts view without treating it as a new game-session owner.
- Verify end-to-end synthetic IPC sockets, forged descriptors, identity mismatch, API token checks, and Qt UI status offline.

## Modified capabilities
- `engine-integration`: existing authenticated session-only IPC operations.
- `controller-api`: opt-in read-only attached engine APIs.
- `warehouse-monitoring`: typed warehouse snapshots from the current engine session.
- `desktop-client`: existing IkaBot session status and connected warehouse workflow.

## Non-goals
No duplicate Gameforge login, new account worker creation, live task start/stop, browser CAPTCHA handling, production cutover, public socket exposure or automatic session restoration.
