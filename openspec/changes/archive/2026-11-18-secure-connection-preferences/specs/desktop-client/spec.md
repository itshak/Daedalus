## ADDED Requirements

### Requirement: Opt-in secure desktop connection persistence
The desktop MUST store a bearer token persistently only upon user opt-in and through an operating-system credential provider; it MUST NOT store bearer tokens in ordinary settings or log them.

#### Scenario: User remembers backend connection
- **GIVEN** a protected backend URL and valid token
- **WHEN** the operator selects Remember connection and connects successfully
- **THEN** only its validated URL is written in owner-private settings and the token is stored in the OS keyring

#### Scenario: Credential provider missing
- **GIVEN** the operating system does not expose a keyring backend
- **WHEN** the user requests persistent authentication
- **THEN** the desktop warns without writing a plain-text token or blocking ordinary in-memory connection

### Requirement: User-directed reconnect and forget
The desktop SHALL expose an explicit reconnect action for an in-memory or saved backend identity and a way to forget saved credentials without automatically replaying tasks.

#### Scenario: Backend restarts
- **WHEN** the user requests Reconnect after a transient API failure
- **THEN** only health, account metadata and capability discovery are attempted; game tasks are not resumed or retried

#### Scenario: User forgets preferences
- **WHEN** the operator clicks Forget saved connection
- **THEN** the saved URL and matching keyring secret are deleted where available
