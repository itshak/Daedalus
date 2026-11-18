## ADDED Requirements

### Requirement: Durable request IDs prevent unintentional replay
Before sending a game-task start operation, the controller SHALL durably record a unique per-account request ID and config fingerprint. A duplicate request ID MUST return its recorded status without executing the task again.

#### Scenario: Client retries after losing the response
- **GIVEN** a previous task request was accepted or its outcome is uncertain
- **WHEN** the same request ID is retried with identical task parameters
- **THEN** the controller returns the original receipt and does not send another start operation

### Requirement: Unknown dispatch outcomes require manual reconciliation
The controller MUST NOT silently replay a task whose acceptance status is unknown. An unresolved request SHALL block new starts on that account until the operator explicitly acknowledges inspecting the engine and game state.

#### Scenario: Engine IPC response lost
- **WHEN** a task launch's IPC response is lost after dispatch
- **THEN** the ledger records an unconfirmed state and prevents a new launch until a confirmed manual reconciliation
