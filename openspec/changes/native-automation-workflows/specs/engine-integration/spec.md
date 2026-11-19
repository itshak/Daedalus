# Engine Integration — UI support without new game client

## Requirement: IkaBot remains the only authoritative game engine
Daedalus SHALL reuse reviewed upstream IkaBot functions for game data, resource/ETA calculations and operation execution. The desktop and controller MUST NOT implement a parallel Gameforge/Ikariam game client, duplicate write requests or guess internal IDs.

### Scenario: Building cost preview
- **WHEN** a user edits an upgrade target
- **THEN** the preview uses a reviewed upstream IkaBot calculation in an authenticated session and never invents a construction cost formula

## Requirement: Strict audited existing-session IPC
Each read-only game-data action SHALL be explicitly allowlisted, performed against the unique existing authenticated session and return a bounded, sanitized DTO. Sensitive responses, arbitrary HTML and uncontrolled upstream exceptions SHALL never be surfaced to the desktop.

### Scenario: New task is found in upstream source
- **WHEN** the AST registry discovers a new function marked @task
- **THEN** the catalog may describe it but the function does not become executable or gain a generic unsafe editor until its adapter, prerequisites and safety contract are reviewed

## Requirement: No fictitious preparation
A native UI SHALL not pass incomplete engine task plans as valid. Interactive-only configurators SHALL remain discovery-only until a separate audited execution adapter provides validated inputs and explicit user consent.

### Scenario: Construction queue requires engine data
- **WHEN** a building queue cannot be produced from verified IkaBot state
- **THEN** no task launch is offered, even if the task's parameter names are known
