# Validate and integrate real-account authentication recovery

## Why
The offline authentication implementation can be archived without falsely claiming that real Gameforge login, browser recovery, independent server-side player attestation, or remote GUI-to-running-worker integration have been exercised. The owner explicitly deferred real-account testing until the complete application is ready.

## What Changes
- Run a supervised isolated-account end-to-end login, CAPTCHA, cookie restoration, worker rebind and new-task flow when the owner authorizes testing.
- Verify the implemented native Mac browser recovery and account-bound encrypted handoff against an owner-authorized real account; never submit plaintext game cookies through API fields.
- Confirm the game server's actual player identity, not merely local restored engine metadata, before considering production cutover.
- Investigate compatibility failures and document deployment-specific recovery limits; preserve the running production IkaBot installation.

## Capabilities
### Modified Capabilities
- `account-sessions`: real-world validation and remaining remote UX integration.

## Completion boundary (2026-11-19)
All seven implementation and safe operational remediation tasks are complete
and independently validated; the remaining human-only real-account tests,
rebind/task trial, host reboot and explicit production approval have been
transferred as **unperformed** acceptance gates to
[issue #60](https://github.com/itshak/Daedalus/issues/60).
Archiving this change closes the implementation work, **not** the release gate.
Any owner-observed defect must receive a new focused OpenSpec proposal and tests.

## Non-goals
No unattended CAPTCHA solving, password extraction, secret upload to controller endpoints,
or claim that synthetic tests authorize real-game production cutover.
