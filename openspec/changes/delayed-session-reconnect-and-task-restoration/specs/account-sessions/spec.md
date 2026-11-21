# Delta: Account Sessions

## ADDED Requirements

### Requirement: Opt-in automatic recovery after a confirmed rotation grace period

For each exactly configured enabled world/player identity, Daedalus SHALL offer an explicitly approved and persistently revocable **automatic session reconnection** policy. When enabled, an authoritative host-local recovery supervisor SHALL distinguish an independently confirmed game-session rotation from an inconclusive network error, immediately prevent new task dispatch and wait a minimum default **300 seconds after confirmed loss** before any unattended game login.

#### Scenario: Owner logs into the game with another browser
- **GIVEN** an enabled account with a verified Daedalus worker and a preapproved 300-second automatic recovery policy
- **WHEN** the engine or two independent read-only probes confirm the world session was rotated
- **THEN** Daedalus SHALL mark that account as in a browser grace period, block new tasks and not initiate a replacement session before the deadline
- **AND** other authenticated accounts SHALL remain unaffected

#### Scenario: A single transient network outage
- **GIVEN** an authenticated worker and no independent proof of session rotation
- **WHEN** one network timeout, generic 5xx or malformed game response occurs
- **THEN** Daedalus SHALL record an inconclusive check without starting the rotation countdown or acquiring another game login

#### Scenario: API restart during a grace period
- **GIVEN** a confirmed loss and persisted grace deadline
- **WHEN** the backend restarts or its wall clock changes
- **THEN** the recovery controller SHALL reconstruct the account state without shortening the remaining safe delay or starting duplicate workers

### Requirement: Protected, bounded and independently verified world reauthentication

An approved unattended reauthentication SHALL use a trusted backend and the maintained IkaBot engine with a previously authorized, protected server-usable lobby credential. An expired world cookie or Mac-only vault is not sufficient. The supervisor SHALL verify the world/player under the exact host-local lease before publishing an authenticated worker; no authentication material may cross an API.

#### Scenario: Lobby token is valid and recovery is due
- **GIVEN** an enabled account with a server-protected usable lobby credential, no competing worker and a completed grace period
- **WHEN** the supervisor obtains a new world session through the trusted engine flow
- **THEN** it SHALL validate the exact HTTPS world host, expected player and IPC owner before setting that account to authenticated
- **AND** it SHALL not dispatch any desired tasks until a separate reconciliation gate passes

#### Scenario: Token is invalid or CAPTCHA is required
- **GIVEN** a due recovery attempt
- **WHEN** lobby authentication fails, requires CAPTCHA/MFA or returns a different identity
- **THEN** Daedalus SHALL stop automatic login, preserve the disabled task-dispatch gate and offer an explicit existing Mac-assisted recovery path without bypassing the challenge

#### Scenario: Multiple accounts rotate together
- **GIVEN** several approved accounts with expired game sessions
- **WHEN** their grace periods expire simultaneously
- **THEN** the supervisor SHALL serialize unattended lobby login attempts across accounts, retain independent leases, enforce per-account retry limits and avoid simultaneous Gameforge login storms

### Requirement: Browser-use pause and explicit early reconnect

Daedalus SHALL permit the owner to pause a per-account recovery policy for a defined duration or until manually resumed. The approved five-minute policy SHALL not claim it can detect human browser inactivity. The UI SHALL explain that unattended game login can end a currently active browser session, while an explicitly approved **Resume now** may bypass only the grace period and never any identity, lease, replay or unresolved-operation safeguard.

#### Scenario: Owner is still browsing after five minutes
- **GIVEN** an account in the recovery grace period
- **WHEN** the owner chooses Pause for browser use before the recovery deadline
- **THEN** Daedalus SHALL defer automatic Gameforge login until the pause ends or the owner explicitly resumes it

#### Scenario: User asks to reconnect immediately
- **GIVEN** a confirmed lost session and an enabled recovery policy
- **WHEN** the owner invokes Resume now and acknowledges browser-session interruption
- **THEN** the controller MAY attempt reauthentication before the countdown reaches zero
- **AND** all normal credential, lease, identity and task-reconciliation requirements SHALL still apply
