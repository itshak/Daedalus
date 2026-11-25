# Implementation status — first vertical slice

Implemented on the integration branch:
- Integrates the desktop player-name and native-only changes from PR #95.
- Web native single-account editors and strict BFF schemas for fixed shipments, distribution, consolidation, resource transport manager, attack alerts and low-wine alerts. Current city choices come from the authenticated controller. No arbitrary task payload accepted from the browser; existing engine validates the selected account's IDs and constraints before launching.
- Explicit review and approval, v4 request IDs, fresh readiness check, no implicit retry; existing controller task ledger and recovery retained.
- Player-first web display names with duplicate disambiguation; EN/RU strings; real game icons on fixed shipment resources.
- Registry/matrix coverage regression test added.

Verification: exact isolated contract/test files checked against Git blob hashes and executed under Node 22.16.0 with type stripping: 4 test groups passed. Isolated contract TypeScript strict check passed. Full desktop, web integration, engine, OpenSpec, CI and live acceptance not yet verified for the integrated commit.

Outstanding: authoritative versioned common contracts and preview tokens, capacity/ETA, external cities, multi-account planning and launch, remaining web forms and all missing interactive adapters, browser/desktop acceptance and deployment. Do not mark the proposal complete or archive it until the matrix and release gates are satisfied.
