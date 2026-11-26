# Consolidation disposition — 2026-11-26

Archived as superseded by the single engineering successor `finish-v010-engineering`, not as proof that unchecked tasks passed. Original task checkboxes remain unchanged. Codes are defined in [the reconciliation index](../../../../docs/V010-RECONCILIATION.md). V codes identify implementation or evidence already present for part/all of a historical task; where E or O also appears, the remaining portion is explicitly transferred. S identifies an obsolete sequencing requirement. No live acceptance is inferred.

| Original unchecked task (in order) | Disposition |
| --- | --- |
| 1. Review the current backend endpoints, active native automations OpenSpec and IkaBot operation inventory; produce a machine-checkable status and endpoint matrix for all desktop/web-safe features. | V1 |
| 2. Apply the actual `apple-design` skill and Apple HIG to the design tokens, responsive screens, interaction physics and accessibility rubric; document exceptions for web-native expectations. | E5 |
| 3. Build two interactive light/dark representative prototypes and obtain owner visual feedback before committing to the complete UI. | O5; S |
| 4. Set up Supabase Auth + web-only Postgres migrations/RLS for admin identities/preferences/redacted audits; disable public signup and implement operator-invited first-admin bootstrap, revocation and logout. | V2; E2; O6 |
| 5. Implement server-verified web sessions, explicit server-side operator authorization, Secure HttpOnly cookie protections, CSRF/origin checks and login/gateway rate limits. | V2; E2 |
| 6. Verify Vercel-to-backend HTTPS reachability without exposing worker IPC; add failure/recovery behavior and security/secret scanning tests. | V3; E2; O6 |
| 7. Implement Overview and Accounts status/master-detail, actual world/email when permitted, secure revision-gated editing and explicit desktop-only Gameforge sign-in guidance. | V4; E1 |
| 8. Implement searchable automation group tabs, capability status and typed forms for real construction/cities, research/tavern/faith, resource/transport/trade, military training/piracy, alerts and exploration. | V5; E1 |
| 9. Preserve authoritative per-account previews, explicit effect review, UUID request-idempotency, launch safeguards, no cross-account identifier reuse and no automatic replay on uncertain result. | V5; E1; E4 |
| 10. Implement missing web-safe interactive-only operations solely through separately specified, audited controller adapters; keep unsupported operations clearly non-executable. | E1 |
| 11. Add offline synthetic controller contract fixtures and unit/component tests for auth, scope, stale data, conflicts, unavailable backend modes and receipt semantics. | V6; E3 |
| 12. Add Playwright browser E2E for admin login, all-account warehouses/print/export, scoped task review, monitored/uncertain request, task stop and Mac-only login guidance. | E3 |
| 13. Add accessibility and visual regression checks for all seven views in light/dark, desktop/tablet/mobile, 200% zoom, reduced motion/contrast; perform manual VoiceOver/Safari and keyboard review. | E5; O5 |
| 14. Run web lint/typecheck/build/tests, Python pytest/Ruff, strict `openspec validate --all --strict --no-interactive`, dependency/secret scans; repair reported failures. | V3; E6 |
| 15. Configure Vercel project on default `daedalus-web-chi.vercel.app` (not Cloudflare DNS); preserve `daedalus.tongrix.com` and `daedalus-api.tongrix.com` as backend ingress; verify live authorized browser→BFF→FastAPI only after dedicated admin provisioning. | V3; O6 |
| 16. Document developer/setup/security/operational rollback; obtain owner acceptance of live workflows and Apple-quality interactions before production release. | E6; O5; O6 |
| 17. Reconcile canonical OpenSpec and docs and archive this change only after verified completion; never mark unperformed live acceptance tasks done. | V7 |
| 18. Verify the authenticated deployed dashboard interaction and visual layout. | O5 |
