# Implementation checklist

- [ ] Audit upstream slider, citizen, overcharge semantics and safe authoritative readback; test unknown data and exact-count representability.
- [ ] Build scoped read-only production inventory and city/resource discovery via existing helpers; explicit unavailable data.
- [ ] Add exact/percentage/max reviewed planner and default priority vs available-only policy with donor before/after and staged fallback.
- [ ] Implement durable staged assignment, minimum release, authoritative readback, leftover restoration, compensation/recovery fencing and idempotency using upstream shared mutation helper.
- [ ] Implement reviewed resource-specific batch plans for all/selected accounts and cities; per-city result and partial failures, no unrelated assignments.
- [ ] Build Production web/native editors and bulk actions, academy/temple sections, default unchecked available-only checkbox and explicit review; translations/accessibility.
- [ ] Test sufficient/insufficient citizens, extra capacity, both resources, release-minimum and fallback, donor restoration, rejection/timeout/crash/readback mismatch, population changes, account scope, no science/temple changes, synthetic E2E and upstream parity.
