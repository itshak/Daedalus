## ADDED Requirements

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
