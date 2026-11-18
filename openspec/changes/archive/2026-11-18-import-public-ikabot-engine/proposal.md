# Integrate the upstream public IkaBot engine

## Why
The public bot already implements game operations. Daedalus should orchestrate those rather than reproduce game protocol code. The production installation has custom authentication changes, and upstream has proposed CLI/IPC interfaces.

## What Changes
- Import pristine upstream IkaBot with MIT attribution and a reproducible upstream version.
- Isolate the engine namespace from the new Daedalus desktop and server package.
- Review and test CLI/IPC changes from upstream PRs #499, #502 and #510.
- Port only individually reviewed nonsecret local authentication changes.
- Provide typed task discovery and lifecycle interface to the backend.

## Capabilities
### Modified Capabilities
- `engine-integration`: auditable upstream import and task adapter.

## Non-goals
No production server migration, live account logins, production credentials, or rewriting game operations.

## Impact
One canonical game engine. See ADR-001, ADR-002 and ADR-003.

## Source reconciliation completion (2026-11-18)
The public revision and PR #499 snapshots were rechecked. A source-only review
of the six locally modified production engine Python files identified two safe
adaptations (bounded remote token-API failure handling and detached prompt
fail-fast), which were reimplemented with isolated tests. Unsafe direct
environment credential bootstrapping and unattended task launch were rejected.
The file-by-file provenance, decisions and patch fingerprint are recorded in
`docs/ENGINE-AUTH-RECONCILIATION.md`; no account runtime files were read or
imported. This closes **engine source reconciliation**, not the separate live
authentication readiness proposal.
