# Add authenticated native account metadata editing without game login

## Why
The desktop can list multiple accounts but cannot create, edit or disable their metadata without manually editing server TOML. This blocks practical setup for remote Mac users, especially when they need to connect an existing authenticated IkaBot worker by world/player identity.

## What changes
- Add a strictly opt-in metadata editing API on the loopback backend, requiring bearer authorization, explicit user confirmation and an optimistic configuration generation.
- Validate only ID, world, player, label and enabled fields. Atomically write owner-private TOML outside the repository, then update in-memory account metadata only while no controller account lease is active.
- Keep account editing mutually exclusive with active task dispatch mode until a supervised worker lifecycle exists.
- Add native account create/edit/delete/disable dialogs using the same client API on local and protected remote connections.
- Test cross-process configuration conflicts, reject secrets and symlinks, preserve account identity isolation and perform no game networking.

## Modified capabilities
- `account-sessions`: validated account metadata configuration mutation
- `controller-api`: opt-in authenticated account editing
- `desktop-client`: native account metadata editor

## Non-goals
No persistent Gameforge credentials, account login, changing an active task's owner, CAPTCHA handling or migrating the production installation.

## Impact
A usable metadata onboarding workflow for existing-session engine attachment, with explicit account editing mode rather than implicitly running game automation.
