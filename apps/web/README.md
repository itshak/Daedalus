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
5. The public web interface uses `https://daedalus.tongrix.com` (Vercel); the authenticated backend uses `https://daedalus-api.tongrix.com`. The Mac client connects directly to the backend origin. Keep worker IPC private.
6. Test logged-out GET /api/controller/accounts = 401 and a separately invited admin reading live accounts and combined warehouses. Do not treat incomplete game observations as zero.

## Local verification

Run `npm ci`, `npm run test`, `npm run typecheck`, `npm run lint`, `npm run build`, and `npm audit --omit=dev --audit-level=high` from `apps/web`. No live account credentials are required for these tests. Never run live Gameforge logins in public CI.

## Known unfinished parts

The current deployed preview includes typed native task editors, reviewed batch flows, military inventory and the sortable/filterable warehouse dashboard. See the permanent [operation coverage](../../docs/operation-coverage.json), [engineering successor](../../openspec/changes/finish-v010-engineering/tasks.md) and separate [owner acceptance](../../docs/V010-OWNER-ACCEPTANCE.md). No raw JSON mutation console is provided. Authenticated dashboard Playwright, cookie/rate-limit/CSP evidence, automated accessibility QA and owner-operated acceptance remain distinct gates.

## Beta gateway security

Browser sign-in uses a same-origin server route and HttpOnly, SameSite=Lax Supabase session cookies (Secure in production). All private gateway requests re-check the verified Supabase user and non-disabled operator row. The CSP blocks external connections, frames and objects; inline script/style remains necessary for the current Next.js rendering path. The bounded in-memory per-instance traffic guards are defense in depth, **not distributed rate limiting**. The deployed Vercel firewall now has an active valid API-prefix fixed-window IP limit (600 requests per 60 seconds), with stricter in-app login and operator limits. Provider open-signup and anonymous-user settings must be verified in the dashboard. Login now also rejects valid provider credentials without an active operator row, signs out locally, and returns no success or usable application session. The hosted project is on the Free plan: compromised-password protection requires Pro or higher ([provider documentation](https://supabase.com/docs/guides/auth/password-security)). Do not purchase an upgrade implicitly; use strong unique passwords and keep provisioning private. Audit action metadata is available from the controller's existing redacted receipt history; Gateway mutations now emit private server-side audit metadata with only operator UUID, role, fixed action, method and HTTP outcome. No body, request URL, account identifier or credential is logged by this audit helper. A controller HTTP response is not proof of a game effect. The reserved Supabase audit table remains inaccessible to anonymous/authenticated roles; the controller receipt history remains authoritative. The baseline SQL is rerunnable for existing installations and revokes all inherited default table grants before granting only the required operations. Live permissions were verified for both roles; neither can truncate any protected web table.

Production automatic builds are version-gated; ordinary pushes and preview branches skip builds. Manual redeploys remain available through the Vercel dashboard with Ignore Build Step unchecked. See [release deployment policy](../../docs/BETA-RELEASE.md#version-gated-vercel-deployment-policy).
