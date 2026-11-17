# Bootstrap the Daedalus public monorepo

## Why
The project needs a publicly auditable, secret-free foundation with OpenSpec conventions and offline CI before any source is migrated from existing local applications or production servers.

## What Changes
- Establish Daedalus identity, the `daedalus` Python distribution/import/CLI, GPL-3.0-only original source license, README, contribution constitution and local docs.
- Install standard OpenSpec folder layout, baseline capability specifications, ADRs and traceable upcoming change proposals.
- Provide an offline package smoke test, multi-OS Python tests and linting, OpenSpec validation, packaging builds, and protected security checks.
- Exclude all production credentials, user accounts, saved cookies, browser profiles, tokens and server configuration from git.

## Capabilities
### Modified Capabilities
- `project-foundation`: add reproducible and CI-safe bootstrapping requirements.

## Non-goals
No live Gameforge connections, account workers, migrated GUI, upstream engine code, deployed services or published PyPI package.

## Impact
The initial commit is safe to publish publicly and establishes testable entry points for later changes. See ADR-001 through ADR-005.
