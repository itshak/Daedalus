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
