# unify-global-account-scope (v0.1.1)

## Why
The released web control center maintains scopeIds and automationAccount independently; an out-of-scope automation target can remain selected.

## What changes
Move one persistent account context into the application shell on web and native. Scope all relevant data and editors, including the new Production page. All, selected, and one account are supported.

## Impact
Planning only for v0.1.1; no production mutation or version bump. Keep v0.2.0 telemetry separate. ADR-006 and existing reviewed authorization remain binding.
