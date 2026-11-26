# Daedalus private web control center

This is an implementation preview, NOT owner-accepted production or live-game certification.

## Architecture

- Next.js 16 App Router, React 19, TypeScript, Tailwind, Refine v5 and accessible React components.
- Supabase Auth validates sessions server-side, then checks the dedicated public.web_operators allowlist with RLS.
- A typed server-only fixed-path gateway connects to FastAPI through TLS and the backend bearer.
- Browser login to Gameforge, Selenium, saved cookies, server SSH, vaults and generic IkaBot IPC are deliberately excluded.

## Safe deployment

1. Create a SEPARATE Supabase project in a user-approved organization. Do not reuse ChessCoachPal data. Apply the migration in supabase/migrations to that project.
2. In Supabase Authentication settings disable open signup and anonymous registration. Invite the first administrator through the trusted dashboard. After verifying the invited auth.users UUID, add it explicitly to web_operators with role owner. Never auto-promote the first login.
3. Link the Vercel app to the repository with root directory apps/web. Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY to the dedicated project values.
4. Set DAEDALUS_API_BASE_URL and DAEDALUS_LEGACY_API_ORIGIN to https://daedalus-api.tongrix.com. Store DAEDALUS_API_TOKEN ONLY in Vercel encrypted server environment. Use the EXISTING authorized backend bearer; never paste it into chat or commit it to GitHub.
5. Keep both existing backend hostnames, `daedalus.tongrix.com` and `daedalus-api.tongrix.com`, unchanged on Cloudflare Tunnel. The web UI uses the Vercel-assigned `daedalus-web-chi.vercel.app` address; no DNS changes are required. The Mac client continues connecting directly to the existing backend host.
6. Test logged-out GET /api/controller/accounts = 401 and a separately invited admin reading live accounts and combined warehouses. Do not treat incomplete game observations as zero.

## Local verification

Run `npm ci`, `npm run test`, `npm run typecheck`, `npm run lint`, `npm run build`, and `npm audit --omit=dev --audit-level=high` from `apps/web`. No live account credentials are required for these tests. Never run live Gameforge logins in public CI.

## Known unfinished parts

The current deployed preview includes typed native task editors, reviewed batch flows, military inventory and the sortable/filterable warehouse dashboard. See the permanent [operation coverage](../../docs/operation-coverage.json), [engineering successor](../../openspec/changes/finish-v010-engineering/tasks.md) and separate [owner acceptance](../../docs/V010-OWNER-ACCEPTANCE.md). No raw JSON mutation console is provided. Authenticated dashboard Playwright, cookie/rate-limit/CSP evidence, automated accessibility QA and owner-operated acceptance remain distinct gates.

## Beta gateway security

Browser sign-in uses a same-origin server route and HttpOnly, SameSite=Lax Supabase session cookies (Secure in production). All private gateway requests re-check the verified Supabase user and non-disabled operator row. The CSP blocks external connections, frames and objects; inline script/style remains necessary for the current Next.js rendering path. The bounded in-memory per-instance traffic guards are defense in depth, **not distributed rate limiting**. Configure provider-side Supabase Auth limits and Vercel ingress limits before public exposure; verify them with an authorized synthetic test. Audit action metadata is available from the controller's existing redacted receipt history; Supabase audit-table ingestion is not yet implemented.
