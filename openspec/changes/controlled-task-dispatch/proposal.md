# Add explicitly enabled native task controls through existing IkaBot IPC

## Why
After the verified read-only IPC milestone, the desktop can show city resources but still cannot start or stop the public IkaBot engine's background tasks. The project needs a real, authorization-checked task lifecycle without a second login, arbitrary PID termination, or silent duplicate launches after interrupted requests.

## What changes
- Add distinct existing-session-only engine IPC operations to start, enumerate and stop **Daedalus-managed** child processes.
- Add a separate opt-in ControlledIPCClient and conservative local AccountSessionCoordinator ownership.
- Add a private SQLite idempotency ledger that stores no task configs or secrets and prevents automatic repeat dispatch.
- Add bearer-protected, explicitly enabled task HTTP routes for start/list/stop and operator acknowledgment of uncertain outcomes.
- Add a native Fluent Tasks page with account/task selection, JSON config, explicit confirmation, task list and stop/reconciliation actions.
- Cover IPC and HTTP with synthetic processes, persisted request data, login-restoration denial, and Qt tests.

## Modified capabilities
- `engine-integration`: managed existing-session task operations
- `controller-api`: opt-in mutation endpoints
- `account-sessions`: host-local lease acquisition before game-task dispatch
- `desktop-client`: first task lifecycle controls
- `automation-controller`: durable at-most-once request dispatch and manual reconciliation

## Non-goals
No unattended saved-session login, CAPTCHA solving, production bot migration, arbitrary process killing, task-policy scheduler, automatic game-state reconciliation, distributed account leases, or full generated forms for every module.

## Impact
Real end-to-end desktop/backend/engine task control for compatible pre-authenticated test accounts, with conservative ownership and retry semantics. See ADR-001, ADR-003 and `docs/TASK-CONTROL.md`.
