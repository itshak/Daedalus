## ADDED Requirements

### Requirement: Unified native worker recovery ownership

A native browser-cookie worker independently attested for an exact configured account SHALL be adopted by the same recovery supervisor and task-controller lease when automatic recovery infrastructure is configured. The saved-cookie retry loop SHALL NOT override a durable recovery event. Session health observation SHALL continue even when an account's unattended recovery policy is disabled.

#### Scenario: Native worker loses its game session

- **GIVEN** an independently verified native cookie worker and enabled automatic recovery
- **WHEN** corroborating existing-session checks confirm game-session loss
- **THEN** the recovery supervisor SHALL stop the old worker, publish a nonauthenticated state, and persist the existing recovery grace period before any new lobby login.

#### Scenario: Unattended recovery lacks a credential

- **GIVEN** a stopped native worker and terminal failed recovery epoch
- **WHEN** the owner explicitly initiates native browser sign-in
- **THEN** the stopped owner MAY release its lease for the verified replacement; only a fresh attested replacement SHALL resolve the failed epoch.
