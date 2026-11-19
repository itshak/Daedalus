# Architecture — target design and current implementation

The product is a single **monorepo**, with distinct installable/runtime components. The diagram summarizes the now-implemented controller and opt-in worker paths. Native Mac human browser login with encrypted handoff is implemented and synthetic-tested; owner-supervised real CAPTCHA/rebind/task acceptance remains outstanding. See [implementation status](PROJECT-STATUS.md).

```text
PySide6 desktop (Mac/Windows/Linux)
        |
        | versioned authenticated API (local or private network)
        v
Daedalus backend: accounts, policies, scheduler, task registry,
                  snapshots, history, authentication coordination
        |
        | local IkaBot CLI/IPC (validated typed JSON messages)
        v
Upstream-tracked IkaBot engine and native task modules
        |
        v
One authenticated game session per account/world/player
```

## Invariants

- No new parallel game-protocol implementation in the controller.
- The explicit `--demo` mode is a **synthetic, isolated offline preview**: it cannot read real account files, attach IPC or control game tasks and visibly labels all sample data. It is not a way to simulate real authentication.
- The explicit `--connect-existing-ipc` attachment reads cities and warehouse spans from a compatible already-authenticated engine without creating a login. A separate `--enable-task-control` flag permits validated built-in background task start/list/stop on this existing session. Durable task idempotency and opt-in dedicated session monitoring exist, with separate human browser recovery. Automated login and unattended CAPTCHA solving are not supported.
- One authoritative account session owner; a Mac Qt WebEngine off-record browser presents human Gameforge login and encrypts only the exact secure world session to a one-use account-bound server challenge. The backend independently validates game-world player identity while holding the same worker lease. Real-world login/rebind acceptance is still pending.
- Desktop API is transport-independent and not tied to tmux.
- Bot workers run under a process supervisor; tmux is for diagnostic access only.
- State-changing operations use idempotency keys and reconcile observed game state after interruptions.
- Warehouse snapshots distinguish total vs. unsecured resources and their freshness.
- Dedicated task views may coexist with automatically generated forms from a module schema.

See OpenSpec capability specs and ADRs for normative requirements.
