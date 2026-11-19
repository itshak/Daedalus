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

### Requirement: Read-only task prerequisites before dispatch

The authenticated task controller SHALL expose a read-only, account-bound task preflight using the authoritative in-memory IkaBot session. The result SHALL include only audited boolean readiness, a nonsecret unresolved-request flag, and reason-code fields. The controller SHALL reject known missing requirements before reserving any task dispatch request, and fail closed when its preflight source is unavailable.

#### Scenario: Missing alert notifications are identified before a task request

- **WHEN** a user checks an alert task for an authenticated account with neither Telegram nor Discord configured
- **THEN** the server returns `notifications_required` without writing to the dispatch ledger, creating a child task, or accessing a saved login

#### Scenario: A preflight request cannot disclose credentials

- **WHEN** a connected client checks an authenticated task's readiness
- **THEN** only the exact target account, task, boolean readiness and an audited reason are returned, never token, webhook, raw session data or game HTML

### Requirement: Deterministic task rejection differs from uncertain dispatch

A task start SHALL preserve original idempotent receipts and SHALL treat only explicitly typed, proven pre-launch engine rejections as rejected. Unknown IPC or network outcomes SHALL remain unconfirmed and block new dispatch until separately reconciled.

#### Scenario: Pre-launch validation fails

- **WHEN** the engine rejects invalid task parameters before creating a child process
- **THEN** the controller marks the request `rejected` and shows a sanitized configuration error without claiming a game task ran

#### Scenario: IPC reply is lost after a possible task start

- **WHEN** the controller cannot establish that the engine rejected before starting a task
- **THEN** it records `unconfirmed` and refuses automatic replay, including if the user changes the task's parameters
