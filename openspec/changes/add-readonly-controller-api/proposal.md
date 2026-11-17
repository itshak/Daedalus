# Add local multi-account metadata and authenticated read-only controller API

## Why
Daedalus needs a real local/remote communication contract before migrating the GUI, while ensuring account setup and reporting do not start competing game sessions.

## What Changes
- Add a strict local TOML account metadata format with synthetic examples and no password/cookie/token fields.
- Add a typed offline warehouse parser using the existing private GUI's verified span identifiers, preferring exact tooltip values.
- Add a snapshot adapter accepting an existing public IkaBot Session, rather than duplicating game HTTP requests.
- Add an authenticated, loopback-only versioned FastAPI service with health, accounts, capabilities and an injectable warehouse snapshot provider.
- Add the `daedalus accounts list` and `daedalus serve` commands.
- Add extensive synthetic-only tests and CI-ready installable server dependencies.

## Capabilities
### New Capabilities
- `controller-api`: authenticated read-only API and local binding requirements.

### Modified Capabilities
- `account-sessions`: local account metadata definitions without secrets.
- `warehouse-monitoring`: exact unsecured warehouse extraction without Selenium session duplication.

## Non-goals
No live game sessions, UI rewrite, production server migration, token import, task scheduling, CAPTCHA implementation or remote public port exposure.

## Impact
A real backend boundary and API contracts for the forthcoming PySide6 client migration. See ADR-001, ADR-003 and ADR-004.
