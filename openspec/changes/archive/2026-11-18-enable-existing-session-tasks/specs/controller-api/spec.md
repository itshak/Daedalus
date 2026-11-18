## ADDED Requirements

### Requirement: Task mutations require explicit server opt-in
Daedalus SHALL keep task launch/stop disabled by default, and SHALL only offer
mutation operations after the operator enables an existing-session task-control
mode in a loopback-bound, bearer-protected backend.

#### Scenario: Default backend receives a task request
- **GIVEN** a default Daedalus controller with an account configured
- **WHEN** an authorized client submits a task-start request
- **THEN** it receives HTTP 503 and no engine operation is invoked

### Requirement: Backend validates account scope and built-in operations
Task API requests MUST reference configured account identities and packaged
built-in background tasks, with bounded JSON configs and UUID4 request IDs.

#### Scenario: An interactive-only menu operation is requested
- **WHEN** an authenticated client submits a menu-only operation as a task
- **THEN** the API rejects it without forwarding it to IkaBot IPC
