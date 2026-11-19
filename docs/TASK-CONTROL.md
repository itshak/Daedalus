# Daedalus controlled task execution — explicit opt-in

This is the first **functional task-control** milestone for the native desktop, authenticated API and existing IkaBot engine. It does **not** create authenticated Gameforge sessions, log in to the game, solve CAPTCHAs, or migrate your existing production bots. Tasks can only run through a compatible IkaBot process that is **already authenticated** on the backend host.

## Start a private test backend

Use a separate authorized test environment, **not the existing production checkout or live tmux workers**. Install Daedalus and its vendored engine, then start a patched IkaBot process with a working authenticated session. The engine and Daedalus backend must run as the same OS user on the same host.

```bash
python -m pip install -e ".[server,desktop]"
python -m pip install -e ./engine/ikabot
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --accounts-file ~/.config/daedalus/accounts.toml \
  --connect-existing-ipc --enable-task-control --host 127.0.0.1
```

The accounts file contains metadata only: account ID, world, player and label. The world/player identity must match exactly one authenticated IkaBot in-memory session.

**The task-control flag must be explicit.** Without it, every state-changing task HTTP endpoint returns 503, even if read-only IPC connectivity is enabled. The backend never binds to a public interface; remote Macs use HTTPS or a protected SSH/Tailscale loopback tunnel.

## Guided native automations update

The native UI now prioritizes a Home dashboard, friendly **Automations** filters,
prepopulated typed parameter widgets, and optional Advanced JSON instead of
requiring every user to hand-author task configuration. The read-only **Explore**
operation catalog links supported background tasks into the guided setup.
Automatic authenticated, read-only task preflight checks flag missing Telegram
or Discord notifications for alert tasks. Before dispatch reservation, known
missing notification prerequisites fail with an understandable error. A typed
engine rejection that proves no process started becomes `rejected`, whereas
an ambiguous lost IPC response remains `unconfirmed`, blocking replay.

Existing task request ledgers are **not automatically cleared**. The owner must
confirm the game and engine state and explicitly reconcile prior unconfirmed
requests. No notification key or webhook is accepted in general task arguments.
See [guided Mac quick start](GUI-QUICKSTART.md) for normal operations and the
direct HTTPS and Keychain auto-reconnect flow. The old SSH fallback is optional. Only user-approved starts have game side
effects.

## Native Fluent GUI task control

Launch `daedalus-desktop` and connect to the backend. The **Tasks** view lists registered engine background tasks; other menu actions remain in the read-only Operations inventory. Select an enabled account, choose a task, enter a JSON configuration with the parameters expected by that IkaBot task, check the authorization box, and confirm the separate start dialog.

The GUI generates a unique idempotency request ID per intentional launch. After starting, **Refresh tasks** reads engine-managed child-process status and the backend's durable request history. **Stop selected task** only targets a child launched through this Daedalus-specific IPC interface. It never kills an arbitrary OS PID.

The Tasks page now derives typed parameter controls from public engine source signatures for every registered background task. Use Build JSON from parameters to review the resulting configuration before confirming. Complex or unknown parameter types retain a JSON value field and the advanced JSON editor; the engine remains responsible for checking all game-specific values.

## Safety and restart behavior

- **Single-owner local lease:** Daedalus acquires an account/world/player host-local lock before a task launch and only attaches if exactly one corresponding in-memory IkaBot session exists
- **No second login:** `start_task_existing` refuses missing/ambiguous sessions without calling `Session.from_saved`
- **Backend authorization:** all task endpoints require the same strong Daedalus bearer token as account snapshots
- **Explicit user confirmation:** the GUI requires a checkbox and a confirmation dialog; the API requires `confirmed: true`
- **Idempotency and durable metadata:** the controller forwards its request UUID to the engine for a second independent replay check; SQLite stores only account ID, request ID, task name, configuration *hash*, engine-managed task ID, PID and status. It does **not** store task arguments, cookies, credentials or browser sessions
- **Conservative unknown outcome:** if IPC fails during launch, the request becomes `unconfirmed` and is never automatically replayed. New requests for that account are blocked until an operator checks engine and game state and explicitly acknowledges the uncertain request
- **Task-specific stop:** only in-memory child processes launched and registered by this IkaBot IPC owner can be stopped; unrelated tasks are never selected by PID
- **No automatic task relaunch:** restarting the controller or a browser never causes any game operation to replay

The task ledger defaults to `~/.local/state/daedalus/task-requests.sqlite3` (or user-local equivalent). You may override it with `--task-ledger`; it must remain private and outside the Git checkout.

Host-local locks are **not distributed** across servers or users. If the independent engine process remains running after a Daedalus backend shutdown, its existing tasks may continue; reconnect and reconcile their statuses before starting more tasks. A future production supervisor and restart-safe account reconciliation mechanism are still needed.

## API

The authenticated, opt-in routes are:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/v1/accounts/{id}/tasks` | Engine-managed tasks and durable nonsecret request history |
| POST | `/api/v1/accounts/{id}/tasks` | Start one validated task in an existing authenticated session |
| POST | `/api/v1/accounts/{id}/tasks/{task_id}/stop` | Stop a tracked engine-managed child |
| POST | `/api/v1/accounts/{id}/tasks/requests/{request_id}/acknowledge` | Explicitly mark an uncertain request manually reconciled |

Example (with an existing, authorized test backend):

```bash
REQUEST_ID="$(python -c 'import uuid; print(uuid.uuid4())')"
curl -sS --fail --request POST http://127.0.0.1:8765/api/v1/accounts/alpha/tasks \
  -H "Authorization: Bearer ${DAEDALUS_API_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"task\":\"alertAttacks\",\"config\":{\"minutes\":20},\"request_id\":\"${REQUEST_ID}\",\"confirmed\":true}"
```

**Never retry with a new request ID after a timeout without first checking status.** Reusing the original ID is safe and returns its recorded status. The engine itself validates the module's expected arguments before launching.

## Tests and current non-goals

All CI tests use synthetic local IPC sockets, mock game sessions, dummy child processes, and temporary SQLite files. They never open Gameforge endpoints or use real accounts.

Production-grade account lifecycle, browser-assisted login recovery, task-specific UI configuration forms, end-to-end real game integration testing, supervisor-based restarts, and automated idempotent game-state reconciliation remain active OpenSpec work. This milestone makes the cross-component task control operational for **explicitly provisioned existing sessions**, not automatically production-ready.
