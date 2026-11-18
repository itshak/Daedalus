# Safe cookie-only restoration probe for existing IkaBot accounts

## Why
IkaBot's experimental `Session.from_saved` can fall back to a Gameforge lobby loginLink when world cookies expire. That may rotate an existing interactive game session and compete with production bots. Daedalus needs a demonstrably non-login retry path before any supervised recovery can be attempted.

## What changes
- Extend Daedalus-vendored IkaBot saved-session restoration with an optional `cookies_only=True` mode. The default public CLI path is unchanged.
- Cookie-only mode selects one explicit player/world, validates only previously saved per-world cookies via a read-only world GET, and refuses lobby access, blackbox creation and loginLink issuance.
- Store the user's local IkaBot saved-account email association only in the OS keyring, keyed to world/player identity; never write email, cookies or credentials to TOML, Git, logs or API.
- Add an explicit local `daedalus sessions` CLI for hidden-input binding, unbinding and manually confirmed cookie-only probe under the host-local account lease.
- Mock the network and persisted engine storage in offline tests; fail closed on wrong world/player, expired cookies, held leases and missing keyring data.

## Modified capabilities
- `account-sessions`: explicit, lease-bound cookie-only validation.
- `engine-integration`: no lobby login-link branch in safe mode.
- `security-boundaries`: no secret persistence in source, CLI args or API.

## Non-goals
No automatic worker login, browser/CAPTCHA orchestration, loginLink use, production cutover, task start or persistent session supervision. The probe closes the transient HTTP session and releases the lease after verification. Those remaining features stay open in `unify-authentication`.
