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

### Requirement: Coordinated interactive authentication
A desktop login assistant MUST coordinate with the single account session owner and SHALL NOT initiate an unrequested second game session.

#### Scenario: Remote worker needs human assistance
- **GIVEN** a game worker cannot restore its session
- **WHEN** a user completes login or CAPTCHA with the desktop assistant
- **THEN** the worker validates a protected handoff before resuming automation

### Requirement: Session secrets remain private
The application MUST store live session cookies, tokens and passwords outside the public source tree and CI.

#### Scenario: Successful login
- **WHEN** authenticated session data is saved
- **THEN** it is stored with restricted access and omitted from logs and Git

### Requirement: Host-local human browser assistance
A user-approved local browser recovery SHALL acquire the exact account/world/player lease before opening the official Gameforge lobby and SHALL retain the lease through manual challenge completion, world-cookie verification and protected persistence. The application SHALL NOT collect a password, solve CAPTCHA, expose cookie material over the API, or report authentication success before the engine verifies the configured world and player.

#### Scenario: Human completes a browser challenge
- **GIVEN** an enabled account with an existing protected saved-email binding
- **WHEN** the operator explicitly starts local browser assistance and supplies a world cookie in a hidden terminal prompt
- **THEN** the engine SHALL verify the configured account under the same lease before the cookie is stored in the OS keyring

#### Scenario: Worker already owns the account
- **GIVEN** an existing host-local owner holding the account lease
- **WHEN** the operator requests a second browser-assisted recovery
- **THEN** the application SHALL reject it before opening a browser or prompting for a cookie

### Requirement: Ephemeral browser recovery without credentials
An explicitly approved local recovery SHALL launch a nonpersistent visible browser, leave authentication and challenges to the human operator, and extract only a secure cookie scoped to the exact configured game-world host after operator confirmation. The account owner lease SHALL remain held through browser closure and successful worker-side identity validation. A remote operator MAY use a protected graphical session on the authoritative host, but SHALL NOT send session secrets over the controller API.

#### Scenario: Human completes a challenge in an ephemeral browser
- **GIVEN** an enabled account, protected keyring binding and no conflicting owner
- **WHEN** the operator completes the visible browser login and explicitly confirms the world page is ready
- **THEN** Daedalus SHALL accept only the exact world-host cookie and SHALL store it only after engine verification

#### Scenario: World cookie does not match the expected account
- **GIVEN** a browser with no secure cookie for the configured world or a worker reporting a different player
- **WHEN** the operator attempts recovery
- **THEN** the application SHALL reject the handoff, close the ephemeral browser and retain the previous keyring binding

### Requirement: Idle-only verified dedicated-worker recovery
A dedicated cookie-only worker SHALL allow a user-approved replacement of its session only while its account lease remains held, the new protected cookie restores the exact configured world/player, and the controller confirms no active or uncertain task. It SHALL stop the old IPC endpoint before publishing the replacement, and SHALL NOT replay a task. Failure after IPC shutdown SHALL retain the lease in a failed state for manual reconciliation.

#### Scenario: Recovery of an idle dedicated worker
- **GIVEN** an owned dedicated worker with no running or uncertain tasks and a newly verified world-cookie binding
- **WHEN** the operator approves a session replacement
- **THEN** the worker SHALL validate the replacement, stop its old IPC endpoint, start the new endpoint, and retain the same account lease

#### Scenario: Uncertain task prevents session replacement
- **GIVEN** an unresolved task dispatch or active engine task
- **WHEN** recovery is requested
- **THEN** the worker SHALL refuse session replacement without stopping its existing IPC endpoint

### Requirement: Explicit new-task dispatch after verified recovery
The controller SHALL reject a post-recovery task request unless the same trusted worker has validated its game session, the operator explicitly approves a new task, and a fresh idempotency key and secret-free configuration are supplied. A successful approval SHALL be single-use, and an ambiguous dispatch SHALL NOT be automatically replayed.

#### Scenario: Operator attempts to reuse recovery approval
- **GIVEN** a trusted worker has validated a recovered session and dispatched one approved task
- **WHEN** the client submits a different task request with the same recovery ticket
- **THEN** the controller SHALL reject it without another game operation

#### Scenario: Recovery session expires before dispatch
- **GIVEN** a previously verified recovery ticket
- **WHEN** the read-only game-world validation no longer succeeds
- **THEN** the controller SHALL reject task dispatch without consuming an unverified game session

### Requirement: Exact server-side player attestation before accepting a world cookie

Daedalus SHALL accept a cookies-only IkaBot session only after a TLS-verified,
nonredirecting game-world response contains an independently recognizable
current-player identity matching the configured world/player. Neither locally
saved IkaBot usernames, caller-supplied identities nor successful HTTP status
alone MAY count as an independent player attestation. The engine SHALL expose
only nonsecret validation booleans over its protected IPC interface, and the
controller SHALL reject older IPC responses that lack proof of attestation.

#### Scenario: Game session belongs to another player
- **GIVEN** a saved account named for the configured player and an authenticated world cookie
- **WHEN** the fresh game-world page attests another current player
- **THEN** the cookie-only restore and existing-worker task validation SHALL fail without starting or replaying tasks

#### Scenario: Game-page layout changes or identity is ambiguous
- **WHEN** the game response lacks a recognized current-player marker or contains conflicting identities
- **THEN** the controller SHALL not mark the session authenticated, and human review SHALL be required rather than bypassing attestation

### Requirement: Host-local staged browser recovery for one dedicated worker

An opt-in remote desktop SHALL present trusted-host manual browser recovery
instructions without transmitting session secrets, cookie material, login
links or browser profiles through the controller API. On a single explicitly
owned dedicated worker, the controller SHALL accept only confirmed nonsecret
preparation and assistance-ticket acknowledgment. A new browser cookie SHALL
be staged in a distinct protected keyring slot on that worker host, treated
as unverified until the worker independently validates the current server
identity. Worker replacement SHALL be rejected when tasks are active or
uncertain, SHALL retain the existing world/player lease, and SHALL NOT
automatically replay any game task.

#### Scenario: Operator initiates recovery from a remote desktop
- **GIVEN** one authenticated, idle, authoritative dedicated worker
- **WHEN** the user explicitly prepares recovery in the desktop and completes the browser challenge on the worker host
- **THEN** only the lease-holder SHALL verify and rebind the staged cookie after the ticket is approved
- **AND** no world cookie SHALL cross the desktop/backend API

#### Scenario: Missing staging or unverified replacement
- **GIVEN** a current human assistance ticket for an existing dedicated worker
- **WHEN** a remote rebind is approved without a staged cookie or with a mismatched server player
- **THEN** no worker rebind success SHALL be returned and no prior game task SHALL be replayed

#### Scenario: Running or uncertain operation
- **GIVEN** an active managed game task or ambiguous previous dispatch
- **WHEN** the user requests a new recovery attempt
- **THEN** the backend SHALL refuse to replace its worker until the user reconciles the outstanding game state

### Requirement: Native Mac human browser session recovery uses one authoritative worker

The client SHALL allow a human to sign in to official Gameforge pages using a temporary native Mac browser without automated CAPTCHA or password entry. It SHALL select only the exact enabled account world session with explicit transfer confirmation. The backend SHALL verify the fresh server-rendered player/world independently before accepting the cookie. A dedicated worker SHALL retain its original lease and SHALL not replay old tasks.

#### Scenario: Human finishes Mac sign-in
- **WHEN** a Mac user signs in and authorizes an encrypted world-cookie transfer
- **THEN** the backend verifies the actual selected player's game-world identity before saving the session or rebinding the existing dedicated worker

#### Scenario: Session mismatches the player
- **WHEN** game-world verification fails or the envelope is expired or replayed
- **THEN** the old verified cookie and authoritative worker lease remain protected; no task is started

### Requirement: Explicit Mac handoff can attach a cookie-only worker for live reports

When a user explicitly approves Mac browser sign-in or warehouse loading and the exact world/player cookie has passed independent backend verification, the authoritative daemon SHALL be able to start a separate cookie-only IkaBot child for that account under an exclusive host-local identity lease. The child SHALL retrieve the world cookie from the protected server credential store, not from a plaintext API response or process argument, and SHALL provide private IPC only after a fresh independent player attestation. A worker launch failure SHALL retain the verified saved cookie but SHALL NOT mark the account authenticated, claim an attached IPC worker, or replay prior tasks. Each account SHALL have an isolated IPC descriptor and owned process lifetime.

#### Scenario: Browser login creates a reportable account without a preexisting worker

- **WHEN** an approved, independently verified Mac handoff is completed on a worker-capable backend
- **THEN** the dedicated child verifies exact world/player and attaches IPC before the account becomes authenticated and available to warehouse reporting

#### Scenario: Worker startup cannot attest the game session

- **WHEN** the child exits or its identity probe fails
- **THEN** the API reports saved cookie but no worker, and releases the lease only after confirming child shutdown

### Requirement: Previously verified native game cookies restore on explicit server startup

Daedalus SHALL allow an operator to opt in to cookie-only restoration of
previously verified, protected game-world bindings at server startup, with
explicit read-only network confirmation. Each identity SHALL receive its own
IPC process and exclusive host-local session lease, and SHALL only show
`authenticated` after a fresh exact world/player attestation. An unavailable,
expired or conflicting saved credential SHALL leave that account disconnected,
without preventing recovery attempts for other saved identities. Restoration
SHALL NOT use a Gameforge lobby loginLink or replay game jobs.

#### Scenario: Ten configured accounts have individually verified saved cookies

- **WHEN** the server starts with native saved-cookie restoration and read-only network consent
- **THEN** it SHALL attempt isolated cookie-only attestation for each eligible account and report only successful workers as authenticated
- **AND** a failed child SHALL not consume or invalidate another account's saved cookie or block subsequent restorations

### Requirement: Cookie-only data reads must not reauthenticate or kill IPC ownership

A cookie-only IkaBot session restored from an explicitly verified saved world
cookie SHALL use bounded, TLS-verified, exact-world-origin GET requests for
read-only city and warehouse retrieval. It MUST NOT invoke the legacy session's
implicit lobby login, request a loginLink, follow a world-to-lobby redirect or
exit the worker process when its saved PHP session differs. An invalid or
expired response SHALL produce a sanitized unavailable state while the daemon
retains and reconciles its authoritative worker ownership. Ordinary non-cookie
sessions SHALL retain their original IkaBot behavior.

#### Scenario: Reading cities or warehouses after cookie-only restoration

- **WHEN** the authorized client reads city data through an already authenticated cookie-only IPC worker
- **THEN** the game request SHALL use the existing world cookie without refreshing the lobby, and a verified reply SHALL not terminate the worker
- **AND** a server error, redirect or expiration SHALL fail closed without leaking cookie values or triggering a new Gameforge login



The backend MUST refuse native browser recovery of a dedicated worker with running, stopping, dispatching, or unconfirmed operations. It MAY pause an idle worker under its existing exclusive identity lease, and MUST keep the lease on failed or uncertain rebind without starting a competing worker.

#### Scenario: Unconfirmed task exists
- **WHEN** an operator requests browser recovery while a durable task receipt remains unconfirmed
- **THEN** recovery is refused without altering the worker or starting another game operation

### Requirement: Controlled credential migration preserves the exact verified game identity

A session credential migration SHALL read existing private account metadata and a cookie only through authorized local sources, re-attest the exact configured world/player from a fresh TLS-verified nonredirecting read-only game page before promoting any legacy cookie, write it exclusively to protected encrypted storage, and verify readback without logging values. Restart SHALL preserve durable task receipts and SHALL NOT replay previous tasks. A completed backend service restart SHALL NOT be equated with whole-host reboot testing or real owner acceptance.

#### Scenario: Legacy saved cookie does not attest the configured player

- **WHEN** the saved source cookie fails fresh server player/world attestation
- **THEN** no unverified cookie is promoted and the controlled worker restart is blocked

#### Scenario: A prior task request has an uncertain outcome

- **WHEN** an operator identifies a prior uncertain task after confirming no managed task is active
- **THEN** reconciliation may mark only that inspected request with an auditable, nonreplaying receipt; it never asserts that the prior game action succeeded

### Requirement: Supervised real-account authentication acceptance
Production cutover SHALL require a supervised real-account test confirming that the authoritative worker validates the actual server-side player identity and that a native Mac desktop can complete human browser recovery using a single-use encrypted handoff without plaintext session secrets in controller API fields.

#### Scenario: Owner authorizes supervised recovery
- **GIVEN** an isolated, explicitly authorized account and one authoritative worker host
- **WHEN** the owner performs a browser login or manual challenge and requests recovery
- **THEN** the worker SHALL validate the game-world session and independently attest the configured player before any new user-approved task is dispatched

#### Scenario: Passing offline tests cannot authorize production
- **GIVEN** synthetic browser, IPC, GUI and server-side identity regression tests pass
- **WHEN** no actual isolated Gameforge account has completed the owner-supervised recovery and task trial
- **THEN** the owner-run real-account acceptance checklist SHALL remain open in the dedicated tracking issue, independent of implementation archival, and production cutover SHALL remain unauthorized

### Requirement: Nonsecret deployment preflight must not imply production acceptance

The host-side operator SHALL be able to inspect only local task-receipt status counts and protected-keyring file metadata to diagnose safe restart prerequisites, without reading credential values, game sessions or performing game network requests. The diagnostic SHALL distinguish absent, unsafe and unresolved ledger state and SHALL report any mere persistent keyring file as **unverified** pending a real reboot test. Passing these checks SHALL NOT set production approval.

#### Scenario: Outstanding task receipts block live cutover

- **GIVEN** an existing ledger containing a `dispatching` or `unconfirmed` request
- **WHEN** the operator runs the local deployment check
- **THEN** the check reports a blocked state and anonymous unresolved count without reading configuration payloads or changing the ledger

#### Scenario: Session-only keyring is not reboot proof

- **GIVEN** the server's keyring uses only an in-memory session collection
- **WHEN** the operator checks deployment readiness
- **THEN** the check warns that durability is absent or unverified and does not claim successful restart or production acceptance

### Requirement: Durable Mac-sealed Gameforge login backups
After explicit account login and independent server identity verification,
Daedalus SHALL permit the Mac to store an account-specific AES-GCM sealed
login in the server's persistent protected credential store. Only the
originating Mac Keychain SHALL hold the decryption key. The absence of a
backup MUST NOT invalidate an independently verified game session.

#### Scenario: Password absent in local Keychain, vault key retained
- **GIVEN** a server-persisted sealed login for this account/world and a matching
Mac Keychain vault key
- **WHEN** the user starts headless Selenium login
- **THEN** the Mac decrypts in memory without sending plaintext credentials
to the Daedalus API and opens a visible browser for CAPTCHA or for a failed
headless attempt to allow user-directed login recovery; server attestation
remains mandatory before any worker is promoted
