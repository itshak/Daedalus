## ADDED Requirements

### Requirement: Explicit saved-cookie worker holds one verified identity lease
Daedalus SHALL start a local cookie-only worker only with explicit operator confirmation, a configured enabled account and a protected OS keyring saved-account binding. It SHALL hold the host-local canonical world/player lease for the lifetime of the authenticated session and refuse competing owners.

#### Scenario: Session validates an exact world/player
- **GIVEN** saved cookies resolve to an authenticated engine session matching the configured account
- **WHEN** the operator explicitly starts that saved account worker
- **THEN** the authoritative account lease remains held while its dedicated IPC is running

#### Scenario: Invalid or expired saved cookies
- **WHEN** restored session verification fails
- **THEN** no authenticated worker or IPC starts and the lease is released without attempting a fresh lobby login
