## ADDED Requirements

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
