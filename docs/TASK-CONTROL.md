# Opt-in existing-session IkaBot task control

Daedalus can manage built-in IkaBot background tasks **only through an explicitly
enabled backend, using an existing authenticated in-memory engine session**.
It does not create a Gameforge login, restore a saved account session, or solve
CAPTCHAs. This is an operator-initiated capability, not an auto-start service.

## Required setup

1. Run a **separate test environment** with the Daedalus-vendored IkaBot engine.
   Log in using the engine's normal mechanism and confirm the account already
   has an authenticated, in-memory session. Do not replace your existing
   production tmux bots or copy their saved sessions to test the new code.
2. Configure only the nonsecret account identity in
   `~/.config/daedalus/accounts.toml` as described in
   [EXISTING-IPC.md](EXISTING-IPC.md).
3. Start the backend **deliberately opting into mutations**:

   ```bash
   python -m pip install -e ".[server,client]"
   export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   daedalus serve --connect-existing-ipc --enable-task-control \
     --accounts-file ~/.config/daedalus/accounts.toml
   ```

4. In the native Mac app's **Connection** page, connect to the local backend or
   a protected SSH loopback tunnel/HTTPS endpoint. Enter its bearer token.
   Open **Tasks**, select an account and built-in background task, enter a JSON
   configuration object and review the confirmation before starting the task.
   Use **Refresh tasks** to inspect the tasks managed by this controller and
   **Stop selected task** to stop a running managed child process.

The default `daedalus serve` command is read-only. A separate
`--enable-task-control` flag is required, and it is rejected without
`--connect-existing-ipc`. No HTTP endpoint opens a game login.

## Task configuration and coverage

Daedalus displays the AST-derived built-in background task inventory. Parameters
are passed as JSON dictionaries to upstream IkaBot's task validation and optional
`prepare` routine. An empty `{}` is accepted **only if the particular task
has no required parameters**; incomplete or invalid values fail without a
background task being started.

This first interface is a **generic JSON editor**, not 23 individually tuned
forms. Only packaged `ikabot.function.*` built-in modules are permitted; saved
custom modules, arbitrary Python commands and legacy interactive menu-only
functions are not executable through the new API.

The engine's task-start response contains the task PID, task name and nonsecret
account identity. It excludes saved Gameforge email/session information.

## Session and process ownership

- The IkaBot IPC server owns the already-authenticated game session. Daedalus
  **attaches to this engine**, not another login.
- Every start is scoped to world/player, validates a random UUID4 idempotency
  key, and refuses an ambiguous or missing in-memory session. Repeating the
  exact start request with the same UUID4 key returns its previous result.
- The server tracks child `multiprocessing.Process` objects started by this
  Daedalus IPC interface. **Only those exact objects** can be stopped; an
  arbitrary PID cannot be killed through the controller. Ordinary upstream
  IkaBot tasks are not affected.
- The engine's manager registry is in memory. If its parent process exits,
  earlier child processes may become unmanageable through this interface.
  Durable recovery/reattachment is future work; review existing game worker
  processes before restarting the engine.
- Daedalus's host-local account leases apply to workers it owns. They do
  not establish global single-session ownership between different hosts or
  independently authenticated external processes.

## Versioned API

All endpoints below require the controller's API bearer token:

| Method | Endpoint | Meaning |
| --- | --- | --- |
| GET | `/api/v1/task-control` | Whether explicit task execution is enabled |
| GET | `/api/v1/accounts/{id}/tasks` | Only tasks started through the Daedalus IPC interface |
| POST | `/api/v1/accounts/{id}/tasks` | Start a built-in task with `task`, `config` and UUID4 `request_id` |
| DELETE | `/api/v1/accounts/{id}/tasks/{pid}` | Stop one exact tracked task PID |

Example body (illustrative only; task-specific parameters may differ):

```json
{
  "task": "alertAttacks",
  "config": {"minutes": 10},
  "request_id": "12345678-1234-4123-8123-123456789abc"
}
```

No real credentials or automation targets are bundled in the repository.

## What this milestone does not yet complete

The Selenium-based Gameforge login assistant from the original private app,
browser CAPTCHA wait and cookie/session handoff, durable task persistence,
schedule/retry policies, specialized per-task forms, multi-host coordination,
and full prior UI parity remain future changes.

All CI and unit tests run against synthetic local IPC sockets, mocked
IkaBot sessions and fake child processes. They never contact Gameforge.
