## ADDED Requirements

### Requirement: Supervised real-account authentication acceptance
Production cutover SHALL require a supervised real-account test confirming that the authoritative worker validates the actual server-side player identity and that a native Mac desktop can complete human browser recovery using a single-use encrypted handoff without plaintext session secrets in controller API fields.

#### Scenario: Owner authorizes supervised recovery
- **GIVEN** an isolated, explicitly authorized account and one authoritative worker host
- **WHEN** the owner performs a browser login or manual challenge and requests recovery
- **THEN** the worker SHALL validate the game-world session and independently attest the configured player before any new user-approved task is dispatched


#### Scenario: Passing offline tests cannot authorize production
- **GIVEN** synthetic browser, IPC, GUI and server-side identity regression tests pass
- **WHEN** no actual isolated Gameforge account has completed the owner-supervised recovery and task trial
- **THEN** the real-account acceptance change SHALL remain active and production cutover SHALL remain unauthorized

### Requirement: Nonsecret deployment preflight must not imply production acceptance

The host-side operator SHALL be able to inspect only local task-receipt status counts and protected-keyring file metadata to diagnose safe restart prerequisites, without reading credential values, game sessions or performing game network requests. The diagnostic SHALL distinguish absent, unsafe and unresolved ledger state and SHALL report any mere persistent keyring file as **unverified** pending a real reboot test. Passing these checks SHALL NOT set production approval.

#### Scenario: Outstanding task receipts block live cutover

- **GIVEN** an existing ledger containing a `dispatching` or `unconfirmed` request
- **WHEN** the operator runs the local deployment check
- **THEN** the check reports a blocked state and anonymous unresolved count without reading configuration payloads or changing the ledger

#### Scenario: Session-only keyring is not reboot proof

- **GIVEN** the server's keyring uses only an in-memory session collection
- **WHEN** the operator checks deployment readiness
- **THEN** the check warns that durability is absent or unverified and does not claim successful restart or production acceptance
