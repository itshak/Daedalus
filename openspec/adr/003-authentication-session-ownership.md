# ADR-003: Single-owner account sessions and assisted authentication

**Status:** Accepted (design baseline)

## Context
Independent browser and bot logins can displace a game's active session. The existing private GUI reliably assists login, captures browser cookies and pauses for manual CAPTCHA solving. Upstream public bot email/password login has been unreliable for this deployment.

## Decision
One account/world/player worker owns the active authenticated game session. The authentication coordinator first validates existing saved state, then uses supported automatic mechanisms, and escalates to a local interactive assistant for manual login/CAPTCHA. Credentials and authenticated session material never transit through public logs, Git, CI or untrusted networks. Session handoffs require validation and may not start a competing game session.

## Consequences
Authentication becomes a first-class UI state machine; no promise of unattended CAPTCHA resolution or universal session transfer. Worker lifecycle must reconcile tasks after successful recovery.
