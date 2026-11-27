# Implementation checklist

- [x] Audit warehouse intent, upstream sender acceptance and existing recovery journal; define exact eligibility and migration exclusions.
- [x] Implement durable per-source bounded receipts and fresh reconciliation via existing upstream helpers; preserve no-replay rules.
- [x] Implement safe startup and reconnect restoration and completed/held outcomes, including stop/epoch fencing.
- [x] Expose eligibility and reasons before launch and in web/native recovery views.
- [ ] Test simulated multi-shipment restart, in-transit and arrived cargo, ambiguous write, legacy jobs, changed stock, stop/reconnect, upstream parity; document live acceptance.


## Implementation evidence

- Reuses the upstream transport executor and waits, and the durable fixed-transfer chunk journal. The approved source vector is immutable; there is no replay of pending or accepted-but-unobserved cargo. Receipt sums must match durable counters.
- Fresh owned cities, destination space net of incoming cargo, fleet availability and remaining original source caps constrain restored shipments. Cargo visibility is verified by origin and destination ownership/name; ambiguous observations hold the task.
- Startup honors the existing grace period, policy, accepted task receipt and account ownership. A legacy or uncertain job is never sufficient to initiate cold-start recovery. Overlapping managed transport work is deferred.
- Local tests: 97 focused transport/recovery tests previously passed; 81 tests passed after adding cold-start coverage (overlapping suites, not additive).
- Full CI, final client checks, and real game acceptance remain pending. No live shipment was performed. Do not archive or merge until the outstanding checks are resolved or explicitly deferred.

- Server-attested prelaunch eligibility now distinguishes disabled policy, missing saved login, paused recovery, unsupported allocation, missing supervisor and eligible checkpoints. Both clients validate the bounded reason. 82 focused Python tests, 98 web tests, TypeScript, targeted ESLint and Python lint pass; all 13 OpenSpec items validate strictly. Production browser regression also passed against the rebuilt app.
