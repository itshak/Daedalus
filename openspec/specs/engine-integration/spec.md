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
