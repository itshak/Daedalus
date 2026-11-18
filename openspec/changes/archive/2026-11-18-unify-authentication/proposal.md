# Unified authentication with human assistance

## Why
The upstream public bot's email/password login has been unreliable in this deployment. The local GUI's Selenium flow can restore sessions, attempt login, save cookies, open a visible fallback and pause for manual CAPTCHA. Independent game logins can invalidate running IkaBot sessions.

## What Changes
- Add a single account/world/player session owner, account locks and recovery state machine.
- Implement opt-in ephemeral browser restoration and manual human CAPTCHA waiting; do not assume automatic password login works.
- Provide a protected authoritative-host remote-desktop fallback and verified OS-keyring cookie handoff without API cookie transport.
- Add idle-only verified dedicated-worker rebind and one-use, explicitly approved NEW task dispatch without replaying uncertain requests.

## Capabilities
### Modified Capabilities
- `account-sessions`: coordinated interactive recovery.

## Non-goals
No CAPTCHA bypass, no assumption password login works, no publishing real session material. Real-account validation, remote desktop UX integration and independently attested server-side player identity are explicitly deferred to `validate-live-authentication`.

## Impact
Fewer manual server interventions and no routine competition between GUI and engine. See ADR-003.
