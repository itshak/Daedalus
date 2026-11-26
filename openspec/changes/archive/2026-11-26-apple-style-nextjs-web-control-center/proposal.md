# Change: Apple-inspired Next.js web control center

## Why

The current PySide6 desktop interface is necessary for secure local Selenium/Gameforge login, but incremental additions have left everyday management too technical and visually inconsistent. Daedalus needs an excellent browser-accessible and installable management application, without replacing the authoritative Python/FastAPI controller or IkaBot game engine.

## What changes

- Add `apps/web/` using supported stable versions of **Next.js App Router (target 16), React, TypeScript, Refine v5, shadcn/ui + Radix, Tailwind CSS, TanStack Table/Query, React Hook Form and Zod**; deploy to **Vercel** under the project default `https://daedalus-web-chi.vercel.app`, preserving `https://daedalus.tongrix.com` as the existing backend and Mac API host.
- **Apply the public `apple-design` skill** (Emil Kowalski, https://github.com/emilkowalski/skills/blob/main/skills/apple-design/SKILL.md) and Apple Human Interface Guidelines (https://developer.apple.com/design/human-interface-guidelines/). The app SHALL embody clarity, crafted typography, restrained materials, responsive feedback, physical and interruptible interactions, predictable navigation, accessibility and reduced-motion/transparency/contrast variants. Apple-inspired, not a macOS-window imitation.
- Use **Supabase Auth + PostgreSQL** only for closed, owner-approved administrator identities, web sessions, preferences and redacted audit metadata. No public registration or first-visitor owner claim.
- Implement a **server-only, typed allowlisted Next.js backend-for-frontend** connecting to the existing HTTPS FastAPI controller with its existing bearer. Never send the Daedalus token, SSH credentials, Gameforge credentials, cookies or vault blobs to the browser or Supabase.
- Provide **Overview, Accounts, Warehouses, Automations, Military, Activity and Settings**, with One / Selected / All account scope on every appropriate page. Preserve combined all-account warehouse printing, island grouping, 220K unsecured-resource filter, exports and partial failure reporting.
- Provide dedicated, real-data editors for supported IkaBot automations: account-scoped cities/buildings/research/resources/routes/offers/units, preflight, plan review, explicit per-account consent, task monitoring/stop and uncertain receipt reconciliation. Routine workflows SHALL NOT expose generic JSON.
- Maintain a tested parity matrix: a catalogued interactive-only IkaBot operation is **not** executable until a separately audited controller endpoint exists. Unsupported capabilities have honest read-only/needs-adapter/desktop-only states, not fake buttons.
- Deliver an accessible responsive PWA while never offline-caching private game/account data or replaying mutations.

## Capabilities

### Added
- `web-control-center`: browser/PWA design, navigation, multi-account feature parity, web-safe task workflows and accessible interaction contract.
- `web-access-security`: closed administrator provisioning, server-only gateway, private caching, deployment and session controls.

Existing `controller-api`, `account-sessions`, `automation-controller`, `warehouse-monitoring` and `security-boundaries` remain authoritative. Missing web-safe backend operations must be designed as separate reviewed deltas.

## Compatibility and dependencies

Follow `AGENTS.md`, ADR-001/003/004/005 and the active `native-automation-workflows` audit. Retain the desktop application as the **only** Selenium-assisted Gameforge login, CAPTCHA and Mac-bound encrypted handoff client. Preserve game worker ownership, backend revision checks, task idempotency, uncertain-result handling, existing deployment and credentials. Use redistributable Daedalus brand assets and separately licensed component/icon assets, not proprietary Apple fonts/symbols.

## Non-goals

No JavaScript recreation of IkaBot, no backend replacement, no browser Gameforge login, CAPTCHA solving, generic Python/IPC executor, open signup, direct browser-to-backend bearer, bulk unreviewed dispatch, production worker cutover, or claim of live-game acceptance.

## Success criteria

The user can sign into the web app securely, understand account status, print a single all-account warehouse report, configure supported tasks through real domain controls, approve each account's action and observe reliable results, inspect military and activity, and recognize when desktop sign-in is required. Light/dark, mobile/tablet/desktop, keyboard, screen reader, reduced motion, auth failure and network failure all pass defined tests. Custom HTTPS domain and actual backend connection are verified before release.

**Planning only.** No functionality or deployment is implied by this proposal. Implementation checklist remains unchecked and change active until verified.
