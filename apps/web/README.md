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

The seven-page shell, protected gateway, read-only warehouse/military/activity panels and read-only construction preview are implementation-stage features. Task-specific mutation form coverage, admin provisioning, Playwright/VoiceOver acceptance, actual authenticated end-to-end tests and operational cutover are separate verification gates. The web client deliberately does not provide a raw JSON-based mutation console.
