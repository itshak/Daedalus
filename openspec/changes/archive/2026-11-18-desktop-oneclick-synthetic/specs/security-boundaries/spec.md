## ADDED Requirements

### Requirement: Embedded synthetic demo cannot access production accounts or persist its token

The one-click demo SHALL use only `create_app(demo_mode=True)`, SHALL bind only an OS-selected loopback IPv4 port, SHALL require an in-memory random bearer token even on local HTTP, and SHALL NOT read real account/IPC/credential stores or persist the demo token to a keyring, repository, URL or configuration file.

#### Scenario: Unauthorized request to local demo port
- **WHEN** a local request lacks the temporary bearer token
- **THEN** the demo SHALL reject protected account and warehouse routes

#### Scenario: Remember connection was enabled
- **WHEN** a user selects the demo action after enabling Remember connection
- **THEN** the UI SHALL explicitly disable persistence for the ephemeral demo token
