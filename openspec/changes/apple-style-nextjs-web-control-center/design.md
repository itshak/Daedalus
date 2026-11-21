# Design: Next.js control plane with Apple-inspired interaction

## Binding design sources

Before visual implementation, read and apply Emil Kowalski's `apple-design` skill at https://github.com/emilkowalski/skills/blob/main/skills/apple-design/SKILL.md and Apple's HIG at https://developer.apple.com/design/human-interface-guidelines/. This includes immediate pointer-down feedback, direct manipulation tracking 1:1, springs retargeted from the current presentation value (velocity carried through interruptions), momentum only where gesture-earned, symmetric motion origins, critically damped default movement, restrained translucency, optical type spacing, reduced-motion/transparency/contrast and tested real browser behavior. Use principles, not copied proprietary Apple assets or code.

## Architecture

```text
Mac/iPad/phone browser or installed PWA
  | HTTPS; Secure HttpOnly SameSite web session
Vercel Next.js App Router (apps/web)
  | server-verified Supabase Auth + explicit operator authorization
  | typed, audited, allowlisted route handlers/server actions
  | Daedalus API bearer secret in encrypted server-only environment
  v
Existing trusted HTTPS ingress --> FastAPI /api/v1/*
  | account identity + capability + ownership + preflight + durable receipts
  v
Existing IkaBot engine/IPC and single-owner authenticated workers
```

Supabase PostgreSQL stores identities, minimal web preferences and redacted audit references only, with explicit migrations and RLS. It never becomes a second source of game truth; do not mirror game snapshots or persist credentials/vault ciphertext there.

## Security model

- **No first-visitor owner takeover**: production denies all private routes until an operator-created invitation or secure one-time admin bootstrap establishes the first owner; public self-signup disabled. Verify the user server-side on every privileged route, then check a persistent server-side allowlist/role.
- Browser never sees `DAEDALUS_API_TOKEN`, SSH secrets, Gameforge passwords, cookies or Supabase service-role keys. No `NEXT_PUBLIC_` secret or secret-bearing serialized props, HTML, client logs, errors, telemetry or URLs.
- Gateway is **not** a generic user-controlled proxy. Explicit method/path/schema allowlist for approved FastAPI endpoints; reject arbitrary host, unapproved method, oversized bodies, cross-origin/CSRF requests and account-ID mismatches before forwarding. Enforce HTTPS/TLS validation, safe timeouts and no-store/noindex headers. Add login rate limiting and audit.
- Keep backend bearer authentication and its actual account/world/player authorization, permission flags, revisions and locks; Refine role checks alone never authorize engine execution.
- Account scope or backend origin/worker state changes invalidate cached queries, draft plans and confirmations. Use independent preflight/preview and request IDs for each account. Never broadcast a city-specific plan to multiple accounts.
- Never retry timed-out game mutations automatically. Distinguish request submitted, accepted, running, completed, rejected and uncertain; show explicit supported reconciliation only.
- Do not expose native browser handoff, saved login vaults or Gameforge auth endpoints to the web client. Desktop Mac remains the only login/recovery workflow.
- Verify that Vercel server functions can reach the trusted backend ingress before enabling production. Do not widen backend/IPC exposure as a shortcut.

## UI engineering

Use Refine for resource conventions, provider routing and admin infrastructure; shadcn/Radix for customizable accessible controls; Tailwind semantic tokens, TanStack Table for warehouses/buildings/military, React Hook Form + Zod for domain editors and TanStack Query for scoped fetch state. An auth provider in the browser is UI convenience, not the security boundary. Use system fonts (never redistribute SF Pro), licensed icons, existing Daedalus app assets and measured motion.

See `ux-blueprint.md` for screen specifics and responsive acceptance. Build representative clickable interactive light/dark prototypes early, get owner feedback, and avoid producing a raw generic Refine starter as final UI.

## Controller parity

Inspect `src/daedalus/api.py` and `docs/AUTOMATION-UX-AUDIT.md` dynamically; see `capability-matrix.md`. Existing routes support accounts, health, capabilities, cities/buildings/construction preview, academies, taverns, miracles, shrines, market, trainable units, workshop upgrades, piracy, military/movements, warehouses, task control/preflight/list/start/stop/reconciliation and optional revisioned account editor. Their presence does not imply the server enables them all simultaneously. Each operation must remain capability/role/session gated. Interactive-only upstream CLI actions require individually audited controller adapters; no arbitrary JSON or command execution.

## Offline, PWA and rollout

Cache only public versioned static shell assets. Authenticated HTML/SSR, login callbacks, API responses, task operations and game information must be network-only/no-store; offline state is locked and clearly marked unavailable, not a stale report. Maintain typed API fixtures with synthetic game data, contract tests, component and Playwright e2e, accessibility and visual regression baselines. Test 1440x900, 1024x768, 390x844 in light/dark, large text, reduced motion/transparency and screen reader.

Development phases: (1) secure BFF and session foundation, (2) Apple-style interactive shell and read-only pages, (3) contextual workflow editors and vetted controller adapter gaps, (4) tests, Vercel private preview, owner visual acceptance, DNS/TLS/domain/backend validation, reversible production release. Keep native desktop and workers unchanged until separately approved.

## Alternatives

MUI Toolpad Core has an uncertain active development trajectory; React-admin is more CRUD-centric; a raw shadcn starter repeats administrative plumbing. Refine + shadcn preserves both productivity and bespoke interaction design. Supabase suits a minimal managed identity/preferences layer; Neon/Better Auth is a viable alternative but not required.
