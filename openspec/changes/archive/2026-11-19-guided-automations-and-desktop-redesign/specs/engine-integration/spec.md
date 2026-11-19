## ADDED Requirements

### Requirement: Existing-session-only task readiness over private IPC

The engine SHALL expose an allowlisted, read-only task-prerequisite action for its exact authenticated world/player. The action SHALL only return nonsecret audited readiness states and SHALL never start or recover a login. Missing alert notification destinations SHALL be diagnosed before task process creation.

#### Scenario: Alert is missing a notification destination

- **WHEN** the existing account has neither a saved Telegram destination nor a Discord webhook for an alerting task
- **THEN** the IPC server returns `notifications_required`, and a launch for that task returns a typed pre-process rejection without creating a task child

#### Scenario: Other accounts cannot be queried

- **WHEN** the client requests a preflight for a different or ambiguous world/player
- **THEN** the engine rejects the request and does not open a new login or return session material
