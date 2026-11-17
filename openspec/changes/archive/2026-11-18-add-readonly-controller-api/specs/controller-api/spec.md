## ADDED Requirements

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
