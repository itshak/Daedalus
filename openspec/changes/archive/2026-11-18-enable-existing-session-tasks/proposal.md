# Enable explicit built-in task control for existing game sessions

## Why

The upstream JSON CLI and the read-only IPC bridge are integrated, but an
operator cannot yet initiate or stop IkaBot background tasks from the native Mac
desktop. We can safely connect this capability to the **existing authenticated
engine session** before implementing browser-assisted session renewal.

## What changes

- Add distinct existing-only IPC actions to start, list and stop background
  tasks without `Session.from_saved` or any new Gameforge login.
- Restrict dispatch to packaged IkaBot `@task` modules and validated JSON
  configurations; exclude arbitrary custom Python modules and interactive
  configurator-only operations.
- Scope task stop to `multiprocessing.Process` handles launched through this
  specific controller and validate world/player identity.
- Require UUID4 idempotency keys for all starts to avoid duplicate task
  execution when an operator repeats a request.
- Add a separate task IPC client with explicit methods. Preserve the existing
  read-only IPC client action allowlist.
- Gate all HTTP mutations behind opt-in `daedalus serve --enable-task-control`
  in addition to existing bearer authentication and loopback binding.
- Add a native Fluent **Tasks** page with account/task selection, JSON
  configuration, confirmation before launch, status, and stop controls.
- Test with synthetic sockets, fake processes, mocked engine sessions and
  headless native Qt; no real game calls.

## Capabilities

### Modified capabilities

- `engine-integration`: existing-session-only built-in task dispatch, status
  and tracked-process stop.
- `controller-api`: explicitly enabled, account-scoped mutations with bearer
  authorization.
- `desktop-client`: operator-confirmed task start/stop and managed task status.

## Non-goals

No game login automation, CAPTCHA bypass, account session restoration, arbitrary
custom modules, distributed ownership, production cutover, durable task
reconciliation or full task-specific configuration forms.

## Impact

Users can test task control against a separately authenticated compatible
IkaBot worker. The default backend remains strictly read-only.
