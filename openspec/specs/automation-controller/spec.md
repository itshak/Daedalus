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

### Requirement: Fixed-quantity cargo restoration uses confirmed dispatch progress
For newly approved Daedalus-managed `sendResources` tasks between cities belonging to the same verified account, the controller MUST durably retain the original per-route, per-resource quantity and a server-generated logical transfer ID before task launch. On verified reconnection it MUST compute remaining cargo as original targets minus independently confirmed engine dispatch receipts. It MUST NOT infer a dispatched cargo amount from warehouse stock changes or the presence of trading ships.

#### Scenario: Worker dies after a partially accepted route
- **GIVEN** a fixed route requests 1,000 wood and durable engine receipts confirm 600 wood was dispatched
- **WHEN** the exact account is reauthenticated and its managed task is absent
- **THEN** the restored job MAY dispatch at most 400 further wood, without repeating the confirmed 600

#### Scenario: A shipment POST may have reached the server
- **GIVEN** the private journal contains a pending but unconfirmed outbound chunk
- **WHEN** session rotation or worker death triggers automatic restoration
- **THEN** Daedalus MUST pause that fixed job for review and MUST NOT resend the uncertain chunk

#### Scenario: Fixed route recipient is no longer owned
- **GIVEN** a saved route's destination city is not in the reauthenticated player's current city list
- **WHEN** recovery checks the desired job
- **THEN** the job MUST remain in manual review without dispatching resources


### Requirement: Default-on verified session and safe-job recovery
A backend configured with fixed accounts, authenticated engine IPC, managed task control and existing-session monitoring MUST start its recovery supervisor by default. Newly configured, enabled accounts MUST default to five-minute delayed recovery and safe-job auto-resume, without requiring a manual per-account enable action. The system MUST preserve any explicitly saved disabled policy, indefinite or timed browser pause and account-identity binding. A host-wide opt-out MUST be available. Missing protected credentials, uncertain task receipts, unverified identities and absent prior managed sessions MUST NOT cause opportunistic login or game task replay.

#### Scenario: New enabled account uses default recovery
- **GIVEN** a fully configured monitored daemon and an enabled account without a prior policy row
- **WHEN** its recovery policy is read
- **THEN** both session recovery and eligible managed-job restoration SHALL be enabled with a 300-second grace period, without initiating any login

#### Scenario: Explicit disable persists through deployment
- **GIVEN** an account has a stored disabled recovery policy
- **WHEN** the service is upgraded or restarted
- **THEN** automatic recovery SHALL remain disabled for that account despite the new defaults

#### Scenario: Owner uses browser pause
- **GIVEN** recovery is enabled by default and the owner has paused the account
- **WHEN** a world session expires during the pause
- **THEN** the supervisor SHALL respect the pause and SHALL NOT reauthenticate early

#### Scenario: Host-wide recovery opt-out
- **GIVEN** an otherwise fully configured daemon
- **WHEN** the operator starts it with the explicit disable-auto-recovery flag
- **THEN** no automatic recovery supervisor SHALL be started

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

### Requirement: Recovery reservation preserves current policy and epoch
An automatic restoration reservation SHALL require the current restored account identity and recovery epoch, an enabled unpaused auto-resume policy, and no earlier unresolved reservation for the same logical job. Edits to unrelated policy fields SHALL NOT clear an explicit browser-use pause.

#### Scenario: A crash or policy change occurs while restoring
- **GIVEN** an approved job and an earlier unresolved recovery receipt, a disabled account, or a superseded recovery epoch
- **WHEN** the supervisor considers the job for automatic restoration
- **THEN** it SHALL not reserve a new dispatch; an unresolved receipt SHALL stay visible only to its original account identity and require operator reconciliation
