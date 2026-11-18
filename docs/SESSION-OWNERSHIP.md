# Account session ownership — implementation baseline

Daedalus now contains a **host-local account lease** and an explicit authentication state machine. This is infrastructure for account workers. The separate opt-in task controller can start background task child processes **only within a compatible already-authenticated IkaBot engine session**. Neither component creates a new Gameforge login, captures a token, or solves a CAPTCHA.

## Why the lock is keyed by world and player

Two local account profiles with different IDs can still refer to the same in-game identity. The lock name is a SHA-256 digest of normalized `world + NUL + player`, rather than the Daedalus account ID. This avoids storing private account labels in the lock file name. The local metadata loader also rejects duplicates.

Leases use OS-backed `filelock` locks in `~/.local/state/daedalus/session-locks` (or the configured user state directory). The directory is created with restrictive permissions, and the file does not contain credentials or session material. The lock is held while a worker waits for a human to complete login/CAPTCHA.

**Important limitation:** This prevents duplicate owners on the **same host and state directory**. It does **not** coordinate two independent Daedalus backends on different machines or under different user/state directories. An account must be assigned to one authoritative backend. A Mac desktop connected to a remote server must remain a client, not start a second game worker.

## States

`validating_session` → `authenticated` on external validation, or → `needs_assistance` when login assistance is required.

`needs_assistance` → `assisted_login` → `validating_handoff` → `authenticated` on successful validation. An invalid handoff returns to `needs_assistance`. Other states include `paused` and `failed`. Releasing a lease closes the session.

These are **reported states**, not proof of actual login: an engine session validator will be added later. The state machine will not automatically authenticate, create an extra browser session, accept tokens, or launch game actions.

## API

Existing read-only endpoints remain bearer-protected. The server can optionally receive an in-process coordinator. `GET /api/v1/accounts` then reports its current nonsecret session states, and `GET /api/v1/accounts/{id}/session` returns one account's state. The unauthenticated health endpoint reports the count of entries marked `authenticated`. No HTTP route allows a client to transition state or start a worker.

A future worker adapter **MUST** acquire the lease before authentication, keep it for the entire game session (including a CAPTCHA wait and suspended task recovery), and release it only after the engine process has definitively stopped. Before remote execution is enabled, a single authoritative backend must be assigned to each account, with a restart/reconciliation policy.

## Test boundaries

Automated tests use only fake account identities, mock state transitions and OS locks. A test spawns a second interpreter to verify that an existing local lease blocks another process. No fixture contains real game credentials.
