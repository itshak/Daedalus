# Validate and integrate real-account authentication recovery

## Why
The offline authentication implementation can be archived without falsely claiming that real Gameforge login, browser recovery, independent server-side player attestation, or remote GUI-to-running-worker integration have been exercised. The owner explicitly deferred real-account testing until the complete application is ready.

## What Changes
- Run a supervised isolated-account end-to-end login, CAPTCHA, cookie restoration, worker rebind and new-task flow when the owner authorizes testing.
- Connect the desktop's remote recovery UX to the supported authoritative-host workflow without transmitting cookies through the API.
- Confirm the game server's actual player identity, not merely local restored engine metadata, before considering production cutover.
- Investigate compatibility failures and document deployment-specific recovery limits; preserve the running production IkaBot installation.

## Capabilities
### Modified Capabilities
- `account-sessions`: real-world validation and remaining remote UX integration.

## Non-goals
No unattended CAPTCHA solving, password extraction, or secret upload to controller endpoints.
