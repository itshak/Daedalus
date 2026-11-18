## ADDED Requirements

### Requirement: Opt-in protected account metadata editor
The API MUST reject configuration mutations unless the operator explicitly enables editing mode, presents the bearer token, confirms the intended operation and supplies the current configuration revision.

#### Scenario: Concurrent metadata change
- **GIVEN** the metadata file has changed since the editor loaded its generation
- **WHEN** the stale editor submits its changes
- **THEN** the server returns a conflict and does not overwrite the newer config

#### Scenario: Disabled account editing mode
- **WHEN** a client attempts to PUT account metadata to a read-only or task-control server
- **THEN** no write is performed and the endpoint reports editing unavailable
