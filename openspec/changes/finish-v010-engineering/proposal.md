# Finish v0.1.0 engineering

## Why
Six overlapping implementation changes are superseded. The deployed preview has a working multi-account backend, native Mac and web clients, reviewed operation contracts and read-only reports. The final engineering backlog must not be confused with owner-operated live acceptance.

## What changes
Close only demonstrated implementation or automated verification gaps: operation option/transport compatibility, web security, offline end-to-end tests, recovery safety, accessible client QA, and reproducible release engineering. Keep owner-only checks in `docs/V010-OWNER-ACCEPTANCE.md` and issue #60. The historical proposals and per-task dispositions remain archived.

## Impact
No automatic game login, game mutation, host reboot, release publication or production approval is authorized by this change. Preserve ADR-006, protected local boundaries, and manual reconciliation of uncertain game effects. New functionality must use existing upstream helpers and guarded session adapters.
