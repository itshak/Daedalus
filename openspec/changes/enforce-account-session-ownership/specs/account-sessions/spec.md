## ADDED Requirements

### Requirement: Host-local exclusive account ownership
The controller SHALL claim a cross-process lease scoped to a normalized world/player identity before any eventual worker login and SHALL refuse a second simultaneous lease for that identity.

#### Scenario: Another process already owns the identity
- **GIVEN** a worker holds the account lease
- **WHEN** a second process tries to claim the same world/player using a different local account ID
- **THEN** it is refused without performing a game login

### Requirement: Assisted login must be validated
A session transitioning from human-assisted login MUST pass through a separate handoff validation state before it is marked authenticated.

#### Scenario: User finishes the browser challenge
- **GIVEN** the session is waiting for assisted login
- **WHEN** the user completes login or CAPTCHA
- **THEN** its state becomes validating_handoff, not authenticated, until the owner verifies the resulting session

### Requirement: Local locks do not guarantee global ownership
The project MUST document that host-local leases do not prevent the same account being used from another independent computer or service instance.

#### Scenario: Remote desktop controlling the server
- **GIVEN** a Mac desktop is connected to a server account
- **WHEN** the desktop requests a status update
- **THEN** the server remains the sole designated game worker; the desktop does not create another local account worker
