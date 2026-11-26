# Remaining agent-owned implementation and verification

Only engineering work belongs here. Owner-only live checks are in `docs/V010-OWNER-ACCEPTANCE.md` and issue #60; do not wait for them to archive this engineering change. See `docs/V010-RECONCILIATION.md` for the full historical mapping.

## E1 — Operation contract and upstream compatibility gaps
- [ ] Audit the current 49-row registry and existing editor/IPC/request contracts at option level against the pinned upstream source; record actual remaining unsupported options (not generic domain-wide TODOs). Implement missing safe supported options and protected cookie-only state-changing request adapters with exact request parity and offline regression tests; keep unsafe/unobservable options explicitly unavailable. Review cross-account/stale DTOs, per-operation effects and remaining generated contract drift. Do not duplicate upstream game algorithms.

## E2 — Web security hardening
- [ ] Verify invite-only provisioning and revocation, cookie attributes, conservative CSP, login/BFF rate limiting and redacted audit policy. Implement missing safeguards and negative tests; verify no secret or privileged snapshot escapes through caches or browser assets. Use existing Supabase/Vercel architecture, not a second auth system.

## E3 — Automated end-to-end coverage
- [ ] Add authenticated synthetic browser Playwright coverage of login, selected/all warehouse filtering/sort/cache/export, military nested unit tables, reviewed launch/stop and uncertain receipts; exercise real BFF/controller transport with synthetic fixtures. Add missing per-family Qt/API integration and stale/cross-account tests, including duplicate display names, without real game effects.

## E4 — Recovery engineering gaps
- [ ] Extend offline fault injection for simultaneous account losses, transient errors, worker death/IPC timeout, crash boundaries, restart with zero workers, and stop/edit/identity changes during grace. Verify existing protected token refresh, rate limits, fencing and nonsecret reason/status parity; fix concrete failures. Provide reviewed legacy configuration import only if independently trustworthy local configuration is available; otherwise explicitly document manual recreation. Extend durable receipt tracking to additional fixed transfers only when authoritative receipt and recipient evidence exists; otherwise retain manual-only recovery.

## E5 — Automated accessibility and UI QA
- [ ] Use the existing screenshot harness and synthetic fixtures to check critical Mac/web layouts at supported sizes, light/dark, keyboard/focus/accessibility names, reduced motion/contrast, EN/RU and stale/loading/partial states; fix concrete clipping, accessibility or feedback defects. Add automated checks where feasible; no requirement to recreate obsolete preimplementation prototypes. Physical Mac/VoiceOver/Safari visual acceptance remains owner-only.

## E6 — Release engineering and documentation
- [ ] Reconcile version metadata and build provenance across backend, Mac and web; make release packaging/checksums and compatibility/rollback procedure reproducible. Run full offline test/lint/build/secret/dependency/OpenSpec checks and required CI on the final engineering revision, fix failures, update permanent guides, coverage evidence and release notes. Publish or deploy only under the existing explicit approval and safe rollout gates. Archive this engineering change when these automated/implementation tasks are complete; keep owner acceptance separate and unpassed.
