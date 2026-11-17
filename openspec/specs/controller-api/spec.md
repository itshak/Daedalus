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

### Requirement: Versioned bearer-protected read-only API
Daedalus SHALL offer versioned HTTP endpoints for account metadata and engine capabilities, with access controlled by a minimum 32-character bearer token.

#### Scenario: Authorization denied
- **GIVEN** a read-only Daedalus server
- **WHEN** a client omits or submits an invalid bearer token
- **THEN** the account/capability resource is denied without exposing private data

### Requirement: Safe local binding
The initial server MUST listen on loopback only and MUST NOT start any game worker.

#### Scenario: Server started with public interface
- **WHEN** the operator specifies `--host 0.0.0.0`
- **THEN** startup fails before the HTTP server is opened

### Requirement: Explicit unavailable warehouse data
The API MUST return HTTP 503 when no authenticated snapshot provider is available.

#### Scenario: Account without a worker
- **GIVEN** a valid configured account and no game session
- **WHEN** its warehouses are requested
- **THEN** the server reports unavailable, not a zero-value or stale snapshot

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

### Requirement: Desktop bearer tokens use protected transport
The desktop SHALL refuse to send an API bearer token over plaintext HTTP to a non-loopback address.

#### Scenario: User enters remote HTTP URL
- **WHEN** the user enters `http://example.org` with an API token
- **THEN** the client refuses the connection before sending any request

### Requirement: Remote errors do not leak credentials
The desktop MUST sanitize connection and API errors and SHALL NOT print response bodies or bearer tokens in log or exception messages.

#### Scenario: Server includes a secret in an error body
- **GIVEN** a remote server responds with a private token in the body
- **WHEN** a request fails
- **THEN** the UI displays a generic status error without the token
