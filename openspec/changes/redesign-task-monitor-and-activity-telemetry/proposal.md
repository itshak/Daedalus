# Redesign task monitor and activity telemetry (v0.2.0)

## Why
The current Activity page mixes engine processes, receipts and history, without durable operation-specific statistics or individual activity detail. The owner-operated warehouse test demonstrated repeated dispatch after fleet waiting, but cumulative counters alone cannot establish the exact shipment count, route-by-route history or delivery. Operators need a logical task monitor that explains what each approved operation has actually achieved.

## What changes
- Replace Activity navigation with Tasks: one entry per logical approved task, account scope, running/waiting/attention/history filters, operation-specific summaries.
- Task detail: expandable activities, statistics, approved configuration, execution runs, recovery and technical receipts; accessible responsive web and native desktop parity.
- Add bounded typed durable telemetry linked to existing task receipts and recovery identities; retain statistics across restart, reconnect and safe restoration.
- Reuse IkaBot upstream action and wait boundaries; no second executor, extra game polling or new authorization path.
- Define metric coverage for every registered operation, with transport, construction and recruitment as the first fully instrumented vertical slices.
- Explicitly distinguish requested, submitted, accepted/verified, and delivered/completed outcomes, partial or missing telemetry and uncertainty.

## Scope
Target v0.2.0 after the v0.1.0 release. This proposal authorizes planning only, not migration, live game changes, implementation or a version bump. Existing first-release engineering and owner acceptance remain independent. ADR-006 remains binding.

## Impact
automation-controller, controller-api, engine-integration, web-control-center, desktop-client, security-boundaries. Preserve existing API/receipt compatibility and the version-gated deployment policy.
