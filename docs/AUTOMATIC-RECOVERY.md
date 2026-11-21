# Delayed automatic session recovery

## Availability and safety

Daedalus implements **opt-in**, per-account automatic IkaBot reconnection with a default **300-second grace period after confirmed session loss**. The grace is not measured from when you open a second browser: the backend must first detect the invalidated world session (managed worker probes every ~30 seconds, requiring a corroborating negative check). The current five-minute existing-session monitor remains independent.

A new verified Gameforge lobby login can invalidate the browser session you are using at that moment. If you want more browser time, use **Pause for browser use** (15, 30, 60 minutes or indefinitely) before the recovery deadline; **Resume now** deliberately bypasses only the timer and still enforces every account and task safety gate. Reconnecting is not possible with only an expired world cookie. The server requires a protected, opt-in Gameforge **lobby token**, which may itself expire or require CAPTCHA/MFA.

**The program is not a second Gameforge client**: only the maintained IkaBot engine generates loginLink and performs game operations. The backend verifies the exact configured world/player through a fresh TLS game-world check and protected account-specific IPC before it marks recovery successful. Browser clients do not receive tokens or cookies, and the Mac's separately sealed login vault cannot be read by the server. If lobby authentication fails, the account remains disconnected for manual Mac-assisted login.

## Enablement

The backend service must be started with its ordinary fixed account/IPC/task/monitoring flags **plus** \`--enable-auto-recovery\`; no account is enabled by that server flag alone. This is deliberately not a replacement for the existing backend security token or the selected-account host-local lease.

Open Accounts → **Browser-friendly recovery** in the Next.js UI, or Accounts → **Automatic recovery** in the Mac app. For each account you explicitly authorize, first select **Import saved token** to copy its matching saved IkaBot lobby token into the existing encrypted *server* credential store. This is a local server-side exact account/world/player lookup (it neither sends credentials to the web browser nor logs into Ikariam). Import is rejected if no unique matching saved identity or token exists. Then choose **Enable recovery** or the bulk selected/all approval. Existing accounts default off and enabling never initiates an immediate login.

The Next.js dashboard shows recovery phases, confirmed loss time, countdown, pause state, credential availability, current session, and desired/restartable task counts. The Mac app provides the same actions with native confirmation dialogs. Both offer **Review saved jobs** and safe bulk enable/disable with per-account results.

Disabling the account policy cancels pending reconnection, not a game operation that was already committed.

## Jobs after reconnect

When a managed IkaBot task is launched through Daedalus, the controller now persists its validated, secret-free configuration as a **desired running job**, separate from the original durable task receipt. Stopping the task changes desired state to stopped *before* contacting a potentially unavailable old worker, so it is not unintentionally revived during the next recovery.

After the account has independently authenticated, the reconciler compares desired jobs to the current protected IPC task list and existing request receipts. It uses a fresh idempotency key, a per-recovery-epoch receipt, and atomic reservations to prevent duplicate launches. **Unknown or unconfirmed previous dispatches always block automatic restoration**.

The automatic restart allowlist is deliberately state-sensitive, based on each newly launched managed job's original approved engine configuration:

| Managed task | Auto-resume | Safety rule |
| --- | --- | --- |
| `alertAttacks` | Yes | Continual alert only; requires the verified worker and no active duplicate |
| `constructionList`, self-funded native plan without shipments | Yes, by target level | Read the actual building slots/levels, skip finished upgrades, wait for busy construction and obtain a fresh IkaBot plan for unfinished targets. Never replay original construction actions or shipments |
| `consolidateResources` (recurring source-retained-stock policy) | Yes | The engine recalculates excess above the retained source balance using fresh city resources, rather than replaying a fixed cargo total |
| `resourceTransportManager` (recurring `consolidate` with `keep` mode) | Yes | The engine recalculates excess above retained stock after checking the source cities are still owned. A new run may send newly generated excess earlier than the original interval |
| New Daedalus-managed `sendResources` fixed-quantity routes **between your own cities** | Yes, with durable receipts | Per route/resource, the engine reserves each cargo chunk in the private SQLite journal **before** sending; after IkaBot receives an explicit game acceptance, the journal adds the accepted quantity. After reconnect, it sends only the original target minus the accepted quantities. An unconfirmed POST is blocked, not guessed or sent again |
| `distributeResources`, fixed-amount / one-shot `resourceTransportManager`, `sendResources` to other players, construction with shipments | No, needs review | These other transfer implementations lack the new per-chunk journal and may have cargo in transit; never silently replay them |
| `research`, `tavernManager`, `donationBot`, `buyResources`, `sellResources` | No, needs review | These can issue repeated research, wine, donation and market actions |
| `attackBarbarians`, `autoBarbarians`, `autoPirate`, `trainArmy`, `UpgradeUnits` | No, needs review | Military orders and resource commitments may be in flight or irreversible |
| `activateMiracle`, `activateShrine`, `loginDaily` | No, needs review | Daily/cooldown and activation state needs authoritative reconciliation |
| `alertLowWine`, `searchForIslandSpaces`, `dumpWorld`, `webServer` | No, needs review | Runtime/notification and server-mode behavior still requires separate assurance |

Construction recovery is an absolute-state reconciliation: an already reached target is marked completed in the durable desired-job journal, a currently busy building is left alone, and missing resources defer the job for the next healthy supervisor poll. Only the existing IkaBot read-only planner may issue the new plan, and the engine validates the plan again before dispatch. Unknown or unconfirmed request receipts still block every automatic dispatch. Threshold transport is a continuing source-balance policy, not a fixed amount or a guaranteed original shipment schedule.

These task-specific classes apply when Daedalus captures the job configuration at a new managed start. Previously created manual-class entries are not silently promoted; review and reauthorize them once. Only **newly started** Daedalus-managed owned-city `sendResources` jobs receive the private fixed-transfer ID and write-ahead receipts. Earlier manually created jobs, tasks launched outside Daedalus, and external-destination shipments are still manual-only. A confirmed **dispatch** counts against the requested total even while the ships are travelling; the controller does not wait for arrival or try to deduce shipments from warehouse balances. If the game accepted a POST but the worker crashed before saving its acknowledgment, that specific chunk remains `pending` and the job reports **Needs review** instead of risking a duplicate delivery.
Legacy IkaBot tasks launched before Daedalus began capturing full configurations **cannot be reconstructed from the old request ledger** (only ID/name/hash are stored), nor from the current managed IPC task listing (which does not return configuration). Those jobs need a one-time reviewed configuration import or manual recreation. No missing data are invented.

## Fixed-quantity transfer recovery contract

Example: you approve 1,000 wood from City A to City B. If IkaBot has confirmed that 600 wood was dispatched before the world session rotates, a later verified recovery will dispatch **only the remaining 400 wood**. Confirmation is recorded for individual transport-ship batches, not only the whole route, so several partial batches are supported. Already accepted cargo is never sent a second time by the resumed job. For multi-resource and multi-route plans, totals are tracked independently for each route and each of the five resource types.

- The original resource targets, source/destination city IDs, worker identity and a server-generated UUID are recorded before the first engine task launch. The controller and engine use the same owner-only SQLite file, connected by a server-side environment variable, never an API-supplied filesystem path.
- Before each mutating IkaBot transport POST, a transaction records the exact outgoing cargo as **pending**. After the known successful server response (`type == 10`), an atomic transaction increments accepted cargo and marks the pending receipt confirmed. A definitive server refusal (`type == 11`) marks it rejected without incrementing cargo.
- A lost response, process kill, malformed reply, conflicting identity, changed recipient ownership, unknown worker, or checkpoint corruption cannot be assumed safe: automatic dispatch pauses. Resource balances and the military advisor's movement list do not expose a reliable per-shipment cargo receipt, so they are **not** used as substitutes for the write-ahead journal.
- If every target quantity is already confirmed as dispatched, the job is marked **Completed**. If only some were dispatched and none are uncertain, the resumed engine reloads the journal and sends the remaining cargo. User-requested Stop fences future pending sends.
- This release does **not** automatically upgrade historic `sendResources` jobs with missing checkpoint IDs. Review and recreate the old job once if you want this new recovery behavior.

**Operational caveat:** Only verified `sendResources` tasks running in a Daedalus-managed engine process with the same protected journal can use these receipts. The initial recovery rollout is still opt-in and requires owner-supervised game testing before general deployment.

## Rollout/acceptance

Synthetic tests cover the 299/300-second boundary, restart-safe grace, account-scoped policy, browser pause, stale session handling, protected lobby token import with fake registry, no-replay receipts, token failure, UI and API access control, and no duplicate managed task starts. A fresh IkaBot **lobby-token loginLink** after real browser takeover **has not been tested live**, so do not claim it will always work; the token may have expired or require renewed browser assistance.

Production rollout is **disabled for all accounts by default**, even if a server supervisor process is running. Start with one low-risk account and an approved test automation, verify grace, reconnect, and job single-instance behavior, and then enable further accounts. The OpenSpec change stays active until the remaining task-specific adapters and owner-operated acceptance tests pass.

The SQLite journal is stored privately at \`~/.local/state/daedalus/recovery.sqlite3\` with owner-only access, separate from \`task-requests.sqlite3\`. Keep both protected stores and IkaBot credential files in backups. Never delete the old ledger or publish a raw token to a browser, logs or CI.
