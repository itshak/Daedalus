## ADDED Requirements

### Requirement: Cookie-only worker bootstrap is a separate explicit opt-in
The `serve` command SHALL require an account metadata file, an existing-session IPC connector, an exact saved account ID and an explicit read-only network confirmation before starting any saved-cookie worker. The default API MUST NOT bootstrap an authenticated worker.

#### Scenario: Missing confirmation
- **WHEN** the operator omits the saved-worker network confirmation
- **THEN** CLI setup fails before accessing a saved session

### Requirement: Task controls adopt only the exact authenticated worker lease
An opted-in TaskController SHALL accept the same in-process authoritative authenticated account lease and protected identity-validated IPC endpoint. It MUST NOT acquire a second lease, replay prior tasks or accept a foreign owner's lease.

#### Scenario: Local saved worker has authenticated
- **GIVEN** task control was independently enabled
- **WHEN** the worker holds a verified account lease and IPC identity validation succeeds
- **THEN** task control may use that existing lease for separately confirmed built-in task operations
