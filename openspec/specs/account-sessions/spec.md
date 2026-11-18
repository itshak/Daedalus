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

### Requirement: Lease-bound manual authentication assistance

The controller SHALL issue a bounded-lifetime, single-use assistance ticket only to a trusted in-process worker holding the matching account identity lease. A ticket SHALL contain only a random identifier, fixed nonsecret reason and status, never cookies, credentials, or session material.

#### Scenario: Operator completes manual login step
- **GIVEN** a currently owned session with a valid assistance ticket
- **WHEN** a human confirms the manual step is complete
- **THEN** the owner SHALL remain unverified and MUST NOT become authenticated solely on human acknowledgment

#### Scenario: Worker independently verifies
- **GIVEN** a confirmed ticket attached to the same lease
- **WHEN** the trusted worker verifies the actual game session
- **THEN** only that worker MAY transition the owner to authenticated
- **AND** failure SHALL require a new manual ticket before another confirmation

#### Scenario: Expired assistance
- **WHEN** an assistance ticket expires
- **THEN** further approvals SHALL be refused and the owner SHALL pause while retaining its account lease

### Requirement: Explicit lease-bound, cookie-only saved-session probing

The controller SHALL permit an operator to probe previously stored world cookies only after explicit confirmation, only while holding the account/world/player host-local lease, and only for one exact configured enabled identity. The probe SHALL release the lease and close any transient session after returning.

#### Scenario: Another Daedalus process owns the account
- **GIVEN** a matching account lease is already held
- **WHEN** a cookie-only probe is requested
- **THEN** the probe SHALL fail without calling the game provider

#### Scenario: Stored cookies do not validate the configured player
- **WHEN** the cookie-only engine returns an expired or another player's session
- **THEN** the result SHALL report manual recovery required and MUST NOT mark the configured account authenticated

### Requirement: Existing-session monitoring keeps account ownership and requires verified recovery

Only an explicitly opted-in controller MAY monitor an already-authenticated IkaBot engine session after a human confirms the intended account and its exact in-memory game identity is verified. It SHALL retain its host-local account lease across expiration and human assistance. Failed validation SHALL block subsequent task dispatch; successful validation after human acknowledgment SHALL require the same trusted monitor to check the real game session.

#### Scenario: Existing session expires during monitoring
- **GIVEN** an exact existing IkaBot session with a Daedalus monitoring lease
- **WHEN** a read-only world validation finds session expiration or rotation
- **THEN** the owner SHALL transition to assistance and a new game task SHALL NOT be dispatched

#### Scenario: Manual completion cannot restore a failed session
- **GIVEN** a pending one-use assistance ticket
- **WHEN** the user acknowledges the manual step but the worker's validation fails
- **THEN** the owner SHALL remain unverified and require a new assistance ticket without automatic task replay

#### Scenario: Monitoring remains disabled
- **WHEN** the operator starts the default controller without monitoring opt-in
- **THEN** the controller SHALL NOT open game-world validation requests or initiate a new login

### Requirement: Local cookie handoff verifies an exact account under the owner lease

The controller SHALL accept a manually obtained game-world cookie only in a local, explicitly confirmed hidden-input flow. The cookie SHALL be validated against exactly one enabled configured account's world/player while holding its host-local identity lease; it SHALL not start a new Gameforge login or automatically resume tasks.

#### Scenario: Browser cookie belongs to another player
- **GIVEN** an existing browser-authenticated world cookie
- **WHEN** exact player/world validation fails
- **THEN** the account remains unverified and the previous saved binding SHALL NOT be overwritten

#### Scenario: Another local worker already owns the account
- **WHEN** a protected local cookie import is requested under an already held account lease
- **THEN** the import SHALL fail before game-world access or keyring writes

### Requirement: Explicit saved-cookie worker holds one verified identity lease
Daedalus SHALL start a local cookie-only worker only with explicit operator confirmation, a configured enabled account and a protected OS keyring saved-account binding. It SHALL hold the host-local canonical world/player lease for the lifetime of the authenticated session and refuse competing owners.

#### Scenario: Session validates an exact world/player
- **GIVEN** saved cookies resolve to an authenticated engine session matching the configured account
- **WHEN** the operator explicitly starts that saved account worker
- **THEN** the authoritative account lease remains held while its dedicated IPC is running

#### Scenario: Invalid or expired saved cookies
- **WHEN** restored session verification fails
- **THEN** no authenticated worker or IPC starts and the lease is released without attempting a fresh lobby login
