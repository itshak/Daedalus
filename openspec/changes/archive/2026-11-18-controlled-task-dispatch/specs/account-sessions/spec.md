## ADDED Requirements

### Requirement: Task dispatch acquires account ownership before any game operation
The backend MUST acquire the local world/player lease and verify exactly one authenticated engine session before invoking any new game-task dispatch.

#### Scenario: Another backend process already holds the account
- **GIVEN** the account is leased by another Daedalus backend
- **WHEN** the controller attempts to launch a task
- **THEN** the request fails without creating a new game login or task
