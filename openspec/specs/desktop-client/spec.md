# Desktop Client

## Purpose
Extend the existing native PySide6 GUI to expose every supported engine operation.

## Requirements

### Requirement: Comprehensive task controls
The desktop SHALL expose supported task types through discoverable categories, configuration editors, validation, progress, and error states.

#### Scenario: New registered engine task
- **GIVEN** an engine task has a compatible schema
- **WHEN** the GUI loads the backend task registry
- **THEN** the GUI can present an actionable configuration without terminal keystroke automation

### Requirement: Common local and remote behavior
The GUI MUST use the same API contract in local and remote modes.

#### Scenario: Switching between local and remote
- **WHEN** the user changes backend connection
- **THEN** account status, snapshots and task configuration remain accessible through the same client flows

### Requirement: Native Fluent desktop control panel
Daedalus SHALL provide an installable PySide6 Fluent desktop with distinct Accounts, Operations, Warehouses, Log and Connection views.

#### Scenario: Desktop opens before any backend exists
- **GIVEN** the native UI is installed
- **WHEN** a user launches `daedalus-desktop` without configured accounts or a live server
- **THEN** the window opens without a game login and offers a backend connection form

### Requirement: Existing warehouse reporting controls
The GUI SHALL preserve the unsecured 220K resource filter and provide CSV/JSON export without converting missing resources to zero.

#### Scenario: Warehouse snapshots contain unknown fields
- **GIVEN** the backend returns missing resource amounts
- **WHEN** a user loads and exports the warehouse table
- **THEN** those fields remain unknown rather than being displayed as zero

### Requirement: UI does not block during HTTP requests
The desktop MUST perform backend network requests off the Qt GUI thread.

#### Scenario: Remote backend is unreachable
- **WHEN** an API connection fails or times out
- **THEN** the UI displays a sanitized error without freezing or exposing the bearer token

### Requirement: No premature task controls
The first native UI MUST show engine operations only as a read-only inventory until task validation and exclusive worker dispatch are implemented.

#### Scenario: CLI support exists but no account worker is connected
- **WHEN** the user opens the Operations page
- **THEN** operations are discoverable and cannot be executed from the UI

### Requirement: Reproducible native macOS preview
Daedalus SHALL provide a macOS application bundle built directly from a checked-out source revision and a named desktop entry point.

#### Scenario: CI preview build
- **GIVEN** a clean source checkout with no account credentials
- **WHEN** the macOS packaging job runs
- **THEN** it produces an identifiable Daedalus.app archive without running Ikariam, modifying /Applications, or loading account sessions

### Requirement: Preview signing is not production notarization
Mac packaging SHALL distinguish local ad-hoc signing from a developer-signed and Apple-notarized release.

#### Scenario: User obtains a CI preview artifact
- **WHEN** the user downloads the app artifact
- **THEN** documentation explains that it is a preview and may be blocked by macOS Gatekeeper without developer notarization

### Requirement: Native desktop can inspect attached engine sessions without account secrets
The desktop SHALL show whether configured accounts match authenticated existing IkaBot sessions, obtained only after an explicit user request, without exposing engine authentication credentials or account emails.

#### Scenario: Operator checks existing session attachment
- **WHEN** the operator clicks Check IkaBot sessions
- **THEN** the Accounts view reports attached/not attached without launching a game login or displaying credentials

### Requirement: Connected warehouse view preserves export semantics
The native warehouse view SHALL display real typed snapshots from an existing authenticated session when available while preserving the unsecured-resource filter and zero/unknown distinction.

#### Scenario: Backend does not have an authenticated engine session
- **WHEN** the operator requests a warehouse snapshot
- **THEN** the desktop displays a sanitized unavailable error and does not fabricate a resource report

### Requirement: Native GUI task controls require confirmation
The desktop SHALL offer a Tasks interface with a configured account, a built-in
background task selector, a bounded JSON configuration editor, and explicit
operator confirmation before sending a mutating request.

#### Scenario: Operator selects task start
- **WHEN** the operator chooses a task for a particular world/player
- **THEN** the UI presents a confirmation identifying that account and task
- **AND** it sends the request only after confirmation

### Requirement: Disabled backend cannot trigger tasks from GUI
The native Tasks page MUST remain disabled until a connected backend confirms
that explicit task control is enabled.

#### Scenario: GUI connects to a read-only controller
- **WHEN** the backend reports `enabled: false`
- **THEN** the Tasks page cannot launch or stop game tasks

### Requirement: Managed task status and targeted stop are available
The desktop SHALL display task PID, operation, state and start timestamp for
tasks explicitly launched through Daedalus, and SHALL request confirmation
before stopping a selected running task.

#### Scenario: Operator stops one running managed task
- **WHEN** a running task is selected and the operator confirms stopping it
- **THEN** the backend requests termination only of that tracked task

### Requirement: Native task creation requires user confirmation
The Fluent GUI SHALL provide a discoverable Tasks page with a generic JSON task config editor, and MUST require an explicit authorization checkbox and confirmation dialog before sending a game task request.

#### Scenario: User does not confirm
- **WHEN** the user opens Tasks but leaves confirmation unchecked
- **THEN** no task-launch network request is made

### Requirement: Desktop can inspect and stop managed tasks
The GUI SHALL display the engine task lifecycle, and MUST use managed task IDs instead of arbitrary PIDs for stopping and reconciliation operations.

#### Scenario: Operator stops an existing Daedalus-managed child
- **GIVEN** a managed task appears in the task view
- **WHEN** the operator selects and confirms Stop
- **THEN** the desktop sends an authenticated account-scoped stop request

### Requirement: Native island-grouped warehouse export
The native desktop SHALL let the operator choose island ordering and export a human-readable grouped text report without replacing CSV or JSON exports.

#### Scenario: Group warehouses in the desktop
- **GIVEN** authenticated warehouse snapshots contain two cities with the same validated island coordinates
- **WHEN** the operator enables island grouping
- **THEN** the table orders those cities together and a TXT export prints one island heading for both cities

#### Scenario: Backend snapshot lacks island metadata
- **GIVEN** an older read-only IPC worker reports no island coordinates
- **WHEN** the GUI loads its warehouse results
- **THEN** the page remains usable, unknown island values are displayed as unknown, and exports remain available

### Requirement: Opt-in secure desktop connection persistence
The desktop MUST store a bearer token persistently only upon user opt-in and through an operating-system credential provider; it MUST NOT store bearer tokens in ordinary settings or log them.

#### Scenario: User remembers backend connection
- **GIVEN** a protected backend URL and valid token
- **WHEN** the operator selects Remember connection and connects successfully
- **THEN** only its validated URL is written in owner-private settings and the token is stored in the OS keyring

#### Scenario: Credential provider missing
- **GIVEN** the operating system does not expose a keyring backend
- **WHEN** the user requests persistent authentication
- **THEN** the desktop warns without writing a plain-text token or blocking ordinary in-memory connection

### Requirement: User-directed reconnect and forget
The desktop SHALL expose an explicit reconnect action for an in-memory or saved backend identity and a way to forget saved credentials without automatically replaying tasks.

#### Scenario: Backend restarts
- **WHEN** the user requests Reconnect after a transient API failure
- **THEN** only health, account metadata and capability discovery are attempted; game tasks are not resumed or retried

#### Scenario: User forgets preferences
- **WHEN** the operator clicks Forget saved connection
- **THEN** the saved URL and matching keyring secret are deleted where available

### Requirement: Parameter-aware native task configuration
The desktop SHALL render per-task parameter controls derived from validated built-in engine capability metadata, including required status and primitive typing when safely identifiable.

#### Scenario: A task has an optional numeric parameter
- **GIVEN** the engine registry reports alertAttacks.minutes as an integer with a literal default
- **WHEN** the user selects alertAttacks in the native Tasks page
- **THEN** the GUI shows an integer field and can construct a JSON config with that value

#### Scenario: A complex task has nested parameters
- **GIVEN** the engine registry cannot infer a parameter type from a public signature
- **WHEN** the user selects that task
- **THEN** the GUI offers an explicitly JSON-typed form input plus the advanced JSON editor without guessing a game value

### Requirement: Explicit form review before task dispatch
The desktop MUST NOT launch a task using unreviewed form inputs, and must retain checkbox, confirmation dialog and backend validation for every game-state-changing request.

#### Scenario: A parameter form has edits that have not been applied
- **WHEN** the user clicks Start task after editing form fields without building/reviewing their JSON
- **THEN** the desktop refuses to emit the start action until the draft is reviewed

### Requirement: Native account metadata editor
The desktop SHALL let the user create, rename, enable, disable and remove account metadata using the protected local/remote API, without storing Gameforge login credentials.

#### Scenario: User confirms a new account record
- **GIVEN** account editing is enabled on the connected backend
- **WHEN** the operator validates and confirms a new world/player account row
- **THEN** the GUI sends only allowed metadata with the current generation and refreshes account views after success

#### Scenario: Backend editing disabled
- **WHEN** the desktop connects to a read-only or task-dispatch backend
- **THEN** metadata editing is disabled and account viewing remains available

### Requirement: Native confirmation of nonsecret manual login assistance

The desktop SHALL let operators inspect a selected account's nonsecret assistance status and SHALL demand separate affirmative consent to acknowledge a completed human step. It MUST NOT claim that such acknowledgment is worker authentication.

#### Scenario: User cancels or selects another account
- **WHEN** the operator cancels consent or changes the selected account
- **THEN** the client SHALL NOT approve the pending or stale ticket

#### Scenario: User approves the manual step
- **WHEN** the operator confirms a valid current ticket
- **THEN** the client SHALL warn that independent worker validation remains required before automation resumes

### Requirement: Unambiguous native synthetic demo labeling

The desktop SHALL label the connected backend, warehouse resources and window title as SYNTHETIC DEMO whenever the backend identifies itself as a demo. It SHALL NOT visually represent demo amounts as live game observations.

#### Scenario: Demo backend is connected
- **GIVEN** a demo backend with synthetic account fixtures
- **WHEN** the desktop completes the authenticated handshake
- **THEN** the connection and resource views SHALL visibly display a synthetic warning and task controls SHALL remain disabled

### Requirement: Native monitoring consent and nonsecret assistance notifications

The Accounts page SHALL offer an explicit monitor action only when the backend indicates that existing-session validation is enabled. The UI SHALL demand a separate confirmation before sending a monitoring request and SHALL show a bounded nonsecret notification for a new waiting assistance ticket without repeating the same notification.

#### Scenario: User cancels monitoring
- **WHEN** the user declines the dialog to monitor a selected account
- **THEN** the desktop SHALL send no monitoring request

#### Scenario: New expired-session ticket
- **WHEN** a connected monitored backend reports a waiting ticket
- **THEN** the desktop SHALL notify the operator without revealing a cookie, token, ticket ID or full game response, and SHALL NOT automatically replay a task
