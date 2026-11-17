# Tasks

## Ownership
- [x] Add cross-platform per-identity account leases using a private state path.
- [x] Validate duplicate account identities, disabled accounts and double acquisition.
- [x] Add a test that uses another Python process to verify lock enforcement.

## Authentication states
- [x] Implement the read-only coordination lifecycle and allowed recovery transitions.
- [x] Require an explicit handoff validation state before successful assisted login.
- [x] Do not connect any Gameforge login or network operation.

## API and documentation
- [x] Surface nonsecret session phases through authenticated account endpoints.
- [x] Preserve read-only API and avoid premature task-dispatch permissions.
- [x] Document host-local, single-backend restrictions and safe worker shutdown ownership.

## Verification
- [x] Run Daedalus tests, OpenSpec validation, Ruff and tracked-file guard.
- [x] Review GitHub CI across supported operating systems and Python versions.
- [x] Merge only after clean CI; real worker connection is a separate change.
