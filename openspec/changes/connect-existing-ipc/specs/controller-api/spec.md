## ADDED Requirements

### Requirement: Explicit read-only attachment to an existing engine
The backend SHALL expose optional bearer-protected GET endpoints for already-connected IkaBot account identities and their city lists only when the operator explicitly enables the existing-session IPC bridge.

#### Scenario: The backend starts with default options
- **GIVEN** the controller has a configured account but no explicit IPC attachment
- **WHEN** a desktop client requests connected engine sessions or cities
- **THEN** it receives HTTP 503 and the backend does not start a game session

### Requirement: Only configured accounts are revealed
The controller MUST filter IPC session identities to the enabled accounts in its own metadata configuration.

#### Scenario: An engine process contains other game accounts
- **GIVEN** the IPC worker lists unrelated player identities
- **WHEN** an authorized desktop requests connected accounts
- **THEN** only configured account IDs are returned

### Requirement: Controller IPC access is constrained to local read operations
The IPC transport MUST restrict calls to a fixed read-action allowlist, require a protected loopback discovery descriptor, and reject malformed credentials, stale owner processes and oversized replies.

#### Scenario: A client attempts task launch using the read bridge
- **WHEN** a requester invokes start_task using the read-only IPC connector
- **THEN** the connector refuses the action before opening a network connection
