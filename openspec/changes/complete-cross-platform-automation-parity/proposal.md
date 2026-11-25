# Change: Complete cross-platform IkaBot native workflow parity

## Why
Daedalus desktop and website must both expose the complete useful IkaBot functionality through proper UI controls, using real account-bound data. The desktop has many specialized forms but incomplete coverage and legacy raw configuration escape hatches on main. The web is mostly a read-only operation inspector. Separate partial proposals have not closed the gap.

## What Changes
- Establish a versioned, source-audited operation registry and shared typed domain draft/preview/execute contracts; use the existing backend and vendored engine as the authority, not two independent automation implementations.
- Implement every menu action and registered background task on both desktop and web in parallel, using dedicated controls, with explicit security-preserving equivalents for privileged local-only functions. Include interactive CLI-only operations through individually reviewed adapters, not CLI prompt scraping or generic task execution.
- Eliminate user-editable JSON, JSON imports, raw engine identifiers and expert overrides from automation settings. Keep serialization internal and report exports unaffected.
- Real game player names, account scope current/selected/all, game-backed city/building/unit/island/offer selectors, human-readable effect review and recoverable task lifecycle on both clients.
- Keep desktop-only native Selenium/credential handoff boundary; web shows actionable status and approved secure admin paths, never raw session cookies or arbitrary server commands.
- Add full per-operation parity matrix, automatic coverage gate, contract, Qt and web component/E2E tests, accessibility, i18n and release gates.

## Impact
Affected specs: desktop-client, controller-api, engine-integration, web-control-center, web-access-security. Code: src/daedalus, engine/ikabot, apps/web, tests, docs, CI. Coordinate PR #95 and existing active changes listed in capability-matrix.md; resolve overlapping deltas before applying or archiving. No deployment or live game actions are part of this planning change.
