# Delta: Automation Controller

## ADDED Requirements

### Requirement: Persist previously approved desired background tasks independently of engine PIDs

After an operator authorizes ongoing managed IkaBot automations for an exact account, Daedalus SHALL durably persist a versioned, secret-free task configuration and a desired running/stopped flag in a private store distinct from the existing request ledger. The desired-state store SHALL be updated by subsequent task stop, edit and deletion actions; a process ID, task name or configuration hash alone SHALL NOT be considered sufficient to recreate a job.

#### Scenario: Browser takeover kills the old game worker
- **GIVEN** two running managed restartable background tasks with their approved, validated configurations persisted
- **WHEN** IkaBot closes those task processes following a rotated world login
- **THEN** the two desired-running records SHALL survive backend and engine process exits without implicitly launching new game operations

#### Scenario: User stops a task during the five-minute grace period
- **GIVEN** a desired task set to running and a pending automatic recovery
- **WHEN** the owner stops, disables or removes that task
- **THEN** its desired-state revision SHALL change immediately and the recovery reconciler SHALL not restart it

#### Scenario: Legacy jobs have missing configurations
- **GIVEN** an active upstream IkaBot task visible only by name and PID
- **WHEN** Daedalus builds an import preview for future restoration
- **THEN** it SHALL require an inspected and explicitly approved local configuration before including that task in a persistent desired set

### Requirement: Restore only safely reconcilable tasks after verified session recovery

Automatic task restoration SHALL require a verified account owner/IPC session, an approved policy, an audited restartable task type, no unresolved dispatch, and proof that the logical task is absent. A restoration SHALL be a fenced, versioned, new desired-state launch with a fresh request ID; no earlier unknown game operation may be replayed.

#### Scenario: Reconnect successfully restores continuous jobs
- **GIVEN** a verified reconnected worker and two approved continuously running, restart-safe desired jobs
- **WHEN** the reconciler verifies neither logical task is already active and no uncertain receipt exists
- **THEN** each missing job SHALL receive at most one durable new dispatch in the current worker generation, and the UI SHALL show running only after a verified engine receipt

#### Scenario: Ambiguous dispatch or in-flight non-idempotent action
- **GIVEN** a previous request is dispatching/unconfirmed or a one-shot operation may have affected game state
- **WHEN** the account reconnects
- **THEN** Daedalus SHALL NOT relaunch that operation automatically, SHALL preserve its original receipt and SHALL flag it for inspected/manual reconciliation

#### Scenario: Two reconcilers race after daemon restart
- **GIVEN** a desired task for the same account and recovery epoch
- **WHEN** two events attempt to reconcile it concurrently
- **THEN** a durable per-task/per-generation fence SHALL allow at most one start request, including when the first response is lost

#### Scenario: Account partially recovers
- **GIVEN** three desired tasks, one already running, one safely restartable and one requiring manual state review
- **WHEN** a fresh verified game worker becomes available
- **THEN** the first task SHALL remain single-instance, the second MAY be restored with a new receipt, and the third SHALL remain paused with a clear reason rather than being declared restored

### Requirement: Account recovery is bounded and auditable without secret disclosure

The task reconciler SHALL expose per-account totals of desired, restored, observed-running, waiting and blocked jobs and a bounded redacted reason history. It SHALL enforce an account-level stop on unknown or unconfirmed outcomes and SHALL not store passwords, cookies, Gameforge refresh tokens, URLs containing tokens, browser profiles or arbitrary executable code in its desired-state store.

#### Scenario: Server starts with zero authenticated workers
- **WHEN** Daedalus reloads a persisted desired task catalog with no live game session
- **THEN** the API SHALL remain healthy and list the desired tasks as waiting, without starting them before authenticated recovery and owner policy checks
