# Account Sessions

## Purpose
Manage local and remote multi-account authentication without competing game logins.

## Requirements

### Requirement: Single active session owner
The backend MUST enforce at most one active game-session owner for an account/world/player identity.

#### Scenario: Duplicate launch
- **GIVEN** an account already has an active owner
- **WHEN** another worker requests that identity
- **THEN** the new worker is refused or routed to the existing owner without an independent login

### Requirement: Human-assisted recovery
The account manager SHALL support saved-session restoration, optional automatic login and interactive human assistance when authentication or CAPTCHA requires it.

#### Scenario: CAPTCHA encountered on remote worker
- **GIVEN** a remote account requires manual challenge completion
- **WHEN** the desktop client is connected
- **THEN** it offers a supervised interactive login path and resumes the owner only after successful validation

### Requirement: No assumption of password-only success
The backend MUST NOT mark password-only Gameforge login as operational until proven through independent tests.

#### Scenario: Password login fails
- **WHEN** password login fails
- **THEN** account tasks move into a recoverable authentication-required state rather than repeatedly creating conflicting game sessions

### Requirement: Local account metadata excludes authentication secrets
Daedalus SHALL support a local multi-account TOML configuration with stable IDs, world, player, label and enabled state, while rejecting passwords, cookies, tokens and unsupported fields.

#### Scenario: User accidentally configures a password
- **WHEN** an `accounts.toml` contains a password field
- **THEN** parsing fails with a message directing the user to protected credentials storage

### Requirement: Duplicate account sessions prevented at configuration time
The controller MUST reject duplicate account IDs and duplicate world/player identities.

#### Scenario: Duplicate world/player record
- **WHEN** two account definitions describe the same world/player identity
- **THEN** configuration validation fails before any game session begins

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

### Requirement: Task dispatch acquires account ownership before any game operation
The backend MUST acquire the local world/player lease and verify exactly one authenticated engine session before invoking any new game-task dispatch.

#### Scenario: Another backend process already holds the account
- **GIVEN** the account is leased by another Daedalus backend
- **WHEN** the controller attempts to launch a task
- **THEN** the request fails without creating a new game login or task

### Requirement: Safe account metadata mutation while idle
The backend SHALL allow validated metadata changes only while no account session lease is active and SHALL never interpret account config as credentials.

#### Scenario: Active account owner holds local lease
- **GIVEN** an account has an active controller ownership lease
- **WHEN** the user attempts to replace account metadata
- **THEN** the change is refused and both disk configuration and active ownership remain unchanged

#### Scenario: User supplies authentication material
- **WHEN** an update includes an email, token, password or cookie field
- **THEN** validation fails before any file write or game login
