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

### Requirement: Saved-session identifiers remain outside Git, TOML and API

The saved IkaBot email association SHALL exist only in a protected OS credential provider, using a key scoped to the current configured account/world/player. Probes SHALL never accept credentials from HTTP, expose saved cookies, persist secret material in project files or include engine exception strings in operator errors.

#### Scenario: Identity metadata changes
- **WHEN** an account changes world or player
- **THEN** its previous saved-session keyring association SHALL NOT be reused for the new identity

#### Scenario: No OS credential store is available
- **WHEN** an operator requests binding or probing with no working keyring
- **THEN** the command SHALL fail safely instead of writing plain-text fallback credentials

### Requirement: Manually imported session cookies never traverse public APIs or project files

The CLI SHALL prompt for a world cookie only in an interactive echo-disabled local terminal with separate explicit network consent, and SHALL keep it out of command arguments, environment variables, logs, TOML and HTTP API. Only a verified cookie MAY be stored through a protected OS credential provider, using an account/world/player-specific key.

#### Scenario: No terminal or OS credential provider
- **WHEN** a user attempts to bind a world cookie without a TTY or protected keyring
- **THEN** Daedalus SHALL refuse the handoff instead of printing or writing the secret

#### Scenario: User changes configured world/player
- **WHEN** the account identity changes
- **THEN** the previously imported world cookie SHALL not be reused or disclosed to the changed identity

#### Scenario: Failed cookie re-import
- **WHEN** a newly supplied cookie cannot validate the world/player
- **THEN** the previous verified cookie SHALL remain unchanged in protected storage
