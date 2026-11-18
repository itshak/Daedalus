# Design — opt-in native task controls

## Process owner

The authenticated IkaBot parent owns its game session. A Daedalus HTTP backend
with `--connect-existing-ipc --enable-task-control` is an explicit client of
that parent; it does not create or restore a game session. Each mutating IPC
request includes the verified account world/player and the local IPC authkey.

The IkaBot parent registers a managed process only after launching a built-in
`@task` child. It retains a live `multiprocessing.Process` reference.
Stopping a task uses only that exact registered handle and first terminates,
then optionally kills the same tracked child after a bounded wait; arbitrary
PIDs are not accepted. Managed tasks are not persisted across server restarts.

## Configuration and idempotency

Only packaged `ikabot.function.<name>` modules are allowed, not custom
module paths from user configuration. The upstream task signature validator
and optional prepare hook validate JSON fields. Account/session, task and JSON
config inputs are incorporated into a UUID4 idempotency record. Replaying the
same request ID with different parameters is rejected. At most 512 recent
idempotency records are retained per IPC server lifetime.

## Backend and native GUI

The standard controller always uses loopback binding and a bearer token. Its
task mutations are unavailable unless explicitly enabled at startup. A
separate ExistingTaskIPCClient provides only start/list/stop methods and never
widens the read-only bridge's public `request()` allowlist.

FastAPI validates configured/enabled accounts, the AST inventory's
background-task name, config size and UUID4 request IDs before IPC. Error
bodies never expose Gameforge session data. The native Fluent Tasks page
shows account and task selectors, JSON configuration, a confirmation dialog,
managed-process status, and a stop confirmation; HTTP runs off the GUI thread.

## Failure semantics

If the existing engine worker is unavailable, the API returns HTTP 503.
Malformed requests return HTTP 422 and disabled accounts return 409.
Multiple concurrent start requests serialize through the authenticated
engine's IPC server lock; UUID4 deduplication protects exact retries. A
parent restart can lose process handles and requires manual reconciliation.

## Tests

Use fake `multiprocessing.Process` objects and fake authenticated sessions,
synthetic loopback IPC servers, mock HTTP transport, FastAPI TestClient and
offscreen/Cocoa Qt smoke tests. No real child task or game login is started in CI.
