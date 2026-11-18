## ADDED Requirements

### Requirement: Scoped authenticated manual assistance

The API SHALL require bearer authorization for account-scoped assistance status and explicit one-use confirmation. It MUST NOT allow public clients to create tickets, start game login, provide authentication material or mark an engine session authenticated.

#### Scenario: Stale, duplicate or cross-account ticket
- **WHEN** an operator submits a stale, duplicate or different account's ticket
- **THEN** the API SHALL refuse approval without changing authentication state

#### Scenario: Disabled broker
- **WHEN** a backend has no trusted assistance broker
- **THEN** confirmation SHALL be unavailable and no browser/game operation SHALL occur
