# Implementation checklist

- [x] Audit warehouse intent, upstream sender acceptance and existing recovery journal; define exact eligibility and migration exclusions.
- [x] Implement durable per-source bounded receipts and fresh reconciliation via existing upstream helpers; preserve no-replay rules.
- [x] Implement safe startup and reconnect restoration and completed/held outcomes, including stop/epoch fencing.
- [x] Expose eligibility and reasons before launch and in web/native recovery views.
- [x] Test simulated multi-shipment restart, in-transit and arrived cargo, ambiguous write, legacy jobs, changed stock, stop/reconnect and upstream parity; document separate live acceptance.
- [ ] Verify complete CI on final combined revision.
- [ ] Verify real-game multi-shipment recovery, cargo attribution, capacity and live acceptance (unperformed).


## Implementation evidence

- Reuses the upstream transport executor and waits, and the durable fixed-transfer chunk journal. The approved source vector is immutable; there is no replay of pending or accepted-but-unobserved cargo. Receipt sums must match durable counters.
- Fresh owned cities, destination space net of incoming cargo, fleet availability and remaining original source caps constrain restored shipments. Cargo visibility is verified by origin and destination ownership/name; ambiguous observations hold the task.
- Startup honors the existing grace period, policy, accepted task receipt and account ownership. A legacy or uncertain job is never sufficient to initiate cold-start recovery. Overlapping managed transport work is deferred.
- Local tests: 97 focused transport/recovery tests previously passed; 81 tests passed after adding cold-start coverage (overlapping suites, not additive).
- Full CI, final client checks, and real game acceptance remain pending. No live shipment was performed. Do not archive or merge until the outstanding checks are resolved or explicitly deferred.

- Server-attested prelaunch eligibility now distinguishes disabled policy, missing saved login, paused recovery, unsupported allocation, missing supervisor and eligible checkpoints. Both clients validate the bounded reason. 82 focused Python tests, 98 web tests, TypeScript, targeted ESLint and Python lint pass; all 13 OpenSpec items validate strictly. Production browser regression also passed against the rebuilt app.

- CI on f434746 passed engine/web/build/security but failed the controller matrix on an external-shipment test fixture missing the new task-list read and missing active-change status documentation. Both regressions are corrected. Warehouse terminal observations now persist across job revisions, previously verified completed jobs are retired before duplicate matching, a no-fleet preview reports its specific hold reason, and ordinary fixed-transfer execution cannot use a warehouse checkpoint. 94 focused controller, engine, shipment and hygiene tests and repository lint passed. Fresh full CI and live acceptance remain outstanding.

- Engine fixture updated to reflect the real ledger schema: 33 combined fixed-transfer and warehouse tests pass. A synthetic world exercises real upstream multi-load waiting and protected POST with both legacy and durable checkpoint paths, including process interruption after one verified shipment and arrival during downtime; restored execution sends exactly the remaining 200 units, never the original 300. Final storage-budget exhaustion now records terminal capacity even when source stock ends on the same load. Recovery summaries exclude uncertain and terminal warehouse work from automatically restartable counts; unresolved warehouse cargo fences all automatic transport restoration, without stopping unrelated alerts. Completed jobs settle on authoritative task-list reads as well as on reconnect. 124 focused controller/engine/API/hygiene regressions plus the separate new fence regression pass. Full final-head CI and real-game acceptance remain separate gates.

- Final fast-completion race regression: task-list reads cannot retire an intent while its restoration receipt is dispatching or unconfirmed. A verified instant completion records the successful engine launch first and then persists the terminal capacity/intent state without a spurious stop. A later local retirement failure cannot rewrite an already durable launch as uncertain. 78 focused task/recovery/fill tests passed.
