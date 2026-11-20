# Implementation tasks — Apple-inspired Next.js web control center

Every item starts unchecked. Keep this proposal active until implementation, automated verification and owner-operated acceptance are complete.

## Audit and design
- [ ] Review the current backend endpoints, active native automations OpenSpec and IkaBot operation inventory; produce a machine-checkable status and endpoint matrix for all desktop/web-safe features.
- [ ] Apply the actual `apple-design` skill and Apple HIG to the design tokens, responsive screens, interaction physics and accessibility rubric; document exceptions for web-native expectations.
- [ ] Build two interactive light/dark representative prototypes and obtain owner visual feedback before committing to the complete UI.

## Security and infrastructure foundation
- [ ] Scaffold `apps/web` in the monorepo with pinned compatible Next.js/React/Refine/shadcn/Tailwind/TanStack/Zod dependencies; CI for lint/typecheck/build/tests.
- [ ] Set up Supabase Auth + web-only Postgres migrations/RLS for admin identities/preferences/redacted audits; disable public signup and implement operator-invited first-admin bootstrap, revocation and logout.
- [ ] Implement server-verified web sessions, explicit server-side operator authorization, Secure HttpOnly cookie protections, CSRF/origin checks and login/gateway rate limits.
- [ ] Build a typed fixed-path FastAPI BFF with strict HTTPS and certificate validation, payload caps/timeouts, no-store, redacted errors and server-only bearer secrets; never expose login-vault/native-browser-login endpoints.
- [ ] Verify Vercel-to-backend HTTPS reachability without exposing worker IPC; add failure/recovery behavior and security/secret scanning tests.

## Pages, account scope and operation-specific interfaces
- [ ] Create cohesive Apple-style light/dark shell and system with accessible navigation, search, account scope, contextual inspectors and responsive states.
- [ ] Implement Overview and Accounts status/master-detail, actual world/email when permitted, secure revision-gated editing and explicit desktop-only Gameforge sign-in guidance.
- [ ] Implement Warehouses one/selected/all account reporting, island grouping, existing 220K filter, account-level failures, printable report and CSV/JSON/TXT exports.
- [ ] Implement Military Troops/Fleet/Movements read-only panels and Activity Running/History/Uncertain tracking, safe Stop and reconciliation.
- [ ] Implement Settings for appearance, accessibility, sessions, safe backend health/capabilities and diagnostics.
- [ ] Implement searchable automation group tabs, capability status and typed forms for real construction/cities, research/tavern/faith, resource/transport/trade, military training/piracy, alerts and exploration.
- [ ] Preserve authoritative per-account previews, explicit effect review, UUID request-idempotency, launch safeguards, no cross-account identifier reuse and no automatic replay on uncertain result.
- [ ] Implement missing web-safe interactive-only operations solely through separately specified, audited controller adapters; keep unsupported operations clearly non-executable.

## PWA, quality and deployment
- [ ] Create branded PWA manifest/icon integration and public-static-only cache policy; prove authenticated/game HTML, API and mutations are never offline-cached.
- [ ] Add offline synthetic controller contract fixtures and unit/component tests for auth, scope, stale data, conflicts, unavailable backend modes and receipt semantics.
- [ ] Add Playwright browser E2E for admin login, all-account warehouses/print/export, scoped task review, monitored/uncertain request, task stop and Mac-only login guidance.
- [ ] Add accessibility and visual regression checks for all seven views in light/dark, desktop/tablet/mobile, 200% zoom, reduced motion/contrast; perform manual VoiceOver/Safari and keyboard review.
- [ ] Run web lint/typecheck/build/tests, Python pytest/Ruff, strict `openspec validate --all --strict --no-interactive`, dependency/secret scans; repair reported failures.
- [ ] Configure Vercel Git project, private previews, secure environment, `daedalus.tongrix.com` domain/DNS/TLS and test actual logged-out denial plus authorized browser→BFF→FastAPI.
- [ ] Document developer/setup/security/operational rollback; obtain owner acceptance of live workflows and Apple-quality interactions before production release.
- [ ] Reconcile canonical OpenSpec and docs and archive this change only after verified completion; never mark unperformed live acceptance tasks done.
