## ADDED Requirements

### Requirement: Safe account metadata mutation while idle
The backend SHALL allow validated metadata changes only while no account session lease is active and SHALL never interpret account config as credentials.

#### Scenario: Active account owner holds local lease
- **GIVEN** an account has an active controller ownership lease
- **WHEN** the user attempts to replace account metadata
- **THEN** the change is refused and both disk configuration and active ownership remain unchanged

#### Scenario: User supplies authentication material
- **WHEN** an update includes an email, token, password or cookie field
- **THEN** validation fails before any file write or game login
