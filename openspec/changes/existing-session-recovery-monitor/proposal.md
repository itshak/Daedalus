# Opt-in existing authenticated session validation and assistance monitoring

## Why
A previously attached IkaBot process can lose or rotate its Gameforge session while the Daedalus task controller still believes it is authenticated. The existing human acknowledgment broker is not connected to a worker-side validation loop, and the desktop cannot proactively signal an expired session.

## What changes
- Extend only the Daedalus engine IPC overlay with a narrow `validate_session_existing` operation: a fixed read-only GET on the already-authenticated world's own base URL, returning only the exact world/player and boolean validity. Never restore or create a game session.
- Add an optional `--monitor-existing-sessions` server mode that requires both `--connect-existing-ipc` and `--enable-task-control`, a matching owner lease and trusted assistance broker. No default startup changes.
- Permit explicit operator-confirmed attachment to existing, uniquely identified authenticated sessions, holding the local lease and validating the world session before a task dispatch.
- On explicit monitoring, periodically detect expiration, pause task starts, issue a lease-bound nonsecret assistance ticket, honor human confirmation, then let the trusted server worker revalidate. Never replay tasks or reopen login automatically.
- Present a native Account-page monitoring consent action and notify the desktop of new waiting tickets without sending cookies or secrets.

## Modified capabilities
- `account-sessions`: controlled observation and guarded recovery.
- `controller-api`: opted-in monitoring, scoped consent, notification reads.
- `desktop-client`: safe native consent and notifications.
- `engine-integration`: read-only exact in-memory session validation.

## Non-goals
No creation of new Gameforge logins, Selenium/browser restoration, automatic CAPTCHA solution, durable game worker creation, distributed locking, automatic task replay or production cutover. Those remain active under `unify-authentication`.
