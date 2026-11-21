# Implementation plan: delayed session reconnection and task restoration

Implementation is in progress: the private policy/configuration journal, protected token import,
host-only opt-in supervisor, cautious continuous-task reconciliation, and Mac/web controls
are implemented and offline-tested. This is NOT field acceptance or a claim that all
legacy or state-changing tasks can be automatically replayed.

## 0. Verify problem and baseline

- [x] Trace upstream IkaBot session rotation and account-scoped process exit; review cookie-only vs lobby-token login primitives without reading tokens.
- [x] Trace Daedalus session monitor, owner lease, task ledger and engine IPC task-list limitations; run existing synthetic safety regression (39 passing).
- [ ] Add offline fault-injection reproducer: a real engine-shaped rotation/redirect must pause only its account; one timeout/5xx must not count as rotation.
- [ ] Record a safe owner-supervised browser takeover on a disposable/approved account, with redacted timestamps only, before making a live-login assumption.

## 1. Durable opt-in policy and desired-job state

- [x] Define versioned schemas, migrations, private SQLite ownership and backup/rollback; existing accounts disabled by default and current task ledger preserved.
- [ ] Persist approved, secret-free configuration at managed task start; update desired state on explicit stop/edit/delete; reject malformed and secret-bearing payloads.
- [x] Add per-task restartability audit for every built-in background task, including non-idempotent construction, resource transfers, military actions and queued jobs; document why each is restartable, reconcilable, or manual-only.
- [ ] Build read-only import and explicit approval for legacy process-list/batch jobs with available config; never silently adopt unknown tasks.

## 2. Detection, five-minute grace and browser-use pause

- [ ] Add event-driven/verified session-rotation detection, distinguish unknown network errors from invalid credentials, and mark the account as blocked before more tasks dispatch.
- [x] Persist confirmed loss and enforce a 300-second grace anchored to that event; restart and clock-jump tests MUST never shorten it.
- [x] Add owner-visible browser-use pause (15/30/60 min or until resumed), Resume now, configurable per-account grace and approved all/selected-account policy controls.
- [ ] Validate multi-account concurrency: one lost account does not block other accounts, and polling does not trigger ten simultaneous relogins.

## 3. Trusted credential refresh and worker recovery

- [x] Design explicit host-encrypted server lobby credential provisioning; verify exact world/player mapping without reading, printing or transmitting token values.
- [ ] Integrate a single, isolated, bounded, noninteractive IkaBot lobby-token/loginLink flow under the existing authoritative lease, with global rate limits, retry budget and jitter; never use Mac-only sealed passwords on the server.
- [ ] Validate exact game host/player and owner after refresh, then atomically swap/recreate the engine IPC worker; retain fence and fail closed if old IPC is uncertain.
- [ ] On expired token, challenge, CAPTCHA/MFA, wrong identity, proxy outage or persistent rotation, stop retries safely and signal the existing Mac-assisted login fallback.

## 4. Fenced task reconciliation

- [x] Introduce worker epoch, logical task identity, versioned desired configuration, durable per-epoch resume receipt and unique atomic reservations.
- [x] Reconcile live managed tasks; only approved, absent continuous or verified target-state/retained-stock jobs can restart with fresh idempotency keys. The construction planner reads actual remaining building levels; fixed-amount and in-flight shipments still need receipts.
- [x] Keep manual gate for unknown or one-shot side effects, in-flight work, missing config and dispatching/unconfirmed task receipts; never replay a previous ambiguous request.
- [ ] Handle crash before/after IPC launch, duplicated recovery signals, stopped task during grace, changed account identity, partial resume and rollback without duplicate work.

## 5. UI/API and diagnostics

- [ ] Add typed, authenticated nonsecret recovery policy/status APIs and redacted audit endpoints; keep world credentials out of web/browser/Supabase.
- [ ] Build Mac Accounts/Automations UI for grace countdown, browser pause, Resume now, all/selected-account enablement, desired vs running job counts and exception handling.
- [ ] Add matching Next.js admin controls through the existing backend-for-frontend, disabled/offline-safe mutation UI and an accurate partial restoration report.
- [ ] Provide operator notices (Needs attention, Token unavailable, Retry scheduled), configuration migration preview, and safe metrics for failures/rate limits.

## 6. Verification, rollout and acceptance

- [ ] Run engine/UI/API security tests and OpenSpec strict validation, complete GitHub macOS/Linux/Windows CI, and build a new ad-hoc signed Mac artifact.
- [ ] Test fake clock at 299s/300s, browser-use pause, duplicate events, ten accounts, invalid token, mismatched player, network flakiness, worker dying mid-recovery and task IPC timeout.
- [ ] Verify full daemon restart retains desired jobs, preserves encrypted credential files and task receipts, and stays healthy with zero authenticated accounts.
- [ ] Deploy disabled-by-default to the server after backup; validate health, protected storage, monitoring and optional token availability without exposing secrets.
- [ ] Owner-supervised live test: one account, browser login rotation, five-minute grace, verified token-based re-login (if eligible), exact restoration of safe jobs, repeated browser pause and no duplicate tasks.
- [ ] Enable additional accounts only after the field test and review; reconcile spec deltas, update docs, archive change only when verified implementation tasks are checked.

**Not production approved.** The implementation is staged off by default. Remaining unchecked
items include true multi-account/legacy engine cutover, a reviewed import for older
untracked jobs, engine-specific restore adapters for state-changing tasks,
complete reason-code telemetry, CI/rollout and operator-supervised real
Gameforge browser takeover with a previously authorized account.
