# Tasks

## Local account metadata
- [x] Define TOML schema and synthetic example with no secrets.
- [x] Validate ids, worlds, duplicate identities, unsupported fields and safe default path.
- [x] Add CLI command to list configuration without session login.

## Warehouse data
- [x] Parse existing GUI's unsecured and capacity identifiers from synthetic HTML.
- [x] Prefer exact tooltip values, normalize crystal/glass, distinguish null from zero.
- [x] Use an injected existing IkaBot session for a read-only warehouse request.

## Read-only controller
- [x] Add optional FastAPI dependencies, loopback-only server launcher and bearer authorization.
- [x] Add versioned read-only routes for health, accounts, capabilities and warehouse snapshots.
- [x] Do not report fake warehouse data when no authenticated snapshot provider exists.

## Verification
- [x] Run new/old tests, lint, OpenSpec validation and source-security guard locally.
- [x] Confirm CI passes on GitHub after pushing.
- [x] Review security/provenance before merging.
