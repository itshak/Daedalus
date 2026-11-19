## ADDED Requirements

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
