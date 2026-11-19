# Persist protected Daedalus headless worker credentials

## Why
The running graphical Secret Service default collection was volatile, so an otherwise authenticated game worker could not restore its world cookie after a process/host restart. Headless Linux API deployments must not rely on an unlocked VNC/desktop session or silently persist plaintext fallback secrets.

## What Changes
- Add an opt-in headless AES-GCM secret store with an OS systemd machine-bound encrypted root credential, transient service-only key material, account-scoped associated authentication data, restrictive permissions, and fail-closed missing-key behavior.
- Provide a metadata-only release audit for encrypted storage and a separate real service-user decryption test that does not disclose secret values.
- Add synthetic cross-account, tamper, missing-key, permission and service-restart integration tests.
- Perform a controlled Monjo migration from its existing independently attested saved identity, reconcile the previously uncertain alert receipt with an audit and backup, and make daemon startup independent of VNC.

## Capabilities
### Modified Capabilities
- `security-boundaries`: secure daemon-only host credential storage.
- `account-sessions`: restore exact verified world cookies from reboot-persistent credentials.

## Non-goals
- No unattended CAPTCHA solving, new session creation, unapproved task replay, plaintext API cookie transfers, or whole-host reboot of other production bots.
- No claim that automated testing substitutes for owner-supervised real Mac Gameforge browser login, live game task acceptance or final production cutover.
