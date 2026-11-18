# Add secure optional desktop connection preferences and manual reconnect

## Why
The desktop forgets remote connection addresses after every launch and cannot reconnect with the current token after a transient backend outage without prompting again. Users should opt in to durable connection preferences while keeping bearer credentials out of normal configuration files and logs.

## What changes
- Add an explicitly enabled connection preference with a validated URL in owner-private local settings and its bearer token in the OS keyring only.
- Add native reconnect and forget-saved-connection controls; reconnect never starts an account login or retries a game mutation.
- Keep credentials in memory by default, support a graceful no-keyring fallback and preserve localhost-only HTTP restrictions.
- Add offline tests for file permissions, invalid configuration, keyring failure, masked UI and reconnect requests.

## Modified capabilities
- `desktop-client`: secure persistent connection preferences and reconnect UI
- `security-boundaries`: credentials may be stored only by an explicitly selected OS keychain provider

## Non-goals
No password-based Gameforge login, automatic task resumption, background reconnect loops or migration of legacy private settings.
