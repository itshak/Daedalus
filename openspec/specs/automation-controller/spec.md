# Automation Controller

## Purpose
Schedule game tasks safely and reconcile desired policy with observed game state.

## Requirements

### Requirement: Idempotent policy reconciliation
The controller MUST check live state and pending operations before repeating any state-changing request.

#### Scenario: Service restart during upgrade
- **GIVEN** a construction job may have been accepted before restart
- **WHEN** the controller resumes
- **THEN** it checks current building and task state before scheduling an additional upgrade

### Requirement: Native transport execution
Wine and construction-supply policies SHALL delegate transport execution to upstream engine modules.

#### Scenario: Planned wine shipment
- **WHEN** the policy calculates a needed wine transfer
- **THEN** a validated engine transport operation is requested rather than using a second HTTP game client

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
