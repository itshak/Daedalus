# Change: Delayed Gameforge session reconnection and desired-task restoration

## Why

An Ikariam browser login on another device can rotate the game-world session held by an IkaBot worker. The maintained upstream engine explicitly detects such rotation and may close the affected worker and its account-scoped tasks. Daedalus currently marks a monitored session as requiring assistance; it intentionally neither obtains a fresh world session nor replays tasks. The existing durable task-request ledger stores fingerprints/receipts but **not task configurations** and is not a restoration plan.

The owner wants to use the ordinary Ikariam website temporarily, then have Daedalus recover the corresponding account in the background **five minutes after a confirmed loss** and restore its prior, safely restartable running automations without reconstructing each job manually.

## Desired behavior

1. An owner explicitly enables **Auto reconnect and restore jobs** for one, selected, or all configured accounts. The account policy defaults to a **300-second grace period** measured from confirmed loss, not from the last healthy sample or a generic network timeout. Enablement is a durable, revocable consent to this narrowly scoped future action.
2. An independently confirmed session rotation marks that account as **Browser grace period**; task dispatch freezes immediately, the desired ongoing task set remains durable, and the supervisor does **not** log in for at least five minutes.
3. After the grace period, a **single authoritative, host-local supervisor** may attempt one bounded, noninteractive Gameforge lobby-to-world restore using an already-authorized protected credential, if one is actually available. It must use the maintained IkaBot engine, not a second game client or remote HTTP credential exchange, and verify the exact world/player via a fresh server-side attestation before publishing a worker.
4. Only then may a task reconciler restore preauthorized, restart-safe desired jobs that are demonstrably not running. Each restoration is a new fenced launch with a fresh durable idempotency key; an uncertain/duplicate/one-shot operation is never blindly replayed.
5. If the owner is still in the game browser at the five-minute mark, Daedalus **cannot reliably infer browser activity** from an expired worker cookie. Offer **Pause for browser use** (15/30/60 minutes or until resumed), **Resume now**, and policy timing/status in Mac and web control centers. An unattended retry could invalidate an active browser session; explain this before enablement.
6. Token invalid/expired, CAPTCHA/MFA, wrong identity, busy lease, task ambiguity, or repeated browser takeovers yield an explicit **Needs attention / Paused** state and bounded retries, never an infinite login loop or task storm.

## Scope

- Backend recovery supervisor with per-account state machine, durable timing, process/lease fencing, bounded detection, and audit.
- Protected server-side refresh credential policy. Existing Mac-bound sealed login vaults and desktop Selenium remain local-only and **do not imply** unattended server-side login capability.
- Durable, versioned **desired task** configurations for managed background automations; precise restart eligibility and live/ledger reconciliation. Review-only import for legacy IkaBot tasks without already trusted configurations.
- Authenticated status/policy/recovery APIs; Mac Accounts/Automations status, bulk scope, and web control-center equivalents behind the existing secure gateway.
- Offline synthetic tests, CI and explicit owner-operated game acceptance; safe migration and rollback.

## Non-goals

- Keeping game and independent browser sessions simultaneously authenticated, overriding Gameforge's session policy, bypassing CAPTCHA/MFA, using an untrusted raw token from a browser/API, replaying a known-uncertain game action, restarting all one-shot operations, importing arbitrary custom Python tasks, exposing session material in web UI/Supabase, or claiming that a still-valid lobby token is already verified in production.
- Auto-enabling the policy for existing accounts without an owner's approval; running real game login or game tasks during this planning change.

## Success criteria

- A configured account that loses its world session while the owner uses the browser is marked as disconnected, its known desired jobs are preserved, **no reconnection starts during the configured 300-second grace**, and a valid noninteractive protected login credential can restore an exact verified worker once the grace expires.
- An approved set of safely repeatable, continuously running tasks returns to a single active instance each; duplicate, uncertain, missing-configuration, and nonrestartable jobs are visibly withheld with reasons.
- A user can put an account in **browser-use pause** or explicitly select **Resume now**; account isolation and background processing survive API restart and do not block other accounts.
- Validation includes offline fault injection (time, token loss, rotation, shutdown, ambiguous receipts) and owner-supervised browser-login/live-task tests before production enablement.

**Planning only.** No automatic login, job restoration, task dispatch, daemon change, account policy or production cutover is implemented by this proposal. The implementation tasks remain unchecked.
