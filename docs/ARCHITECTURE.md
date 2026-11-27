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


## Global account working context (v0.1.1 implementation)

The shell owns a working account preference: either dynamic **all authorized
accounts**, or an explicit set of stable account IDs (including the empty
set). The effective inventory is the intersection of the preference and the
current authorized roster. Explicitly selected deleted IDs are removed; an
empty explicit set is never interpreted as all. Display names are player
nicknames with world/ID disambiguation, not identity keys.

The web workspace uses `apps/web/lib/account-scope.ts`, with a preference
namespaced by an opaque hash of the authenticated operator and controller
origin. The native shell stores only account IDs under its existing
backend-scoped local GUI preferences; legacy report exclusions migrate on
connection. Global context changes invalidate account-dependent editors,
review queues and asynchronous read generations. Account-specific operations
may refine their target within the working scope; account management has an
explicit manage-all exception. The controller's existing authorization,
idempotency and review-ticket validation remain independent of this UI
preference. No task stop, restart or game mutation is implied by changing
scope. Production and future activity views should consume the shell's
effective roster, rather than introducing another global selection.

Controller health, release metadata, authentication, appearance and
connection settings remain global; sanitized untagged native diagnostic
messages are not misrepresented as account activity. Account-bound settings,
warehouse reports and exports, military observations, managed tasks and
server receipts use the working roster.
