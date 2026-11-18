## ADDED Requirements

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
