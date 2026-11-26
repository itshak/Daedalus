# Design: delayed session recovery with verified desired-state task reconciliation

## Evidence from the current implementation (2026-11-21)

| Component | Observed source behavior | Design consequence |
| --- | --- | --- |
| Upstream engine: ikabot/web/session.py | __isSessionRotated and __printSessionRotated detect a lobby redirect/reload; __closeIkabot may terminate the account's tasks/processes. __isSessionAlive returns None on indeterminate network errors. | Treat rotation as a loss signal, not a recoverable live requests.Session. Make the supervisor independent of that terminating process. |
| Daedalus: session_monitor.py | ExistingSessionRecoveryMonitor defaults to a 300-second polling interval and marks an owned invalid session as requiring assistance. It never auto logs in or starts a job. | Add an opt-in supervisor, not an implicit change to manual recovery. Detection delay and grace delay are distinct. |
| Daedalus: saved_worker.py | SavedCookieWorker.start uses exact saved **world cookie**, cookies_only=True, verifying identity, and fails closed if it expires. An authenticated owner lease must be held. | An invalidated world cookie cannot be assumed sufficient to establish a new session. |
| Maintained IkaBot: Session.from_saved | cookies_only=False may validate a cached Gameforge lobby token and, if needed, request a fresh lobby loginLink through the existing engine. That path can rotate a browser session and may depend on blackbox/challenge availability. | Investigate one supervised, noninteractive engine-provided refresh; never promise that an old token always works. |
| Daedalus: task_control.py | TaskLedger contains account ID, request ID, task name, payload hash, status, managed task ID and PID; it **does not store task configuration**. Unconfirmed/dispatching blocks new task starts. | Create a separate durable desired-state journal and preserve the existing no-replay receipt semantics. |
| Maintained engine: helpers/ipc.py | Managed task list returns task, process ID and status, but not config. Process-list and manually saved task-batch configurations may exist locally and contain sensitive fields. | Capture configs at original authorized start; importing legacy jobs is local review-only, never inferred from PID or public API responses. |
| Live daemon status | 10 accounts configured; 0 authenticated workers at inspection. | No live browser-takeover/reconnect claim is possible yet. Owner field acceptance is mandatory. |

The source review is supported by an existing offline regression run: 39 tests passed across session monitoring, saved worker, and task control. This validates the **current no-replay contract**, not the future recovery implementation.

## Operational timeline

- Healthy: read-only validity checks and engine event hooks confirm the session remains bound to the configured player.
- Suspect: one ambiguous timeout, 5xx response, or malformed response must not be called a takeover. A positive rotation signal (known lobby redirect/reload or two independent invalid read-only probes) becomes **confirmed lost**. Capture both a monotonic countdown anchor and persisted UTC event/deadline; retain the account lease and block any new game action.
- Browser grace: hold for **300 seconds from confirmed loss** (default; 60–3600 seconds configurable later). The backend SHALL NOT call lobby loginLink, start a worker or restart tasks during that window. It remains observable to clients.
- Explicit browser-use pause: the owner may extend the buffer before or during it, indefinitely if requested. A paused account never reconnects until the timer expires or the owner resumes it.
- Restore: after the deadline, check policy enabled, identity/lease ownership, absence of competing worker, absence of unresolved task receipts, credentials availability, retry budget and backend version. Prefer a newly valid saved world cookie (read-only validation); otherwise permit exactly one bounded trusted engine lobby-login attempt if a protected lobby token has been provisioned.
- Verify: independently attest HTTPS world endpoint, expected world/player, valid session cookie, IPC identity and same authoritative lease. Only after passing all checks set phase to authenticated.
- Reconcile: read live managed tasks under the new worker epoch. Match each persisted desired-task identity/config digest. Start only eligible and known-absent tasks using a *fresh* UUIDv4 and durable transaction/receipt. Do not use an old request ID, replay an uncertain IPC request or assume PID persistence.
- Outcome: report **Restored**, **Partially restored**, **Needs attention**, **Paused for browser**, or **Retry scheduled**, with per-job reasons. Never claim restored before observing a running engine task.

Default monitor polling today is 300 seconds. The rollout MAY use faster low-impact event-driven detection for opted-in accounts, but the **five-minute buffer starts after loss is confirmed**, not after browser login itself. UI should show the detection timestamp separately from the reconnect deadline.

## Proposed state machine

~~~text
Authenticated ──rotation evidence──> Suspected loss
                                     │ verified negative
                                     v
                              Browser grace (300s)
                                     │   ├─ owner browser pause -> Paused
                                     │   └─ explicit Resume now -> Confirm + recover
                                     v
                           Reconnect preflight
                         /    |          |        \
                 no token  busy lease  uncertain  safe
                    |         |          |         |
                   Needs attention       |        Reauth
                              <-----------          |
                                       wrong player ├─> Needs attention
                                                    v
                                             Verified IPC owner
                                                    |
                                             Task reconciliation
                                                    |
                                       Restored / Partial / Attention
~~~

Each transition persists a sanitized event with account ID, phase, correlation ID, epoch and timestamps, **never** session cookies, refresh tokens, credentials, Gameforge loginLink URLs or game HTML.

## Durable state and transaction model

Add a private SQLite store (mode 0600; directory 0700) outside the checkout, separate from existing task-requests.sqlite3:

- recovery_policy: account_id; enabled; grace_seconds (default 300); browser_pause_until/indefinite; auto_resume_enabled; policy_revision; updated_at; approved_by; approved_at. **Updated policy (2026-11-21):** newly configured, enabled accounts default to session recovery and safe-job restoration ON if a monitored-task-control backend is configured. Explicit persisted OFF policies and browser pauses take precedence; changed world/player identities fail closed. Account-wide bulk disable remains available.
- recovery_attempt: account_id; event/epoch; confirmed_lost_at; next_allowed_at; attempts; last_failure_code; status; lock/fence generation; timestamps. On restart use persisted timestamp conservatively—never accidentally shorten the grace after clock jumps.
- desired_task: logical ID; account/world/player identity fingerprint; built-in task type; validated **secret-free** canonical config JSON and digest; policy_revision; desired_state ("running"/"stopped"); restart_class; source ("managed"/"reviewed_legacy"); approved_at; worker_generation; last_known task ID; last_launch_request ID; timestamps. Task configs require the existing schema and a bounded allowlist, not arbitrary Python or external URLs.
- resume_receipt: logical desired_task ID; recovery epoch; fresh request ID; status ("reserved"/"dispatching"/"started"/"verified_running"/"rejected"/"unconfirmed"/"skipped"); observed engine task ID; timestamps. Unique (account, logical ID, epoch), with a durable atomic reservation/fence before the IPC call.
- redacted recovery_audit: account, event, phase, reason code, counts, timestamps and actor. Secrets never enter audit or API responses.

Do not store Gameforge tokens in the desired-job database. Store permitted lobby credentials only via already approved host-encrypted credential storage; Mac-bound encrypted vaults are not server-decryptable.

Any new user stop/remove/edit immediately updates desired_state and policy_revision, invalidates pending reconnect dispatch, and remains stopped after the next session recovery.

## Task eligibility, duplication and migration

The owner's desired outcome is **the same running set of automations**, not blind re-execution of old game actions.

- Classify each built-in IkaBot background task by semantics: **continuous and safely restartable**, **requires game-state reconciliation before resume**, or **manual-only/non-idempotent**. The capability audit explicitly covers construction, transports, fleets, purchases, attacks, notifications and time-windowed tasks.
- For the first two classes, an owner may approve durable auto-resume once. A reconciler compares desired vs observed tasks and relevant live game state; only one task per logical desired ID may run in a worker generation. For a known one-shot game operation, use state-specific reconciliation or leave paused for explicit approval.
- Persist full validated configs **when a managed task is first approved**. The current ledger cannot reconstruct them. For currently running legacy IkaBot jobs, offer a local-only, redacted import/review from the actual process list or explicitly saved batch files if available; unknown/missing config remains **Needs review** rather than inventing values.
- On rotation the upstream task process may already be killed. Recovery must tolerate an absent IPC endpoint without mistaking it for a safe start. Guard against two independent backends and against parent/child process group termination.
- Keep existing TaskLedger and engine IPC deduplication unchanged; a new **resume** is a distinct, explicitly preauthorized policy reconciliation with a fresh request ID, and only after all prior starts are known/reconciled. A timeout after dispatch is **unconfirmed** and halts further dispatch for that account pending manual resolution.
- No automatic restart of unmanaged arbitrary processes, generic Python jobs, or operations whose in-flight side effects cannot be verified.

## Implemented fixed-quantity shipment continuation (2026-11-21)

This part of the earlier design is now implemented for **new Daedalus-managed `sendResources` jobs from one owned city to another owned city**. All other one-shot resource transfer modules, historic jobs without recorded IDs, and external recipients remain excluded from automatic restart.

- Schema v2 adds `fixed_transfers` (identity/world/player; immutable normalized route/resource targets; acknowledged per-route/per-resource vectors; status) and `fixed_transfer_chunks` (per-batch route index, cargo vector, pending/confirmed/rejected receipt and timestamp) in the existing mode-0600 recovery database. V1 upgrades in place without discarding desired jobs or receipts.
- Before the original IPC launch, the backend assigns its own UUID4 fixed transfer ID, atomically records a `dispatching` desired job and the immutable target, then creates its normal task-request receipt. The engine child inherits the authoritative journal path only from the trusted daemon environment.
- At every outgoing `sendGoods` POST, the IkaBot engine first reserves one pending batch. An explicit successful `type=10` response atomically commits its quantities, and an explicit `type=11` non-dispatch marks the reservation rejected. Malformed/unknown/lost replies and process death leave the pending batch unresolved.
- During recovery, the original routes remain the authority. The controller checks a verified worker, exact world/player and current ownership of **both** route endpoints; checks for pending dispatches; and resumes by passing the original approved config and ID. The engine reads authoritative acknowledged vectors and sends only `target - dispatched`, never trusting the browser, cached resource stock, or a guessed transport movement.
- If every cargo vector equals the original targets, the desired job is completed without sending. A user stop fences future sends. Missing/corrupt checkpoints, non-owned destinations, two same-task active plans or an uncertain prior request remain blocked.
- A dispatched shipment is counted even while in transit; arrival is not mistaken for sending it again. There is a narrow unavoidable uncertainty window after a game's successful POST but before a local acknowledgment is persisted. Without a reliable game-provided cargo transaction ID, the correct result there is **Needs review**, not automatic retransmission.

Operator status exposes aggregate dispatched/remaining resource vectors and uncertainty flags through the authenticated API and Next.js panel; no cookies, session HTML or login tokens are added. Synthetic tests are not a substitute for an owner-supervised game trial.

## Reconnection credentials and process isolation

1. Before any recovery attempt, check whether a server-usable, encrypted **lobby credential** is configured for the exact identity. Default-enabled policy grants no credential access or new login by itself. A valid world cookie alone does not count. Do not assume a Mac Keychain/GF password is on the server.
2. Prefer trusted IkaBot engine primitives; run the potentially blocking lobby flow in a supervisor-owned process with bounded network timeouts and killable descendants. Do not invoke UI Selenium or pull browser secrets via the desktop/web API.
3. Refresh attempts must hold the canonical world/player lock, validate the exact lobby account mapping and independently attest game world/player. A single global refresh slot (across the 10 accounts), per-account fence and jitter prevent login storms.
4. Respect challenge/MFA/CAPTCHA responses. Never auto-bypass or loop; surface **Sign in on Mac required** and allow existing encrypted human handoff.
5. Retry policy: no retries before the 300s grace; at most three automatic login attempts per account per hour and six per day; on transient error back off 5, then 15, then 60 minutes with jitter; stop entirely on credentials rejected, account mismatch, repeated rotation, manual pause or unsafe task receipts. UI shows deadline and attempt count.
6. No probes are guaranteed to tell if a human is *still browsing* on another device. Explain that the default auto-reconnect may invalidate a browser session after grace. The prominent pause toggle provides a cooperative solution.

## API and UI contract

Behind current bearer authentication and server-only web gateway:

- Read-only account recovery summary: phase, confirmed-lost time, reconnect deadline, pause mode, authorized credential availability boolean, eligible/blocked desired-task counts, last attempt reason, next retry, recovery epoch. No secrets.
- Scoped policy review/save with explicit confirmation; user can select one/selected/all accounts with per-account conflict preview. Changes carry a policy revision and authorization; bulk operations are individually reported.
- Actions: **Pause for browser use**, **Resume now** (explicitly acknowledges it may log out the browser), **Disable auto recovery**, **Review jobs**, **Retry after fixing credentials**, and **Acknowledge uncertain receipt** with existing manual safety checks.
- Tasks view: persistent **Desired / Running / Needs review** grouping; each job shows original config in proper structured editor, eligibility category, last known worker task, restore receipt, and reason for skipping. No generic JSON form.
- Desktop and web pages share the same API state. UI can refresh without keeping a local automation loop alive. PWA must not cache secret game data or dispatch actions offline.

## Safety/rollout

- Stage 1: add read-only diagnostics and synthetic rotation simulations; no authenticated login side effects.
- Stage 2: persist new desired-task policies, guarded task journal, management UI, migration previews; new enabled accounts default on, but no automatic login without confirmed loss and protected credentials.
- Stage 3: implement one-account refresh supervisor, strict token/lease/identity controls and 300-second delay; existing explicit off policies always take precedence.
- Stage 4: add verified restart-class allowlist, reconciler, receipts and bulk status; safe-job auto-resume is default-enabled for active accounts but still requires exact state reconciliation.
- Stage 5: integration/CI, forced-crash/clock/IPC fault injection, macOS package, staged server deployment and operator acceptance on one low-risk account before bulk opt-in.
- Rollback: disable policies, stop the supervisor safely without killing verified user-owned tasks, retain the old durable journal and server credentials, keep the API healthy even with zero verified workers, and never transform an uncertain start into "not running".

No change to actual Gameforge sessions, engine tasks, deployment, account configuration or stored credentials is part of this **planning** PR.
