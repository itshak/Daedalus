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

The initial **automatic restart allowlist is intentionally narrow**:

| Managed background task | Auto-restart | Reason |
| --- | --- | --- |
| \`alertAttacks\` | Allowed after verified worker and no active duplicate | Periodic alert/monitor rather than an immediate one-shot game purchase, build or attack; still requires IkaBot notification prerequisites |
| \`alertLowWine\`, \`searchForIslandSpaces\`, \`dumpWorld\`, \`webServer\` | Manual review | Periodic scans and server-mode behaviors need separate runtime/input/output assurance before enabling |
| \`constructionList\`, \`research\`, \`tavernManager\`, \`resourceTransportManager\`, \`distributeResources\`, \`consolidateResources\`, \`sendResources\`, \`donationBot\`, \`buyResources\`, \`sellResources\` | Manual review | Can issue repeated buildings, resources, research, transport or market mutations |
| \`attackBarbarians\`, \`autoBarbarians\`, \`autoPirate\`, \`trainArmy\`, \`UpgradeUnits\` | Manual review | Military orders and resource commitments may be in flight or irreversible |
| \`activateMiracle\`, \`activateShrine\`, \`loginDaily\` | Manual review | Daily/cooldown and activation semantics require current-game-state reconciliation |

This list includes all 23 currently catalogued upstream background tasks. For tasks not yet audited as repeat-safe, Daedalus **preserves the desired configuration** and displays **Needs review** rather than silently re-running a game action. A stopped/manual-only job can be restarted by a new explicit action and fresh preflight after checking game state.

Legacy IkaBot tasks launched before Daedalus began capturing full configurations **cannot be reconstructed from the old request ledger** (only ID/name/hash are stored), nor from the current managed IPC task listing (which does not return configuration). Those jobs need a one-time reviewed configuration import or manual recreation. No missing data are invented.

## Rollout/acceptance

Synthetic tests cover the 299/300-second boundary, restart-safe grace, account-scoped policy, browser pause, stale session handling, protected lobby token import with fake registry, no-replay receipts, token failure, UI and API access control, and no duplicate managed task starts. A fresh IkaBot **lobby-token loginLink** after real browser takeover **has not been tested live**, so do not claim it will always work; the token may have expired or require renewed browser assistance.

Production rollout is **disabled for all accounts by default**, even if a server supervisor process is running. Start with one low-risk account and an approved test automation, verify grace, reconnect, and job single-instance behavior, and then enable further accounts. The OpenSpec change stays active until the remaining task-specific adapters and owner-operated acceptance tests pass.

The SQLite journal is stored privately at \`~/.local/state/daedalus/recovery.sqlite3\` with owner-only access, separate from \`task-requests.sqlite3\`. Keep both protected stores and IkaBot credential files in backups. Never delete the old ledger or publish a raw token to a browser, logs or CI.
