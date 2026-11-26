# Implementation tasks — Apple-inspired Next.js web control center

Every item starts unchecked. Keep this proposal active until implementation, automated verification and owner-operated acceptance are complete.

## Audit and design
- [ ] Review the current backend endpoints, active native automations OpenSpec and IkaBot operation inventory; produce a machine-checkable status and endpoint matrix for all desktop/web-safe features.
- [ ] Apply the actual `apple-design` skill and Apple HIG to the design tokens, responsive screens, interaction physics and accessibility rubric; document exceptions for web-native expectations.
- [ ] Build two interactive light/dark representative prototypes and obtain owner visual feedback before committing to the complete UI.

## Security and infrastructure foundation
- [x] Scaffold `apps/web` with pinned Next.js/React/Refine/Tailwind/TanStack/Zod dependencies, lockfile and CI for lint/typecheck/build/tests (shadcn present as Radix-based primitives; full component catalog outstanding).
- [ ] Set up Supabase Auth + web-only Postgres migrations/RLS for admin identities/preferences/redacted audits; disable public signup and implement operator-invited first-admin bootstrap, revocation and logout.
- [ ] Implement server-verified web sessions, explicit server-side operator authorization, Secure HttpOnly cookie protections, CSRF/origin checks and login/gateway rate limits.
- [x] Build a fixed-path allowlisted HTTPS FastAPI BFF with payload caps/timeouts, no-store, redacted errors and server-only bearer support; excluded native login/vault routes have negative-policy tests.
- [ ] Verify Vercel-to-backend HTTPS reachability without exposing worker IPC; add failure/recovery behavior and security/secret scanning tests.

## Pages, account scope and operation-specific interfaces
- [x] Create cohesive light/dark shell with accessible navigation, search, account scope, contextual inspectors and responsive styles; owner design acceptance outstanding.
- [ ] Implement Overview and Accounts status/master-detail, actual world/email when permitted, secure revision-gated editing and explicit desktop-only Gameforge sign-in guidance.
- [x] Implement Warehouses one/selected/all account reporting, island grouping, 220K filter, account-level failures, print and CSV/JSON/TXT exports; live authenticated owner acceptance outstanding.
- [x] Implement Military Troops/Fleet/Movements read-only panels and Activity/receipts/managed Stop/reconciliation wiring; live authenticated owner acceptance outstanding.
- [x] Implement Settings for appearance, session status and safe backend health/capabilities; additional audit/session management controls outstanding.
- [ ] Implement searchable automation group tabs, capability status and typed forms for real construction/cities, research/tavern/faith, resource/transport/trade, military training/piracy, alerts and exploration.
- [ ] Preserve authoritative per-account previews, explicit effect review, UUID request-idempotency, launch safeguards, no cross-account identifier reuse and no automatic replay on uncertain result.
- [ ] Implement missing web-safe interactive-only operations solely through separately specified, audited controller adapters; keep unsupported operations clearly non-executable.

## PWA, quality and deployment
- [x] Create branded PWA manifest/icon integration and private no-store response policy; local HTTP smoke verified protected routes deny unauthenticated access.
- [ ] Add offline synthetic controller contract fixtures and unit/component tests for auth, scope, stale data, conflicts, unavailable backend modes and receipt semantics.
- [ ] Add Playwright browser E2E for admin login, all-account warehouses/print/export, scoped task review, monitored/uncertain request, task stop and Mac-only login guidance.
- [ ] Add accessibility and visual regression checks for all seven views in light/dark, desktop/tablet/mobile, 200% zoom, reduced motion/contrast; perform manual VoiceOver/Safari and keyboard review.
- [ ] Run web lint/typecheck/build/tests, Python pytest/Ruff, strict `openspec validate --all --strict --no-interactive`, dependency/secret scans; repair reported failures.
- [ ] Configure Vercel project on default `daedalus-web-chi.vercel.app` (not Cloudflare DNS); preserve `daedalus.tongrix.com` and `daedalus-api.tongrix.com` as backend ingress; verify live authorized browser→BFF→FastAPI only after dedicated admin provisioning.
- [ ] Document developer/setup/security/operational rollback; obtain owner acceptance of live workflows and Apple-quality interactions before production release.
- [ ] Reconcile canonical OpenSpec and docs and archive this change only after verified completion; never mark unperformed live acceptance tasks done.


## Warehouse dashboard usability and cache
- [x] Restore the last valid workspace page after reload without persisting game snapshots.
- [x] Use a sortable TanStack warehouse table with island/world, resource and stock threshold filters, search, filtered totals and exports.
- [x] Reuse online per-account successful snapshots in volatile memory for 120 seconds, deduplicate requests, invalidate on refresh/offline and test expiry and isolation.
- [ ] Verify the authenticated deployed dashboard interaction and visual layout.
