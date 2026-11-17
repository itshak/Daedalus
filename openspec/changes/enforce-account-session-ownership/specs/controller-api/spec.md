## ADDED Requirements

### Requirement: Read-only account session status
An authenticated client SHALL be able to query a configured account's nonsecret session state, and an unauthorized client SHALL receive no such state.

#### Scenario: Authentication assistance needed
- **GIVEN** a coordinator has marked an account as needs_assistance
- **WHEN** an authorized desktop client requests the account session endpoint
- **THEN** it receives needs_assistance without receiving credentials or session cookies

### Requirement: Session reads cannot start workers
The controller MUST NOT launch an engine worker, start a game login, or transition account state in response to a read-only status request.

#### Scenario: Account state is queried without a worker
- **WHEN** a client requests account status before any worker is connected
- **THEN** it receives not_connected and no game or IPC action is sent
