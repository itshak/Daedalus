# Architecture — target design and current implementation

The product is a single **monorepo**, with distinct installable/runtime components. The diagram below represents the **target** architecture, not the current runtime: the desktop client and read-only API exist, but real supervised IkaBot workers, authenticated account handoff and task orchestration are still forthcoming. See [implementation status](PROJECT-STATUS.md).

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
- The explicit, read-only `--connect-existing-ipc` attachment reads cities and warehouse spans from a compatible already-authenticated engine; it never creates a game login. Task dispatch and session restoration are still separate planned work.
- One account session owner; browser-assisted login is coordinated through the owner.
- Desktop API is transport-independent and not tied to tmux.
- Bot workers run under a process supervisor; tmux is for diagnostic access only.
- State-changing operations use idempotency keys and reconcile observed game state after interruptions.
- Warehouse snapshots distinguish total vs. unsecured resources and their freshness.
- Dedicated task views may coexist with automatically generated forms from a module schema.

See OpenSpec capability specs and ADRs for normative requirements.
