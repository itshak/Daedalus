# Design — opt-in task lifecycle

## Engine
The vendored IkaBot IPC server exposes new `start_task_existing`, `list_tasks_existing` and `stop_task_existing` actions. The start operation chooses a uniquely matching in-memory logged-in world/player session without calling `Session.from_saved`, then delegates to upstream's existing task module registry and parameter validation. It records only its own child process handles under random task IDs. List and stop are filtered by the supplied exact world/player identity and can stop **only registered child process objects**, never arbitrary OS PIDs. The previous upstream CLI actions remain unchanged.

## Transport
`ExistingIPCClient` keeps its fixed read-only action allowlist. The separate `ControlledIPCClient` is used only when the operator selects `--enable-task-control` along with `--connect-existing-ipc`. Both use the owner-only authenticated loopback IPC descriptor and bounded JSON messages; task start has a longer timeout to allow engine prepare hooks. The backend does not expose the IkaBot IPC key or saved game session material.

## API
FastAPI registers routes but rejects all state-changing game-task requests with HTTP 503 when no TaskController was injected. Explicitly enabled task mode requires bearer authorization, known enabled accounts, real engine background task discovery, explicit `confirmed=true`, and a UUID request ID.

## Session ownership and ledger
The controller acquires and retains a host-local AccountSessionCoordinator world/player lock, then verifies exactly one authenticated engine session before calling start. A private SQLite ledger records a unique (account_id, request_id), task name, SHA-256 config digest and outcome. It never stores credentials or task JSON. The ledger reserves `dispatching` before the IPC call. Uncertain outcomes are `unconfirmed`, are not retried with that ID, and block future requests until deliberate operator acknowledgment after inspecting game and engine state. Normal duplicate same-ID submissions return the original receipt without a second game action.

Host-local locks are not sufficient for distributed ownership or production fault tolerance. Engine-managed tasks may outlive a backend restart; the backend will never automatically replay a task. A supervised worker and game-state reconciliation flow are future work.

## Desktop
The native Fluent Tasks page is disabled for backends reporting `structured_engine_dispatch=false`; when enabled, it displays background tasks, accepts JSON parameters, requires a checkbox and a confirmation dialog, and generates one UUID per launch. Managed-task stop and manual reconciliation also require user confirmation and use account-scoped API routes. All requests run in QThread workers; errors are sanitized.

## Verification
Test only a synthetic socket/server, fake game sessions, mock child processes, SQLite files in temporary directories, and headless Qt. Assert no Gameforge networking, no second login, no arbitrary PID kill, and no raw secrets in logs, exceptions or task persistence.
