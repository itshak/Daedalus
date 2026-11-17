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
