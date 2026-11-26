# Consolidation disposition — 2026-11-26

Archived as superseded by the single engineering successor `finish-v010-engineering`, not as proof that unchecked tasks passed. Original task checkboxes remain unchanged. Codes are defined in [the reconciliation index](../../../../docs/V010-RECONCILIATION.md). V codes identify implementation or evidence already present for part/all of a historical task; where E or O also appears, the remaining portion is explicitly transferred. S identifies an obsolete sequencing requirement. No live acceptance is inferred.

| Original unchecked task (in order) | Disposition |
| --- | --- |
| 1. Add offline fault-injection reproducer: a real engine-shaped rotation/redirect must pause only its account; one timeout/5xx must not count as rotation. | V8; E4 |
| 2. Record a safe owner-supervised browser takeover on a disposable/approved account, with redacted timestamps only, before making a live-login assumption. | O3 |
| 3. Persist approved, secret-free configuration at managed task start; update desired state on explicit stop/edit/delete; reject malformed and secret-bearing payloads. | V8; E4 |
| 4. Build read-only import and explicit approval for legacy process-list/batch jobs with available config; never silently adopt unknown tasks. | E4 |
| 5. Add event-driven/verified session-rotation detection, distinguish unknown network errors from invalid credentials, and mark the account as blocked before more tasks dispatch. | V8; E4 |
| 6. Validate multi-account concurrency: one lost account does not block other accounts, and polling does not trigger ten simultaneous relogins. | E4 |
| 7. Integrate a single, isolated, bounded, noninteractive IkaBot lobby-token/loginLink flow under the existing authoritative lease, with global rate limits, retry budget and jitter; never use Mac-only sealed passwords on the server. | V8; E4 |
| 8. Validate exact game host/player and owner after refresh, then atomically swap/recreate the engine IPC worker; retain fence and fail closed if old IPC is uncertain. | V8; E4 |
| 9. On expired token, challenge, CAPTCHA/MFA, wrong identity, proxy outage or persistent rotation, stop retries safely and signal the existing Mac-assisted login fallback. | V8; E4 |
| 10. Handle crash before/after IPC launch, duplicated recovery signals, stopped task during grace, changed account identity, partial resume and rollback without duplicate work. | E4 |
| 11. Owner-supervised network trial: forcibly rotate the browser session during multiple partial dispatches and verify no resource is sent twice after a successful credential-based reconnect. | O3 |
| 12. Extend verified per-chunk receipt tracking to other fixed-quantity transfer modules and foreign destinations only if authoritative recipient/transaction evidence is available. | E4 |
| 13. Add typed, authenticated nonsecret recovery policy/status APIs and redacted audit endpoints; keep world credentials out of web/browser/Supabase. | V8; E4 |
| 14. Build Mac Accounts/Automations UI for grace countdown, browser pause, Resume now, all/selected-account enablement, desired vs running job counts and exception handling. | V8; E4 |
| 15. Add matching Next.js admin controls through the existing backend-for-frontend, disabled/offline-safe mutation UI and an accurate partial restoration report. | V8; E4 |
| 16. Provide operator notices (Needs attention, Token unavailable, Retry scheduled), configuration migration preview, and safe metrics for failures/rate limits. | E4 |
| 17. Run engine/UI/API security tests and OpenSpec strict validation, complete GitHub macOS/Linux/Windows CI, and build a new ad-hoc signed Mac artifact. | V3; E6 |
| 18. Test fake clock at 299s/300s, browser-use pause, duplicate events, ten accounts, invalid token, mismatched player, network flakiness, worker dying mid-recovery and task IPC timeout. | V8; E4 |
| 19. Verify full daemon restart retains desired jobs, preserves encrypted credential files and task receipts, and stays healthy with zero authenticated accounts. | E4; O4 |
| 20. Deploy default-on supervised recovery to the server after backup; validate health, protected storage, monitoring and credential availability without exposing secrets. | V3; E6; O3 |
| 21. Owner-supervised live test: one account, browser login rotation, five-minute grace, verified token-based re-login (if eligible), exact restoration of safe jobs, repeated browser pause and no duplicate tasks. | O3 |
| 22. Enable additional accounts only after the field test and review; reconcile spec deltas, update docs, archive change only when verified implementation tasks are checked. | V7; O3 |
