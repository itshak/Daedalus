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

The expert CLI SHALL prompt for a world cookie only in an interactive echo-disabled **host-local** terminal with separate explicit network consent; it SHALL keep plaintext credentials out of command arguments, environment variables, logs and TOML. The separate opt-in native Mac encrypted handoff is the only permitted remote transfer: it SHALL NOT accept any raw plaintext world-cookie field. Only a server-side independently verified cookie MAY be promoted to a protected OS credential provider, using an account/world/player-specific key.

#### Scenario: No terminal or OS credential provider
- **WHEN** a user attempts to bind a world cookie without a TTY or protected keyring
- **THEN** Daedalus SHALL refuse the handoff instead of printing or writing the secret

#### Scenario: User changes configured world/player
- **WHEN** the account identity changes
- **THEN** the previously imported world cookie SHALL not be reused or disclosed to the changed identity

#### Scenario: Failed cookie re-import
- **WHEN** a newly supplied cookie cannot validate the world/player
- **THEN** the previous verified cookie SHALL remain unchanged in protected storage

### Requirement: Saved-cookie worker never transports private authentication material
The controller API, metadata file and CLI arguments SHALL NOT contain saved account email, Gameforge tokens, cookies or credentials. The worker SHALL resolve its saved identity locally from a protected OS keyring, SHALL use only the engine's validated cookie-only world request and SHALL close IPC/session/lease on failure and shutdown.

#### Scenario: Worker restore raises a private error
- **WHEN** saved cookie restoration raises an exception containing sensitive data
- **THEN** the external CLI surfaces a sanitized failure without exposing that data

### Requirement: Embedded synthetic demo cannot access production accounts or persist its token

The one-click demo SHALL use only `create_app(demo_mode=True)`, SHALL bind only an OS-selected loopback IPv4 port, SHALL require an in-memory random bearer token even on local HTTP, and SHALL NOT read real account/IPC/credential stores or persist the demo token to a keyring, repository, URL or configuration file.

#### Scenario: Unauthorized request to local demo port
- **WHEN** a local request lacks the temporary bearer token
- **THEN** the demo SHALL reject protected account and warehouse routes

#### Scenario: Remember connection was enabled
- **WHEN** a user selects the demo action after enabling Remember connection
- **THEN** the UI SHALL explicitly disable persistence for the ephemeral demo token

### Requirement: Remote Mac session material is encrypted for a one-use identity-bound handoff

A backend explicitly opted in to native browser recovery MAY receive encrypted world-cookie material only through a time-limited, single-use public-key challenge scoped to the exact fixed configured account/world/player identity. It MUST require the existing API bearer, trusted HTTPS for remote access, authenticated encryption, protected OS-keyring storage after independent world verification, and sanitized failures. The endpoint MUST reject raw plaintext game cookies, passwords, unrelated profiles, expired challenges and replays.

#### Scenario: Browser session is submitted
- **WHEN** the native Mac user explicitly authorizes one world-cookie handoff
- **THEN** the API receives ciphertext, a one-time client public key and nonce only; no plaintext world cookie or Gameforge identity appears in request fields, logs, responses or project files

#### Scenario: Envelope is tampered with or replayed
- **WHEN** an attacker changes ciphertext, identity binding, or reuses a consumed ticket
- **THEN** decryption/validation fails closed and no worker or verified cookie is replaced
