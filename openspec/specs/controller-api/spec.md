# Controller API

## Purpose
Provide a versioned, authenticated read-only service for local and remote desktop clients before enabling state-changing engine task dispatch.

## Requirements

### Requirement: Authenticated account and capability views
The controller SHALL expose account metadata and engine capability descriptions over versioned HTTP endpoints requiring bearer authentication.

#### Scenario: Unauthorized account enumeration
- **GIVEN** a running controller
- **WHEN** an unauthenticated client requests the account list
- **THEN** the server returns HTTP 401 without account details

### Requirement: Secure development binding
The initial controller CLI MUST bind only to the loopback interface and MUST require a cryptographically unpredictable API bearer token of at least 32 characters.

#### Scenario: Non-loopback bind requested
- **WHEN** an operator requests binding to a non-loopback address
- **THEN** startup fails with instructions to use a protected tunnel

### Requirement: No fabricated account or warehouse activity
Until an authenticated IkaBot worker is connected, the controller MUST report no active game sessions and SHALL return an explicit unavailable response for warehouse snapshots.

#### Scenario: Warehouse snapshot request without worker
- **GIVEN** an account is configured but no snapshot provider exists
- **WHEN** a client requests its warehouse data
- **THEN** HTTP 503 is returned, rather than empty or invented resource totals

### Requirement: Read-only entry point
The first API release MUST NOT offer game-login, background-task dispatch, or state-changing game operations.

#### Scenario: Status request
- **WHEN** an operator calls the API health endpoint
- **THEN** it reports read-only mode and zero connected workers without contacting Ikariam
