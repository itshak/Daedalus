# v0.1.0 OpenSpec reconciliation

Reviewed against main `69d7552` (PR #110), 2026-11-26. This is a consolidation, not a release approval or proof of every option. Six prior changes are superseded; original tasks, designs, proposals, matrix and historical checklists are retained. The sole active successor is [finish-v010-engineering](../openspec/changes/finish-v010-engineering/tasks.md).

## Evidence keys

- **V1** — registry and generated contract: `src/daedalus/operation_manifest.py`, `scripts/generate_operation_contract.py`, `tests/test_cross_platform_parity.py`; 49 operations, 33 native / 15 existing views / 1 protected local; all live_accepted flags false. The permanent matrix is `docs/operation-coverage.json`.
- **V2** — `apps/web/lib/supabase.ts`, `apps/web/supabase/migrations/20261120_apple_web_operators.sql`, controller gateway route and request-policy tests. Server-side identity and roles, RLS, fixed paths, no-store and origin checks exist; rate limiting, HttpOnly/CSP and deployed audit evidence are not certified.
- **V3** — main 69d7552: seven successful GitHub workflows including cross-platform Python, engine, web, secret/dependency scanning, desktop and packaging; matching preview DMG/checksum and Vercel production READY. Production API reported 10/10 authenticated accounts and no uncertain receipts during read-only inspection; backend source matched main even though checkout commit differed. No new deployment or real game mutation in this consolidation. Final successor revision still requires its own verification.
- **V4** — desktop `app.py`, `design_system.py`, `theme.py`, `home_page.py`, `pages.py`, `task_page.py`, `log_page.py`; tests `test_desktop_redesign.py`, `test_desktop_account_scopes.py`, `test_desktop_parity.py`, and `test_macos_packaging.py`. Web `control-center.tsx` and domain components, PRs #109–110. These establish implemented paths, not exhaustive visual acceptance.
- **V5** — reviewed operation manifest, `api.py`, `engine_ipc.py`, `operation_previews.py`, `reviewed_operations.py`, `native_controls.py`, dedicated web editors, generated launch contract and canonical controller specs. Archived PR #97 and subsequent implemented slices in the archived parity `prior-checklist.md`. Not a claim of full option-level coverage.
- **V6** — existing Python/Qt/IPC and web contract suites, 82 web tests and full main CI. Browser-recovery Playwright in CI is cookie isolation, not authenticated web-dashboard E2E.
- **V7** — this reconciliation, canonical requirement integration and archived dispositions. Remaining evidence transfers to E/O codes.
- **V8** — recovery implementation and tests: `recovery_runtime.py`, `recovery_state.py`, `recovery_reconcile.py`, `recovery_credentials.py`, `test_recovery_runtime.py`, `test_recovery_state.py`, `test_fixed_transfer_recovery.py`, `test_recovery_api.py`; default-on, 300 seconds, policy/pause, per-epoch fences, fixed cargo receipts and safe allowlist. No live restoration assertion.
- **S** — preimplementation prototype sequencing obsolete for the already implemented product; actual visual and automated QA retained.

**E1–E6** correspond to the six concrete agent tasks in the successor. **O1–O6** correspond to owner checks in [V010-OWNER-ACCEPTANCE.md](V010-OWNER-ACCEPTANCE.md). Mixed dispositions deliberately retain partial work; V codes do not mean a broad historical task is fully complete. No unchecked original task was changed to checked.

## Archived source records

- [apple-style-nextjs-web-control-center](../openspec/changes/archive/2026-11-26-apple-style-nextjs-web-control-center/consolidation-record.md) — 18 previously unchecked task dispositions.
- [delayed-session-reconnect-and-task-restoration](../openspec/changes/archive/2026-11-26-delayed-session-reconnect-and-task-restoration/consolidation-record.md) — 22 previously unchecked task dispositions.
- [fill-city-warehouse](../openspec/changes/archive/2026-11-26-fill-city-warehouse/consolidation-record.md) — 8 previously unchecked task dispositions.
- [native-automation-workflows](../openspec/changes/archive/2026-11-26-native-automation-workflows/consolidation-record.md) — 35 previously unchecked task dispositions.
- [redesign-macos-desktop-experience](../openspec/changes/archive/2026-11-26-redesign-macos-desktop-experience/consolidation-record.md) — 33 previously unchecked task dispositions.
- [verify-and-release-cross-platform-parity](../openspec/changes/archive/2026-11-26-verify-and-release-cross-platform-parity/consolidation-record.md) — 6 previously unchecked task dispositions.

The parity source also contains `original-tasks.md` and `prior-checklist.md`. The original registry/option/API/adapter/transport/operation scopes and cross-platform contract criteria are retained in E1; auth/security/provider boundaries in E2; per-family integration and synthetic tests in E3; replay/recovery in E4; visual/accessibility in E5 and O5; CI/packaging/rollout/documentation in E6 and O6; all owner/live criteria in O1–O6. Previously checked follow-up slices stay checked in history. No original criterion is dropped or represented as fully accepted.

## Canonical delta disposition

| Source | Capability | Requirement | Result |
| --- | --- | --- | --- |
| apple-style-nextjs-web-control-center | web-access-security | Closed first-admin provisioning | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-access-security | Server-only controller credentials and fixed gateway | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-access-security | Mutations remain authenticated and isolated | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-access-security | Privacy, caching and audit boundaries | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-access-security | Verified secure deployment | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Optional Apple-inspired web experience | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Accessible, adaptive, fluid and interruptible UI | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Account-aware cross-screen management | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Warehouse and military reporting parity | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Purpose-built task editors and explicit confirmation | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Safe task lifecycle across accounts | Reconciled into canonical spec; not proof of implementation. |
| apple-style-nextjs-web-control-center | web-control-center | Private network-only game state in PWA | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | account-sessions | Opt-in automatic recovery after a confirmed rotation grace period | Reconciled as Confirmed rotation grace period for automatic recovery; default-on canonical policy takes precedence. |
| delayed-session-reconnect-and-task-restoration | account-sessions | Protected, bounded and independently verified world reauthentication | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | account-sessions | Browser-use pause and explicit early reconnect | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | automation-controller | Persist previously approved desired background tasks independently of engine PIDs | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | automation-controller | Restore only safely reconcilable tasks after verified session recovery | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | automation-controller | Account recovery is bounded and auditable without secret disclosure | Reconciled into canonical spec; not proof of implementation. |
| delayed-session-reconnect-and-task-restoration | desktop-client | Simple per-account and bulk recovery controls | Reconciled with default-on and explicit disable/pause. |
| fill-city-warehouse | controller-api | Fill an owned city's warehouse for one resource | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | Authenticated contextual read models | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | Nonmutating native plan previews | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | User-approved per-account task dispatch | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | Bound read-only military DTOs | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | Upstream gameplay waiting compatibility | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | controller-api | Minimize divergence from upstream operation implementation | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | desktop-client | Grouped task discovery | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | desktop-client | Live domain controls, not guessed JSON values | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | desktop-client | Per-account review and nonbroadcast domain plans | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | desktop-client | Accessible, compact operation workspace | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | desktop-client | Native, nonmutating military inspection | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | engine-integration | IkaBot remains the only authoritative game engine | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | engine-integration | Strict audited existing-session IPC | Reconciled into canonical spec; not proof of implementation. |
| native-automation-workflows | engine-integration | No fictitious preparation | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Coherent macOS-native desktop design system | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Unified, account-aware information architecture | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Progressive-disclosure connection experience | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Contextual account management and recovery UX | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Truthful account-first Overview | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Capability-grounded operation discovery | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Task-aware guided configuration with safe fallback | Reconciled with canonical Native-only automation settings; no JSON escape hatch. |
| redesign-macos-desktop-experience | desktop-client | Clear, guarded automation confirmation and lifecycle | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Warehouse report parity with polished interaction | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Consistent asynchronous feedback and stale-result safety | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Human-centered Activity and private Settings | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Accessibility, adaptive layout and visual acceptance | Reconciled; visual acceptance separated from engineering archival. |
| redesign-macos-desktop-experience | desktop-client | First-class all-account and selected-account workflows | Reconciled into canonical spec; not proof of implementation. |
| redesign-macos-desktop-experience | desktop-client | Automatic headless Gameforge authentication with human CAPTCHA only | Superseded by canonical Observable headless Gameforge authentication with visible failure recovery (PR #85). |
| verify-and-release-cross-platform-parity | controller-api | Exact revision release verification | Reconciled into canonical spec; not proof of implementation. |
