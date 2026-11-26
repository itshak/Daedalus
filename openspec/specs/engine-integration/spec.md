# Engine Integration

## Purpose
Keep upstream IkaBot the only game-operation implementation.

## Requirements

### Requirement: Typed task adapter
Daedalus SHALL discover available engine tasks, validate configurations and submit supported tasks through an engine-owned CLI/IPC interface.

#### Scenario: Valid task configuration
- **GIVEN** a compatible running worker
- **WHEN** a validated task request is received
- **THEN** the engine receives a typed task configuration and the backend records its lifecycle

### Requirement: Upstream compatibility
Engine updates MUST preserve source attribution and include regression tests before production deployment.

#### Scenario: New upstream release
- **WHEN** an upstream engine revision is integrated
- **THEN** previously supported task configurations and offline fixtures are checked before cutover

### Requirement: Combined stable and proposed upstream code
Daedalus SHALL integrate the stable upstream baseline and the proposed JSON CLI/IPC branch using traceable upstream revisions, retaining fixes from both branches.

#### Scenario: Trace upstream contributions
- **GIVEN** a vendored CLI-enabled IkaBot engine
- **WHEN** a developer reproduces the upstream merge using the documented commit IDs
- **THEN** the imported engine source matches the public source and retains MIT notices

### Requirement: Offline recognition of structured CLI support
The Daedalus inventory SHALL detect public engine CLI and IPC entry points from source code without importing game modules, opening sockets or starting authenticated sessions.

#### Scenario: Inspect the new engine
- **GIVEN** a CLI-enabled upstream engine source tree
- **WHEN** the user runs `daedalus engine inventory`
- **THEN** output reports that the engine contains structured CLI support, without claiming task execution or session ownership is implemented

### Requirement: No premature game-task execution
The controller MUST NOT expose the upstream IPC task launcher over its HTTP API before exclusive session ownership, task validation and authorization are implemented.

#### Scenario: Controller before worker integration
- **GIVEN** the upstream IPC module has been vendored
- **WHEN** a desktop client lists capabilities
- **THEN** it can inspect the engine's documented functions but cannot launch a live game task

### Requirement: Existing-session IPC requests cannot restore a game login
Daedalus SHALL provide separate, explicit IPC actions for listing in-memory authenticated sessions, reading their cities, and retrieving warehouse resources. Each action MUST refuse missing or ambiguous session identities and MUST NOT call saved-session login restoration.

#### Scenario: World/player has no active in-memory session
- **GIVEN** no authenticated IkaBot session exists for the specified world/player
- **WHEN** the controller invokes an existing-only IPC operation
- **THEN** the operation fails without creating or restoring a session

### Requirement: Warehouse IPC replies expose numeric data only
The IkaBot engine SHALL extract known unsecured-resource and capacity values from authenticated warehouse responses without transmitting raw HTML or action tokens to the controller.

#### Scenario: Warehouse HTML contains a sensitive action field
- **GIVEN** the game page includes resource spans and a hidden actionRequest token
- **WHEN** the controller requests an existing-session warehouse snapshot
- **THEN** the IPC reply includes only resource amounts and city identity; it does not include the hidden token or page markup

### Requirement: Existing authenticated session is necessary for task launch
The IkaBot IPC engine SHALL offer a distinct task-launch action that requires
an unambiguous already-authenticated world/player in-memory session and MUST
NOT restore or create a game login.

#### Scenario: Task requested for an account without a session
- **GIVEN** no in-memory authenticated session matches the requested identity
- **WHEN** the controller attempts to start a built-in task
- **THEN** the request fails without a saved-session restoration or new login

### Requirement: Managed task registry restricts stopping processes
The engine MUST allow termination only for child Process objects it launched
through the Daedalus existing-session task interface and MUST reject
arbitrary PIDs and unrelated account identities.

#### Scenario: User provides another OS process PID
- **WHEN** the controller requests task termination for a PID it did not launch
- **THEN** the engine refuses the request without signaling that process

### Requirement: Task starts are idempotent and schema-validated
The engine SHALL validate packaged built-in task modules and JSON parameter
signatures and SHALL deduplicate identical start requests by UUID4, rejecting
a UUID reused with different parameters.

#### Scenario: Client retries a task start
- **GIVEN** a start request was previously accepted
- **WHEN** the same account, task, config and UUID4 are submitted again
- **THEN** the engine returns the earlier result without starting another child

### Requirement: Managed tasks use existing authenticated game session only
The engine SHALL expose distinct existing-session-only IPC task start/list/stop operations that MUST NOT restore a saved session or open a new Gameforge login.

#### Scenario: No existing authenticated player
- **GIVEN** the engine has no logged-in session matching an explicit world/player
- **WHEN** a task-start request is received
- **THEN** the engine refuses without launching a game worker or calling Session.from_saved

### Requirement: Task stop targets managed child handles
The engine MUST stop only child processes created and retained under its own opaque managed-task IDs, never an arbitrary client-submitted OS process ID.

#### Scenario: Stop request for another account's task ID
- **GIVEN** a managed task belongs to account A
- **WHEN** account B requests its task ID be stopped
- **THEN** the engine refuses and leaves the child running

### Requirement: Offline bounded task parameter metadata
The engine registry SHALL derive form metadata only from parsed public IkaBot source files without importing game modules or evaluating arbitrary expressions.

#### Scenario: Task has a runtime default expression
- **GIVEN** a task default argument is a function call rather than a literal
- **WHEN** offline registry introspection inspects that task
- **THEN** no expression is executed and no fabricated default value is returned

### Requirement: Safe saved-world-cookie restoration without new lobby login

The Daedalus-vendored IkaBot engine SHALL offer an explicit `cookies_only` restoration mode that validates only previously stored world cookies. That mode MUST NOT query the lobby login token, mint a blackbox, request a loginLink or create a new Gameforge session.

#### Scenario: Saved cookie is expired or redirected
- **GIVEN** invalid cookies for the requested world/player
- **WHEN** the engine attempts cookie-only restoration
- **THEN** it SHALL fail without issuing a lobby login or interactive CAPTCHA request

#### Scenario: Existing valid saved world cookie
- **GIVEN** a valid stored `ikariam` world cookie and exact selected identity
- **WHEN** a world GET returns HTTP 200 on the expected host
- **THEN** the engine MAY report a verified transient saved world session

### Requirement: Fixed read-only validation of an existing authenticated engine session

The Daedalus-maintained IkaBot IPC overlay SHALL provide a strictly allowlisted action that chooses only a matching in-memory authenticated game session and performs a read-only probe to its own canonical HTTPS world URL. It SHALL return only a boolean and matching world/player identity. It MUST NOT call `Session.from_saved`, start another login, deliver raw HTML, send action tokens across IPC or accept arbitrary URLs.

#### Scenario: Expired or redirected response
- **GIVEN** an already attached world session
- **WHEN** its world response is expired, redirected to lobby or lacks the game marker
- **THEN** the engine SHALL return `session_valid=false` with no cookie or HTML

#### Scenario: Wrong account identity
- **WHEN** a request names a different player or world
- **THEN** no matching session SHALL be selected and no game request SHALL occur

### Requirement: In-memory game-world cookie override is limited to safe restoration

The Daedalus-maintained IkaBot engine SHALL permit an already authenticated game-world cookie override only in an explicit cookies-only restoration call with exact world/player selectors. It MUST NOT send lobby loginLink or blackbox requests or persist the override into upstream saved-session files.

#### Scenario: Override supplied to normal upstream login
- **WHEN** a caller supplies a world cookie override without cookies-only mode
- **THEN** the engine SHALL refuse it before making any network request

#### Scenario: Verified exact world cookie
- **GIVEN** a syntactically valid existing cookie for a saved world/player
- **WHEN** the exact game-world GET validates it
- **THEN** only the verified in-memory engine session MAY use that cookie without creating a new lobby login

### Requirement: Dedicated IPC is exclusive to the verified saved worker
The engine SHALL register an already-authenticated cookie-only restored session with a new protected loopback IPC owner only if no running IkaBot IPC owner can be found. It MUST NOT join an unrelated IPC server, run a new Gameforge login or replace another worker.

#### Scenario: Existing IPC owner detected
- **GIVEN** another existing IPC owner responds on the host
- **WHEN** the local saved worker tries to start its dedicated IPC
- **THEN** startup fails closed without replacing that owner's session or credentials

### Requirement: Auditable upstream engine import
Imported public engine source SHALL be traceable to a specific upstream revision and preserve all required license and copyright notices.

#### Scenario: Upstream update review
- **GIVEN** a public engine update is proposed
- **WHEN** it is integrated
- **THEN** maintainers can verify its origin and run regression tests using synthetic identities

### Requirement: Nonconflicting Python namespaces
The `daedalus` controller and upstream `ikabot` engine MUST have nonconflicting imports and installation paths.

#### Scenario: Install the combined application
- **WHEN** the distribution installs the engine and backend
- **THEN** the intended engine module resolves without shadowing the legacy desktop scraper

### Requirement: Safe production-authentication source reconciliation
Daedalus SHALL review locally modified production IkaBot source against its
pinned public upstream before porting any behavior. Only explicitly audited
nonsecret changes MAY be reimplemented. The process MUST NOT import local
account data, cookie files, credentials, runtime logs or automatic task-launch
behavior into the public engine.

#### Scenario: Review a locally modified production engine
- **GIVEN** a private tracked-source patch against an older public engine
- **WHEN** a maintainer reconciles it
- **THEN** each changed source file receives a documented port, reject or already-upstream disposition and a source-only patch fingerprint
- **AND** no private source archive or runtime credential material is committed

### Requirement: Fail-closed detached engine authentication
The optional native engine login SHALL fail promptly rather than recursively
prompting on exhausted noninteractive input. The external blackbox-token
retrieval helper SHALL use bounded retries only for transport failures and
MUST NOT expose credential-bearing exception strings or API response bodies
through its public errors.

#### Scenario: Token API unavailable in a detached worker
- **GIVEN** no interactive operator terminal and a failed token API request
- **WHEN** the optional native engine login needs manual blackbox assistance
- **THEN** it fails with a nonsecret assistance-required error without prompting for a password, cookie or new Gameforge session

#### Scenario: Token API responds with failure or incompatible parameters
- **WHEN** the API reports HTTP 400/422
- **THEN** the existing single user-agent compatibility request remains available
- **AND** any unauthorized HTTP response or malformed payload fails closed without replaying Gameforge login or displaying the response body

### Requirement: Existing-session-only task readiness over private IPC

The engine SHALL expose an allowlisted, read-only task-prerequisite action for its exact authenticated world/player. The action SHALL only return nonsecret audited readiness states and SHALL never start or recover a login. Missing alert notification destinations SHALL be diagnosed before task process creation.

#### Scenario: Alert is missing a notification destination

- **WHEN** the existing account has neither a saved Telegram destination nor a Discord webhook for an alerting task
- **THEN** the IPC server returns `notifications_required`, and a launch for that task returns a typed pre-process rejection without creating a task child

#### Scenario: Other accounts cannot be queried

- **WHEN** the client requests a preflight for a different or ambiguous world/player
- **THEN** the engine rejects the request and does not open a new login or return session material

### Requirement: IkaBot commits fixed cargo progress around transport mutations
For Daedalus-managed own-city fixed-quantity transfers, the maintained IkaBot transport engine SHALL write an owner-only, route-scoped pending receipt before each irreversible transport POST and SHALL mark that receipt confirmed only following an explicit successful game response. Confirmed receipts SHALL atomically increase dispatched quantities without exceeding the original target. A definite rejection MAY release the reservation without incrementing cargo; a timeout, crash or unrecognized game response MUST leave an unresolved checkpoint that prevents silent replay.

#### Scenario: Several ship batches complete before disconnect
- **GIVEN** a single fixed resource route must be split across multiple ships
- **WHEN** the first ship batches receive valid game success responses and the worker later loses its session
- **THEN** the retained engine journal SHALL show the accepted quantities of each batch and a new worker SHALL resume only the outstanding quantities

#### Scenario: Engine loses response after sending cargo
- **WHEN** a transport request has a durable pending receipt but no definitive game acceptance or rejection
- **THEN** the engine MUST NOT repeat that send automatically, even if a new worker or process begins

### Requirement: Source-audited operation coverage manifest
The integration SHALL inventory public menu actions and registered tasks and maintain an explicit coverage entry for each. Missing registry rows SHALL fail the inventory drift test. Coverage status MUST NOT imply full upstream or live acceptance.

#### Scenario: Upstream adds an operation
- **WHEN** the vendored engine inventory changes
- **THEN** the coverage test reports an operation without a reviewed entry

### Requirement: Reviewed external transport recipient verification
Native external shipments and recurring external consolidation SHALL bind the observed island, city and recipient identities, rechecking the receiving identity before dispatch and cargo requests. External routes MUST NOT be automatically restored.

#### Scenario: A reviewed recipient changes
- **WHEN** recipient ownership or eligibility changes before a shipment
- **THEN** the engine stops rather than sends to a changed recipient

### Requirement: Protected upstream military read compatibility
The engine SHALL reuse the upstream `viewArmy.getCityMilitaryData` and `parseUnits` helpers and the shared military advisor reader for existing-session military inspection. The verified-cookie session adapter SHALL accept only the audited upstream `cityMilitary` read form: matching positive city identifiers, `activeTab` and `currentTab` equal to `tabUnits`, `templateView=cityMilitary`, the upstream action-request placeholder and `ajax=1`, with no extra fields. It SHALL verify the current player and request token and use the existing protected same-world read transport without implicit relogin or game orders. The original upstream inventory reader and parser SHALL remain unchanged.

#### Scenario: Military inventory on a verified cookie worker
- **GIVEN** a uniquely authenticated worker and verified owned cities
- **WHEN** the upstream military inventory helper reads a city
- **THEN** the exact upstream request uses the protected read transport, returns the original response shape to the upstream parser and leaves the worker available for subsequent reads

#### Scenario: Invalid military read form
- **WHEN** a military inventory form includes mismatched city identifiers, a changed tab or extra mutation fields
- **THEN** the adapter rejects the form before any game POST and does not fall through to legacy login

#### Scenario: Regression coverage for actual upstream reads
- **WHEN** the military session adapter changes
- **THEN** offline tests SHALL invoke the actual upstream helper through the real cookie-session transport with a synthetic HTTP response and verify exact request parameters, rejection of unsafe forms and absence of implicit login; mocked IPC DTO tests alone SHALL NOT establish transport compatibility

### Requirement: IkaBot remains the only authoritative game engine
Daedalus SHALL reuse reviewed upstream IkaBot functions for game data, resource/ETA calculations and operation execution. The desktop and controller MUST NOT implement a parallel Gameforge/Ikariam game client, duplicate write requests or guess internal IDs.

#### Scenario: Building cost preview
- **WHEN** a user edits an upgrade target
- **THEN** the preview uses a reviewed upstream IkaBot calculation in an authenticated session and never invents a construction cost formula

### Requirement: Strict audited existing-session IPC
Each read-only game-data action SHALL be explicitly allowlisted, performed against the unique existing authenticated session and return a bounded, sanitized DTO. Sensitive responses, arbitrary HTML and uncontrolled upstream exceptions SHALL never be surfaced to the desktop.

#### Scenario: New task is found in upstream source
- **WHEN** the AST registry discovers a new function marked @task
- **THEN** the catalog may describe it but the function does not become executable or gain a generic unsafe editor until its adapter, prerequisites and safety contract are reviewed

### Requirement: No fictitious preparation
A native UI SHALL not pass incomplete engine task plans as valid. Interactive-only configurators SHALL remain discovery-only until a separate audited execution adapter provides validated inputs and explicit user consent.

#### Scenario: Construction queue requires engine data
- **WHEN** a building queue cannot be produced from verified IkaBot state
- **THEN** no task launch is offered, even if the task's parameter names are known

### Requirement: Reviewed cookie-session mutation compatibility
For audited original construction, recruitment, layout, worker, donation, wine and study request forms, the protected cookie-session adapter SHALL preserve the upstream request fields and endpoint, verify the exact player and selected city using a fresh HTTPS world page, replace the request token from that page, submit at most once and reject malformed, mismatched or uncertain responses without relogin or replay. The upstream task preparation remains responsible for fresh ownership and reviewed operation constraints.

#### Scenario: A reviewed city request is sent
- **GIVEN** a verified cookie-only worker and a reviewed upstream mutation with the exact expected form
- **WHEN** the original upstream helper submits the request
- **THEN** only one same-world bounded POST SHALL be attempted; wrong city/player, additional fields or retry options SHALL fail closed

#### Scenario: The server reply is lost
- **WHEN** the protected reviewed POST receives an uncertain transport outcome
- **THEN** it SHALL report uncertainty and MUST NOT repeat the mutation
