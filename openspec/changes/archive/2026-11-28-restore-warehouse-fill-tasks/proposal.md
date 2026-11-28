# restore-warehouse-fill-tasks (v0.1.1)

## Why
Production restart restored account sessions but the preserved fillCityWarehouse job is classified manual; no safe restore implemented. Current fill has reviewed per-source caps and fresh storage/incoming checks, but volatile progress alone does not prove what was already dispatched.

## What changes
Introduce narrowly eligible restart-safe warehouse fill with durable per-source intent and confirmed dispatch evidence, truthful recovery status and eligibility information.

## Impact
Planning only for v0.1.1; no production mutation or version bump. Keep v0.2.0 telemetry separate. ADR-006 and existing reviewed authorization remain binding.
