# Implementation checklist

- [ ] Audit upstream slider, citizen, overcharge semantics and safe authoritative readback; test unknown data and exact-count representability.
- [x] Build scoped read-only production inventory and city/resource discovery via existing helpers; explicit unavailable data.
- [x] Add exact/percentage/max reviewed planner and default priority vs available-only policy with donor before/after and staged fallback.
- [ ] Implement durable staged assignment, minimum release, authoritative readback, leftover restoration, compensation/recovery fencing and idempotency using upstream shared mutation helper.
- [ ] Implement reviewed resource-specific batch plans for all/selected accounts and cities; per-city result and partial failures, no unrelated assignments.
- [ ] Build Production web/native editors and bulk actions, academy/temple sections, default unchecked available-only checkbox and explicit review; translations/accessibility.
- [ ] Test sufficient/insufficient citizens, extra capacity, both resources, release-minimum and fallback, donor restoration, rejection/timeout/crash/readback mismatch, population changes, account scope, no science/temple changes, synthetic E2E and upstream parity.

## Initial implementation evidence (in progress)

- Existing IkaBot `getCityById` and `getCity` expose `freeCitizens` through
  `getFreeCitizens`; use that instead of another parser. Existing `getIsland`
  supplies the luxury code. `_read_worker_slider` exposes max_value, overcharge
  and optional value; do not infer current count or independent normal/extra
  allocation from those fields. Exact totals are supported by the policy;
  exact split and actual game slider/readback semantics need live evidence.
- Original interactive production waits 2 seconds between workerPlan writes
  on one island; staged execution must reuse upstream wait rather than retry
  an ambiguous mutation. No new mutation path is enabled yet.
- Initial policy and inventory helpers are implemented with synthetic tests.
  Authenticated inventory reads are exposed through the account/city-scoped
  controller and both read-only interfaces; no new game mutation is exposed.
- Local verification: 32 focused engine/controller/parity and OpenSpec tests,
  41 native account-scope tests, 93 web tests plus the new production route
  allowlist regression; TypeScript compilation and targeted lint pass.
- Remaining: connect fresh server-reviewed plans and durable staged execution
  to the task ledger, implement batch/per-city review and mutation UI,
  compensation and recovery fencing, and synthetic E2E. Actual slider
  readback and live mutation effects are not verified.

## Staged implementation checkpoint

- Exact/percentage/maximum, overcharge, default priority, available-only, explicit full-release fallback (known capacities and allocations), per-city exclusion and exact override are wired through existing worker review tickets, with 16-city per-account and 32-account review bounds.
- Controller persists immutable account/city plan before engine dispatch. Engine uses upstream workerPlan helper with no transport retries, upstream wait, readback and durable release/target/restore receipts. Unfinished runs fence new tasks and recovery; completed runs release the fence. Stale pre-mutation cities are isolated.
- Native and web resource-specific bulk review controls implemented; all-resources is still inventory only. Manual reconciliation UI, durable receipt presentation, additional fallback for unknown capacity, and production-specific synthetic E2E remain open. No definitive workerPlan rejection contract was verified; ambiguous rejection is fenced, never compensated blindly.
- Local regression evidence: 107 focused engine/controller/recovery/parity tests, 41 native scope tests, 94 web tests, TypeScript and targeted lint. No game mutations.

## Current implementation evidence

- Web and native both-resource maximum operations require explicit wood-first or luxury-first priority; the second site uses remaining free population. Available-only never reduces the donor. Both-resource operation requires known capacities and population.
- A separately reviewed single-resource full-release fallback covers unknown population or target capacity only when both initial allocations and donor capacity are known. After release, fresh authoritative target capacity and free citizens are mandatory; unknown values leave a recovery fence.
- Controller, engine and client tests exercise review ownership, minimum release, extra capacity, donor restoration, crash/timeout/readback mismatch, explicit reconciliation, both-resource priority and unknown-capacity fallback. The operation uses existing workerPlan request construction and wait helpers. The narrow optional unknown-population parameter on getCity/getCityById retains the old strict behavior for other callers and avoids a parallel parser.
- Web and native execution history shows confirmed/pending stage receipts and per-city results. Manual reconciliation requires current allocations and a separate approval; it performs no game write.
- Verification: 98 web unit tests, 40 focused production/upstream/worker tests, 41 native scope tests, TypeScript, targeted ESLint, repository Python lint. Browser E2E and full latest-head CI remain pending. No live account mutation performed.
- A definitive target rejection is not exposed as an attested outcome by the existing workerPlan helper. Unknown or unchanged readback therefore fences rather than automatically compensating. Actual game slider semantics and rejection evidence remain unverified. Keep the change active rather than declaring this scenario or live acceptance complete.
