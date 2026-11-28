# Implementation checklist — v0.2.0 (not started)

## 1. Audit and contract
- [ ] Inventory every actual registry operation, upstream execution/wait/response boundary, existing receipts and supported observations; map metric definitions and explicit unavailable reasons in a machine-readable coverage manifest.
- [ ] Review identity, evidence semantics, status model, time accounting, proposed retention and security threat model; add ADR for telemetry-only separation and compatibility.
- [ ] Design web/native responsive layouts and localization keys; document examples as synthetic, not actual activity.

## 2. Backend foundation
- [ ] Implement private versioned logical task/run/event/projection schema, additive migrations, backups, quota/retention checkpoints and rollback; test disk full, corruption, interrupted migrations and pruned histories.
- [ ] Integrate reviewed launch/registration/stop and recovery bindings without changing authorization or replay policy; preserve logical identity across safe runs; fence stale epochs and conflicting identities.
- [ ] Implement bounded typed observation ingestion, sequence deduplication and gap handling; test concurrent duplicate events, crash at every commit boundary, lost IPC and invalid payloads.
- [ ] Implement evidence-aware metric and duration projection, deterministic rebuild, partial/unknown states, monotonic time and restart accounting; ensure failure cannot block or repeat engine dispatch.
- [ ] Implement scoped GET endpoints, bounded aggregate summaries, BFF allowlists, capability negotiation, pagination/filter validation, export safety, role/revocation/isolation and no-secret tests.

## 3. Domain instrumentation
- [ ] Warehouse fill and transport: route/resource/ship correlation, wait transitions, verified dispatch counts and quantity, explicit delivery unknown; use existing IkaBot helpers and receipts; reproduce multi-shipment test with synthetic game responses.
- [ ] Construction and recruitment: accepted vs completed, targets, per-building/per-unit batches, queue wait, observed resource costs; synthetic multi-round/recovery tests.
- [ ] Remaining supported operations: implement audited metrics per registry coverage, lifecycle-only or explicit unavailable where evidence missing; prove exact registry coverage.
- [ ] Verify upstream parity, no new gameplay requests or loops, no telemetry-driven retries, no broadened remote operation capability.

## 4. Clients
- [ ] Web Tasks navigation, scoped filters, summaries, cards/table, detail and expandable timeline, stats/config/runs/receipts, refresh/cursor/export, partial/unavailable states, responsive EN/RU dark/light and keyboard tests.
- [ ] Native Qt/Fluent Tasks monitor and detail parity with shared API, compact and normal desktop sizes, theme/accessibility, native localization policy.
- [ ] Preserve existing task-control/reconciliation actions and old backend compatibility; relocate existing world reports and technical receipt views without loss.
- [ ] Synthetic end-to-end UI/BFF/controller/IPC/journal tests; screenshots and accessibility QA; verify no sensitive persistent browser storage.

## 5. Release
- [ ] Full offline Python/engine/web/native CI, security, packaging and strict OpenSpec; exact-revision tests and source provenance. Document migration, retention, degradation, recovery, compatibility and rollback.
- [ ] Stage with feature flag disabled, test against synthetic state and approved read-only deployment checks; defer real game effects to owner acceptance and explicitly record results.
- [ ] Obtain v0.2.0 approval, align versions, publish/redeploy under existing release policy, archive only verified implementation work; keep manual acceptance separate.
