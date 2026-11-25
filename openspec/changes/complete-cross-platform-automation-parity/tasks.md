# Implementation tasks

All items are intentionally unchecked. A code editor or read-only placeholder is not a completed mutating operation. Track per-operation desktop/web/backend/test status in a machine-readable companion to capability-matrix.md.

## 0. Audit and coordination
- [ ] Run inspect_engine() on vendored source; enumerate all menu actions, @task registrations and interactive submenus; reconcile matrix and add CI drift check.
- [ ] Reconcile PR #95, active native-automation-workflows, redesign-macos-desktop-experience, apple-style-nextjs-web-control-center and delayed-session-reconnect-and-task-restoration; resolve overlapping specs without losing existing progress.
- [ ] Review current actual backend and website versions, feature flags, APIs, account scope, security and test status. Snapshot baseline with verified evidence.
- [ ] Agree shared operation manifests, DTO schema, version compatibility, UI control vocabulary, local-only exception policy, human-readable summaries and test fixtures. Split backend, desktop and web workstreams into parallel branches.

## 1. Shared backend/engine track (A)
- [ ] Implement versioned reviewed registry, typed draft schemas, dynamic capabilities and account-specific availability; generate/validate Python and TS contracts.
- [ ] Reuse and complete authoritative inventory endpoints; add external city/island search, capacity/ship/ETA, production, eligibility, combat plans, logs and admin status where needed.
- [ ] Implement scoped read-only prepare/preview with expiry/fingerprint, exact effect summary and live recheck; strict execution/one-shot receipts, idempotency, stop/recovery and no automatic replay on uncertainty.
- [ ] Implement missing interactive adapters per matrix (building, workers, reorder, donation, vacation, station, status/logs, notification/proxy/service/update/admin). Do not execute interactive CLI prompts or arbitrary code. Preserve secure local-only handoff.
- [ ] Implement multi-account independently prepared plan orchestration; validate all targets, exact receipts, limits, partial/uncertain outcome handling, restoration compatibility.
- [ ] Add per-operation backend/engine contract tests, negative authorization/scope/staleness tests, no-side-effect previews and synthetic fixtures; document API.

## 2. Parallel desktop track (B)
- [ ] Integrate #95 player-first selector and native-only settings; verify no JSON settings/import/override or raw ID fields in any automation surface.
- [ ] Consume shared operation contracts, dynamic catalog, account scopes and inventory invalidation; reuse native editors and compact Fluent layout.
- [ ] Transport/construction: complete own/external city selectors, quantities, capacity/ETA, queue/shortage and independently scoped batch preview/launch.
- [ ] Cities/research/faith/daily: full dedicated editor and eligibility review for every matrix row, including worker and reorder operations.
- [ ] Trade/military/mission: full live offers, donations, units, garrison, barbarian and piracy planners with validated previews.
- [ ] Monitoring/admin: native interval/filter controls, status/logs, service/proxy/notification/provider/version panels, controlled extension and secure session workflows.
- [ ] Implement unified review, receipt, stop/history/recovery, error/stale/loading and accessibility; add per-operation Qt tests and light/dark compact window/VoiceOver checks.

## 3. Parallel web track (C)
- [ ] Replace hardcoded inspector catalog with reviewed dynamic manifest; player-first account selector, current/selected/all and responsive Apple-inspired workspace; retain EN/RU translations.
- [ ] Add strict BFF per-operation typed schemas, role/account authorization, origin and request limits, server-only credentials, negative route and secret tests; no generic raw config executor.
- [ ] Transport/construction: actual city dropdowns, repeatable route/resource matrix, fleet/capacity/ETA, multi-building queue/shortage, per-account review and executable typed launch.
- [ ] Cities/research/faith/daily: real academy/tavern/wonder/shrine/reward and worker/building editors, not read-only inventory placeholders.
- [ ] Trade/military/mission: live quotes, offers, donations, units/garrison/barbarian/piracy forms, schedule and validated effect previews.
- [ ] Monitoring/admin: functional status/logs/alerts/map/service/provider/notification and controlled release panels; secure local-only session or extension boundary with guided handoff.
- [ ] Connect review, preview, launch, receipts, stop/history/recovery and independent batch scope; add unit/component and Playwright per-family tests, keyboard/mobile/desktop/light/dark/EN/RU accessibility checks.

## 4. Domain integration gates (A+B+C; each row in matrix checked individually)
- [ ] Transport and construction vertical slice passes shared fixtures + Qt + web E2E, including duplicate account names and real city selectors.
- [ ] City/research/faith/daily slice complete across both clients and backend.
- [ ] Resource trade/donation and military/mission slice complete across both clients and backend.
- [ ] Monitoring, system and interactive/admin slice complete; security exceptions explicit, justified and owner-approved.
- [ ] Registry coverage gate: every menu/@task/submenu row maps to native desktop and web workflows (or approved secure equivalent), typed contract, test and completion evidence; no unimplemented mutating placeholders or JSON escape hatch.

## 5. Verification, release and closure
- [ ] Run Ruff, full pytest incl. engine and offscreen Qt, web lint/typecheck/unit/build, Playwright, security scans and strict OpenSpec validation; fix failures.
- [ ] Verify native Mac bundle installation, responsive web accessibility, all-account operations, duplicate display names, session switching, offline/stale data and restoration regressions.
- [ ] Coordinate backend compatibility rollout, verified Vercel deployment, latest macOS DMG and rollback; report exact versions and links.
- [ ] Owner performs live account acceptance and approves any security-boundary exceptions; do not use live accounts automatically in CI.
- [ ] Update canonical specs, docs, operation matrix and releases; archive only after acceptance evidence, reconcile prior overlapping proposals.
