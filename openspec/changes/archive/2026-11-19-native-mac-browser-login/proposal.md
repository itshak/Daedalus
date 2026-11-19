# Implement native Mac browser authentication and encrypted worker handoff

## Why

The previous recovery flow required opening a browser and terminal on the Linux server. The macOS controller must allow human Gameforge sign-in without remote VNC/SSH and without starting a second game worker.

## What Changes

- Embed off-the-record Gameforge login in the native Mac GUI, leaving CAPTCHA/MFA/password entry to the user.
- Send only an encrypted, short-lived, single-use world-session handoff over the authenticated HTTPS control API, with exact account/world/player binding.
- Independently validate the game-world player on the authoritative worker before accepting the session, while retaining the existing owner lease, rejecting active or uncertain tasks, and never replaying operations.
- Add typed client endpoints, backend opt-in, protected keyring staging, tests, macOS browser packaging and documentation.
- Keep real live-account/browser/CAPTCHA/reboot acceptance in the separately active acceptance gate; archival of this completed implementation is not production authorization.

## Capabilities

### Modified Capabilities
- `account-sessions`: supervised client browser and worker handoff.
- `desktop-client`: native macOS browser login and package support.
- `security-boundaries`: encrypted-only account-bound session exchange.

## Non-goals

Automated CAPTCHA, extraction of credentials, plain-text cookie upload, unattended worker restart, automatic task replay, or unverified production rollout.
