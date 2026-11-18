# Manual login assistance — trusted-worker acknowledgment protocol

This is a **protocol foundation**, not a working Gameforge/Selenium login
assistant. It supports a nonsecret pending assistance request that an
authoritative Daedalus worker could publish in a later integration. There is
currently no production game-worker adapter that automatically creates these
requests or validates browser handoff. No user should migrate production
sessions expecting this feature to restore them.

## Why two steps?

A human clicking "I finished the manual step" must **not** mark a game
session authenticated. Only the same trusted engine worker holding the
account/world/player lease can validate a real session. This protects both
against stale browser state and against duplicate task execution.

1. A trusted in-process worker obtains its `OwnedAccountSession` lease and
   requests assistance using one fixed nonsecret reason.
2. A random, short-lived, one-use UUID ticket becomes available to a properly
   configured API instance. No browser cookie, password, session token, email
   or Gameforge identifier is embedded in the ticket.
3. In the native **Accounts** page, select the account and click **Check
   login assistance**. The client shows only the reason and ticket state.
4. If the human actually finished the manual step in an independently trusted
   browser, click **Confirm manual step complete** and affirm the separate
   confirmation. This changes the state to `operator_ready`, **not**
   `authenticated`.
5. The same trusted worker, if later integrated with real session validation,
   calls `begin_validation` and `complete_validation(valid=...)`. Only that
   final internal call may advance the owner to authenticated. Failure
   requires a fresh ticket. Expiry pauses the owner but keeps the lease held.

The API's optional broker is **disabled by default**, and cannot be activated
by the public HTTP request. Integrators must inject an in-process
`AssistanceBroker` bound to the same trusted `AccountSessionCoordinator`.
No CLI flag is provided until an actual safe worker integration exists.

## API contract

For an authorized client:

- `GET /api/v1/accounts/{account_id}/auth-assistance` returns
  `enabled`, `account_id` and either no ticket or only
  `ticket_id`, `reason`, `state`.
- `POST /api/v1/accounts/{account_id}/auth-assistance/{ticket_id}/approve`
  requires exactly `{"confirmed": true}`, bearer auth, the currently
  waiting ticket for that exact account, and an unexpired, owned lease.

The read endpoint reports `enabled: false` when the broker is not connected,
so the native client can degrade gracefully. An attempted approval then fails
without any game network interaction. The API never accepts credential fields,
session data or "authenticated" transitions. The desktop token remains in
memory unless separately opted into OS keyring preferences.

The ticket broker is intentionally in-memory and non-durable. Following a
restart, the worker must reconcile the game session before creating another
request. No automatic replay or authentication is performed.

## Test and security boundaries

Run `python -m pytest tests/test_auth_assistance.py tests/test_client.py
tests/test_desktop.py`, Ruff and strict OpenSpec. Tests create synthetic
identities, fake worker leases, mock HTTP responses and Qt dialogs only.
They cover expiry, replay, cross-account isolation, invalid confirmation,
failed worker verification and the rule that the UI cannot claim authentication.
No production credentials, real browser data or Gameforge network connection
is used.

**Still required for production:** secure browser restoration or remote
handoff, manual CAPTCHA assistance orchestration, actual session validation,
worker supervision/recovery and safe task resumption. See the active
`unify-authentication` OpenSpec proposal.
