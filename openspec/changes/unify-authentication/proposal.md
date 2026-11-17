# Unified authentication with human assistance

## Why
The upstream public bot's email/password login has been unreliable in this deployment. The local GUI's Selenium flow can restore sessions, attempt login, save cookies, open a visible fallback and pause for manual CAPTCHA. Independent game logins can invalidate running IkaBot sessions.

## What Changes
- Add a single account/world/player session owner, account locks and recovery state machine.
- Port audited browser restoration, automatic login attempts and human CAPTCHA waiting.
- Introduce secure Mac-to-server login handoff and validation.
- Reconcile task resumption and authentication errors without duplicate game logins.

## Capabilities
### Modified Capabilities
- `account-sessions`: coordinated interactive recovery.

## Non-goals
No CAPTCHA bypass, no assumption password login works, no publishing real session material.

## Impact
Fewer manual server interventions and no routine competition between GUI and engine. See ADR-003.
