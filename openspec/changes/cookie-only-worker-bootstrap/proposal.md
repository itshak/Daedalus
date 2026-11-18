# Explicit saved-cookie worker bootstrap for local Daedalus control

## Why
Daedalus can operate a compatible existing authenticated IkaBot IPC process but cannot start its own. The previously shipped saved-cookie probe validates a real world session and closes it immediately. A carefully scoped next step is to retain such a verified cookie-only session under its host-local account lease, without invoking a new Gameforge lobby login or browser authentication.

## What changes
- Add a separate, explicitly confirmed serve opt-in for ONE configured account, using only OS-keyring-referenced existing IkaBot world cookies and exact world/player identity verification.
- Start a dedicated protected local engine IPC endpoint only when no other IkaBot IPC owner exists.
- Share that exact in-process account-owner lease with the optional existing task controller so normal confirmed built-in task controls can act without a competing lease or second login.
- Keep credentials out of API/CLI/metadata/config and release IPC/session/lease on shutdown; test synthetic recovery and failure behavior.

## Modified capabilities
- `account-sessions`: persistent lease-bound cookie-only session lifetime.
- `engine-integration`: exclusive dedicated IPC for an already verified saved world session.
- `controller-api`: explicit CLI opt-in and safe task-controller adoption.
- `security-boundaries`: protected local recovery inputs and failure cleanup.

## Non-goals
No Selenium browser login, Gameforge lobby loginLink, CAPTCHA handling, credentials transport, automatic task restoration, unattended worker restart, multi-account supervisor, or production migration. The worker is an operator-started **experimental** local bootstrap for a verified previously saved session only.
