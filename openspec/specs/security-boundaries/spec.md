# Security Boundaries

## Purpose
Prevent a public repository or remote control surface from exposing account credentials and executable game-session privileges.

## Requirements

### Requirement: Offline unprivileged CI
Public pull-request jobs MUST have no Gameforge credentials, login activity, privileged publish permissions or deployment connectivity.

#### Scenario: External contribution
- **GIVEN** an untrusted pull request
- **WHEN** checks run
- **THEN** only synthetic test identities and read-only permissions are used

### Requirement: Protected local and remote interfaces
Session-owning IPC and authenticated backend APIs MUST be restricted to authorized clients and MUST NOT expose raw privileged proxies by default.

#### Scenario: Unauthorized remote client
- **WHEN** a client lacks authorization
- **THEN** it receives no account data and cannot start, stop, or modify tasks
