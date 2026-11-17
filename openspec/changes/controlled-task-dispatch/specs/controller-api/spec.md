## ADDED Requirements

### Requirement: Task execution is explicitly opted in and bearer-protected
The controller MUST deny task POST requests unless its operator enabled controlled task dispatch, and MUST require the same bearer authentication as all other account endpoints.

#### Scenario: Default read-only backend
- **WHEN** a user submits a task-start HTTP request without the task-control feature flag
- **THEN** the API returns unavailable without any IPC operation

### Requirement: Validated account-scoped task lifecycle
The task API SHALL accept only known background tasks, secret-free JSON parameter objects, explicit user confirmation and unique request IDs, and SHALL expose managed-task list/stop endpoints.

#### Scenario: Valid authorized task start
- **GIVEN** an enabled account has an already-authenticated engine session and no conflicting owner
- **WHEN** a confirmed, validated task request arrives
- **THEN** the engine launches it through its native task interface and the backend returns its managed task ID
