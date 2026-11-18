## ADDED Requirements

### Requirement: Explicit synthetic demonstration backend

The controller SHALL provide a clearly marked, operator-opted-in synthetic demo with sample account identities, cities and warehouse resource reports. The demo SHALL keep the standard authenticated API transport and SHALL identify synthetic content in machine-readable responses.

#### Scenario: Synthetic warehouse view
- **WHEN** a bearer-authorized demo client requests warehouse resources
- **THEN** the controller SHALL return clearly synthetic account-specific sample values with zero distinct from unknown and MUST NOT contact a game session

#### Scenario: Default backend startup
- **WHEN** the controller starts without explicit demo opt-in
- **THEN** it SHALL NOT load synthetic accounts or claim to show genuine reports from unavailable game sessions
