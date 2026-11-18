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

### Requirement: No plaintext persistent controller tokens
Daedalus SHALL NOT write API bearer tokens to ordinary JSON, TOML, log, or runtime preference files.

#### Scenario: Persistent credential setup
- **GIVEN** the user opts in to storing a backend connection
- **WHEN** the secure credential provider cannot write a secret
- **THEN** no insecure fallback file containing the bearer credential is created

### Requirement: Demo mode cannot attach real accounts or execute automation

An explicit synthetic demo SHALL reject real account paths, IPC descriptors, injected snapshot providers, existing authenticated sessions, task execution, account editing and game login. It SHALL retain bearer authorization for all account/report data and loopback-only host binding.

#### Scenario: Demo is combined with production flags
- **WHEN** an operator requests demo mode with real account, IPC, task control or editing options
- **THEN** startup SHALL fail before opening any game client or account file

#### Scenario: Client attempts to modify game state in demo
- **WHEN** a client attempts to start a game task, attach an existing IkaBot session or edit an account
- **THEN** the controller SHALL reject it without network or game side effects
