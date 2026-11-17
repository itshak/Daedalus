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
