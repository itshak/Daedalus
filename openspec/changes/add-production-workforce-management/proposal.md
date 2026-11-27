# add-production-workforce-management (v0.1.1)

## Why
modifyProduction supports percentage and a boolean maximum overcharge, but no resource-specific cross-account bulk actions or priority reallocation. The owner requires maximizing a resource even when free citizens are insufficient.

## What changes
Add Production navigation, per-city wood/luxury/scientist/priest views and edits, resource-specific maximum/percentage/exact bulk workforce changes, global scope, and default priority reallocation from the other production site. Provide an opt-out: Use only available population.

## Impact
Planning only for v0.1.1; no production mutation or version bump. Keep v0.2.0 telemetry separate. ADR-006 and existing reviewed authorization remain binding.
