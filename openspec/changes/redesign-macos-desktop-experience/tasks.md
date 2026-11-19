# Implementation tasks — complete native macOS experience

All tasks are intentionally open. This change contains planning only; do not mark work done based solely on an existing first-pass feature or a passed synthetic test from an earlier change. Finish each item with its own measurable evidence before archival. Follow the ordering and checkpoint gates below; use small, separately reviewable PRs referencing this change ID.

## Phase 0 — baseline and design validation

- [ ] 0.1 Capture current light/dark screenshots and widget-tree inventory for every current route at 900x650 and 1200x800; document UI defects and separately mark legacy warehouse features to preserve.
- [ ] 0.2 Map every current account, recovery, operation, report, connection, settings and diagnostic action to the target blueprint; flag missing API metadata, conflicts with ADRs, risk and screen-level acceptance ownership.
- [ ] 0.3 Define approved Mac design tokens, responsive layout grid, type scale, colors, density, icon semantics and accessible states; obtain a visual style baseline approval before widespread refactoring.
- [ ] 0.4 Evaluate the installed PySide6-Fluent-Widgets version for all proposed widgets (navigation, searchable inputs, switches, cards, dialogs, progress, badge/status, table and segmented controls); record verified imports and fallback wrappers.

## Phase 1 — reusable Fluent foundation and navigation

- [ ] 1.1 Introduce a centralized theme/token system with Mac system light/dark following and local overrides; preserve legacy OpaqueCardWidget and scroll table behavior.
- [ ] 1.2 Create a vetted semantic icon registry and distinct, crisp primary/secondary navigation assets; add automated uniqueness tests preventing repeated Connection/Settings or Wine/Automations glyphs.
- [ ] 1.3 Build reusable accessible page headers, section cards, account/backend pickers, status chips, inline helper/error, safe confirmation, empty/loading/partial state and toast components.
- [ ] 1.4 Rework FluentWindow sidebar/titlebar/toolbar to the five-primary-destination hierarchy, distinct Connection and Settings utilities, safe native keyboard shortcuts, correct resize and selection persistence.
- [ ] 1.5 Implement semantic route/deep-link handling so prior Home, Wine, Construction, catalog and task shortcuts reach unified contexts without stale or cross-account selections.
- [ ] 1.6 Introduce typed, nonsecret per-backend/account Qt view state and async request generation guards; discard stale responses and test rapid account/backend changes.
- [ ] 1.7 Add shared accessible page-shell layouts and narrow-window overflow/scroll behavior; verify minimum-size layout does not clip controls or Mac traffic lights.

## Phase 2 — connection, overview and account experience

- [ ] 2.1 Redesign first-run onboarding with HTTPS URL/token validation, demo choice, progress and exact-origin Keychain opt-in/out states; preserve automatic read-only reconnect and ephemeral fallback.
- [ ] 2.2 Redesign the connected Connection screen as status/details/reconnect/forget plus Advanced SSH fallback; test missing/untrusted TLS, unauthorized token, unavailable keyring and trusted SSH fail-closed handling.
- [ ] 2.3 Replace simple Home action grid with an account-scoped Overview showing truthful backend/worker health, quick actions, summaries and source/refresh/empty/partial states.
- [ ] 2.4 Redesign Accounts as an accessible master/detail workspace with clear account identity, session status and contextual primary action while preserving account create/edit/enable/disable/remove rules and confirmations.
- [ ] 2.5 Implement a guided Sign in on this Mac dialog/sheet with explicit account/world, manual CAPTCHA expectations, one-use challenge progress, cancel, timeout and independently verified success; never surface secret material.
- [ ] 2.6 Move manual assistance, monitoring and host-side recovery into separated permission-gated secondary flows with verified lease/status handling, stale-ticket guards and no implicit worker authentication.
- [ ] 2.7 Add offscreen synthetic UI coverage for disconnected, read-only, demo, unverified, paused, needs assistance, worker-busy and multiactive account states; ensure zero accidental game requests.

## Phase 3 — coherent automations and operation-specific UX

- [ ] 3.1 Consolidate three TasksPage instances and OperationsPage into a single Discover/Configure/Running/History workspace while maintaining equivalent Wine, Construction and catalog navigation.
- [ ] 3.2 Build a capability-aware searchable task gallery with understandable titles, icons, explanatory descriptions, permission/readiness labels and honest interactive-only entries.
- [ ] 3.3 Create a typed schema-aware field rendering library (boolean, integer, decimal, time/unit, validated enum, optional, conditional/group and expert JSON fallback); never infer IDs/options absent backend metadata.
- [ ] 3.4 Build dedicated Wine controls for tavernManager/alertLowWine and accurate Construction controls for constructionList/research, with backend-supported defaults, examples and focused synthetic form tests.
- [ ] 3.5 Build dedicated Alerts/Monitoring and Resources/Trade forms for the supported registered tasks, including field help, units, validation and safe fallback for nested/unsupported schemas.
- [ ] 3.6 Cover military, miracle, daily, piracy and all remaining registered operations with reviewed typed presentation or prominently explained expert/unsupported paths; verify catalog coverage against registry.
- [ ] 3.7 Implement a one-screen review summary and separate explicit start authorization bound to account/world/task/config revision and fresh preflight; preserve backend UUID/idempotency and dispatch permission checks.
- [ ] 3.8 Implement human-readable managed task lifecycle/stop/detail views using account-bound managed IDs and explicit stop consent, with refresh and nonblocking status.
- [ ] 3.9 Add safe history and uncertain-request reconciliation detail flow: no automatic retry, authoritative state guidance and expert-only acknowledgement; ensure sanitized copy and no false Running/Success.
- [ ] 3.10 Test complete automation flows using synthetic capability registry changes, disabled backend, dirty drafts, stale replies, preflight rejection, double click, task start timeout and receipt ambiguity.

## Phase 4 — trusted reporting, activity and settings

- [ ] 4.1 Refine warehouse toolbar and account/batch selection while preserving legacy filter, island sorting, scroll behavior, per-backend report scope and unknown-versus-zero invariants.
- [ ] 4.2 Consolidate exports into a discoverable menu with Copy CSV/Island text and Save CSV/JSON/TXT, with unchanged content and clear feedback; test partial batch errors and empty/filtered reports.
- [ ] 4.3 Create a human-readable Activity view from available sanitized events, separate bounded raw diagnostics, and label missing server history honestly rather than inventing an audit stream.
- [ ] 4.4 Consolidate local appearance/reporting preferences and contextual connection controls into Settings while retaining explicit credential deletion and safe persisted preference validation.
- [ ] 4.5 Unify all screen-level loading/empty/error/offline/permission/demo/partial/uncertain messaging, consistency of terminology and localization-ready string sourcing.

## Phase 5 — QA, accessibility, packaging and completion gates

- [ ] 5.1 Verify keyboard-only navigation, macOS accessibility names/roles, screen-reader focus, dynamic/high-contrast text, visual focus and icon-independent status across every critical workflow.
- [ ] 5.2 Review screenshots of all screens, overlays and state variants on macOS in System/Light/Dark at 900x650, 1200x800 and maximized; approve typography, spacing, density, contrast and distinct icons.
- [ ] 5.3 Extend macOS CI packaged Daedalus.app offscreen/on-screen smoke with genuine Fluent imports, safe synthetic data and window resize; confirm no new signing/packaging regressions.
- [ ] 5.4 Run offline pytest, ruff, OpenSpec strict validation, secret scanning, desktop parity, regression and export tests; record outcomes and repair failures before claiming tasks complete.
- [ ] 5.5 Update GUI user guide, screenshots, first-run/setup, shortcuts, advanced controls and support docs; include explicit distinction between secure API connection and Gameforge login and no-SSH primary workflow.
- [ ] 5.6 Perform owner-approved *synthetic* end-to-end usability walkthroughs of the seven ux-blueprint.md journeys and capture action counts, defects and visual signoff; leave live-account acceptance to validate-live-authentication.
- [ ] 5.7 Merge reviewed implementation PRs under itshak identity; reconcile delta specs into canonical desktop-client, archive this change via OpenSpec, update PROJECT-STATUS and verify archive/test hygiene only after all checked gates.

## Design / implementation release gates

Gate A: tokens/icons/navigation reviewed before adding new visual pages.
Gate B: first-run and account flows pass fully offline synthetic review before automation restructuring.
Gate C: no simplified task workflow may ship without backend authorization and ambiguous-receipt regression evidence.
Gate D: reporting parity must hold before removing any legacy page/widget code.
Gate E: visual/keyboard/packaged-app review and explicit completion evidence are mandatory before archive; none of these gates substitutes for real-account production acceptance.

## Deliberate scope separation

The separate active validate-live-authentication change tracks owner-supervised real Gameforge, encrypted browser handoff, keyring persistence, and task/worker production acceptance. This redesign does not modify existing live backend sessions or resolve an unconfirmed game task receipt, and none of these unchecked boxes should be treated as acceptance evidence for that change.