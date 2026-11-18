# Safe manual authentication acknowledgment between trusted worker and desktop

## Why
The session ownership state machine reports assistance needs but lacks an account-scoped acknowledgment contract. The desktop must never mistake human completion for a verified game session.

## What changes
- Add a host-local, in-process, lease-bound, credential-free assistance ticket broker with fixed nonsecret reasons and expiry.
- Add an optional bearer-authenticated read and one-use confirmation API.
- Add native Accounts-page status/confirmation buttons with explicit user consent.
- Reserve verification and authenticated state transitions for a trusted worker holding the lease.

## Modified capabilities
- `account-sessions`: lease-bound assistance tickets.
- `controller-api`: scoped read/ack endpoints.
- `desktop-client`: consentful manual help status.

## Non-goals
No Selenium/browser login, cookie/token handoff, CAPTCHA bypass, worker startup, task resume, credential transfer, distributed coordination or production cutover. These remain open in `unify-authentication`.

## Impact
Safe offline-testable assistance protocol foundation. No public API can set an account to authenticated.
