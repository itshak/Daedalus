# Remaining agent-owned implementation and verification

Only engineering work belongs here. Owner-only live checks are in `docs/V010-OWNER-ACCEPTANCE.md` and issue #60; do not wait for them to archive this engineering change. See `docs/V010-RECONCILIATION.md` for the full historical mapping.

## E1 — Operation contract and upstream compatibility gaps
- [ ] Audit the current 49-row registry and existing editor/IPC/request contracts at option level against the pinned upstream source; record actual remaining unsupported options (not generic domain-wide TODOs). Implement missing safe supported options and protected cookie-only state-changing request adapters with exact request parity and offline regression tests; keep unsafe/unobservable options explicitly unavailable. Review cross-account/stale DTOs, per-operation effects and remaining generated contract drift. Do not duplicate upstream game algorithms.

- Progress: Implemented strict BFF query validation/forwarding (including aggregate pagination), with request regressions. Added exact reviewed cookie-session mutation adapters for construction, recruitment, layout, resource/academy/temple workers, donation, wine and study plus tavern read parity (48 focused tests). Remaining: audit other protected mutation forms and options; do not claim unsupported options are implemented.

## E2 — Web security hardening
- [ ] Verify invite-only provisioning and revocation, cookie attributes, conservative CSP, login/BFF rate limiting and redacted audit policy. Implement missing safeguards and negative tests; verify no secret or privileged snapshot escapes through caches or browser assets. Use existing Supabase/Vercel architecture, not a second auth system.

- Progress: Implemented server-side sign-in, HttpOnly/SameSite/Secure production cookies, restrictive CSP, bounded per-instance traffic guards and revocation regression. Supabase RLS verified read-only. Configured and read back active Vercel API rate limit (600 per IP per 60 seconds), revoked excess database grants and verified no anonymous grants, no authenticated operator writes or TRUNCATE, and no authenticated audit access. Remaining: provider leaked-password protection, audit ingestion decision and deployed authenticated verification.

## E3 — Automated end-to-end coverage
- [ ] Add authenticated synthetic browser Playwright coverage of login, selected/all warehouse filtering/sort/cache/export, military nested unit tables, reviewed launch/stop and uncertain receipts; exercise real BFF/controller transport with synthetic fixtures. Add missing per-family Qt/API integration and stale/cross-account tests, including duplicate display names, without real game effects.

- Progress: Implemented real Next.js/Playwright synthetic auth, warehouse, military, caching, export, reviewed task, ambiguous receipt, revocation and cross-account scenarios; Browser E2E workflow and macOS provenance checks are now committed through the authorized GitHub integration. Remaining: exhaustive per-family Qt/API integration gaps.

## E4 — Recovery engineering gaps
- [ ] Extend offline fault injection for simultaneous account losses, transient errors, worker death/IPC timeout, crash boundaries, restart with zero workers, and stop/edit/identity changes during grace. Verify existing protected token refresh, rate limits, fencing and nonsecret reason/status parity; fix concrete failures. Provide reviewed legacy configuration import only if independently trustworthy local configuration is available; otherwise explicitly document manual recreation. Extend durable receipt tracking to additional fixed transfers only when authoritative receipt and recipient evidence exists; otherwise retain manual-only recovery.

- Progress: Implemented distinction between transient upstream transport errors and confirmed session loss in recovery supervisor; added offline regressions. Added disabled-account policy fence, pause preservation on edits, current restored-epoch and unresolved-receipt guards, isolation of identity-scoped receipts, cleanup-failure isolation, revocation during worker startup, and simultaneous-loss, dead-worker, stop-during-grace and legacy monitor tests (57 focused tests passed). Remaining: additional fixed transfer and live acceptance boundaries.

## E5 — Automated accessibility and UI QA
- [ ] Use the existing screenshot harness and synthetic fixtures to check critical Mac/web layouts at supported sizes, light/dark, keyboard/focus/accessibility names, reduced motion/contrast, EN/RU and stale/loading/partial states; fix concrete clipping, accessibility or feedback defects. Add automated checks where feasible; no requirement to recreate obsolete preimplementation prototypes. Physical Mac/VoiceOver/Safari visual acceptance remains owner-only.

- Progress: Implemented accessible warehouse filters/scope state, responsive overflow fix, automated EN/RU, dark mode and mobile checks. Added strict warehouse DTO validation and generation-fenced refresh, cross-account response rejection, and verified logout feedback. Remaining: full desktop/keyboard and screenshot-harness matrix.

## E6 — Release engineering and documentation
- [ ] Reconcile version metadata and build provenance across backend, Mac and web; make release packaging/checksums and compatibility/rollback procedure reproducible. Run full offline test/lint/build/secret/dependency/OpenSpec checks and required CI on the final engineering revision, fix failures, update permanent guides, coverage evidence and release notes. Publish or deploy only under the existing explicit approval and safe rollout gates. Archive this engineering change when these automated/implementation tasks are complete; keep owner acceptance separate and unpassed.
- Progress: Implemented beta metadata, README, changelog, community docs, web and macOS build provenance and version-consistency tests. Fixed recovery-reconcile test fixtures to use actual restored epochs; full local Python suite 676 passed / 25 skipped. Remaining: final CI, approved release publication/rollout and completion of other workstreams.
