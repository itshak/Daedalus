## ADDED Requirements

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
