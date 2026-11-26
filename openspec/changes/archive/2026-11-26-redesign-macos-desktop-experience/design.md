# Technical design — polished Mac-native Fluent UX

## Context and architecture decisions

Retain Python 3.11+, PySide6, PySide6-Fluent-Widgets, native Daedalus.app, a single versioned DaedalusClient API and QThread/Qt signal isolation of network work. Do not move game operations, authentication or authorization into desktop widgets. Keep ADR-001, ADR-003, ADR-004 and the security-boundaries spec authoritative.

Review baseline: desktop/app.py (~1147 lines) owns API workers, SSH, connection lifecycle, account syncing and most routing; pages.py (~1074 lines) combines Connection, Accounts, Operations and Warehouses; task_page.py (~622 lines) defines three almost identical task pages; home_page.py holds basic cards; theme.py/widgets.py hold reviewed visual behavior. The design SHALL reduce coupling, not break existing public interfaces while migrating tests.

## 1. Proposed package structure (design targets, not required names)

- desktop/shell: one FluentWindow, global navigation, backend/account status toolbar, Mac titlebar integration and hotkeys.
- desktop/state: typed immutable read models (BackendIdentity, AccountSummary, OperationDescriptor, OperationDraft, TaskReadiness, ManagedTask, WarehouseSnapshotView, LoginRecoveryView) and a single Qt signal-based session/view model; no secrets in models or signal payloads.
- desktop/services: wrap the existing DaedalusClient and APIWorker with tagged cancellable read requests, per-screen loading, bounded timeouts, capability awareness and generation IDs. The transport is not replaced; queued mutating calls remain single-dispatch and non-retryable.
- desktop/design_system: palette and metrics tokens, reviewed icon registry, status and guidance components, reusable headers/section cards/toolbar, safe dialogs and empty/loading/permission panels.
- desktop/screens: Overview, Accounts master/detail and recovery sheets, Warehouses, Automations workspace, Activity, Settings/Connection; each screen owns view binding and requests, not backend session authority.
- desktop/workflows: UI-only adapters mapping *known* engine capability metadata to task presentation/schema widgets; a fallback renderer for unknown typed params and validated expert JSON. Engine registry remains source of task name, types/defaults and availability.
- desktop/legacy: keep or re-export ScrollTableWidget, OpaqueCardWidget, report formatting/copy behavior, existing titlebar/palette and queued QtLogBridge until replacements pass parity tests.

Split by incremental wrapper/shim migrations, not a big-bang rename. Preserve automation selection and exposed signals needed by test_desktop, test_desktop_parity, test_desktop_redesign and existing packaging. Remove duplicate page instances only after equivalent Wine/Construction deep links and tests exist.

## 2. State ownership and async boundaries

Root view state is keyed by exact connected HTTPS origin (or explicit loopback/demo origin), account ID, capability version/revision and request generation. Switching origin invalidates account selections, cached snapshots, task drafts, assistance tickets and old responses. Backend account state is authoritative. Safe local preferences (appearance, filters, last nonsecret view) persist privately; tokens remain in origin-bound OS Keychain, never in widget state snapshots, JSON/TOML, debugging events or screenshot fixtures.

All read actions are off the main Qt thread. Tag each asynchronous request with backend generation, account ID and selected draft/revision; ignore stale completions after switches. Allow independent read refreshes for Overview/Warehouses/Tasks rather than a global busy spinner, while preventing duplicate *mutating* submissions. Show stale/partial data explicitly if a read fails; never present cache as verified live state. Reconnect must query health/accounts/capabilities without launching or replaying any automation. Multi-account selection does not blend account histories.

For task launches, preserve server-side preflight/validation, explicit user confirmation, account lease, request UUID/idempotency and durable receipt semantics. The form's Reviewed state invalidates on account, task, metadata, readiness, or parameter change. Optimistic UI may show Requesting but not Running until authoritative receipt. An ambiguous response must route to reconciliation and forbid auto retry. All Stop actions use managed task ID and an account-scoped confirmation.

## 3. Design-system implementation contract

Create one vetted icon registry mapping semantic identifiers to verified qfluentwidgets FluentIcon or an in-repo single-stroke Qt vector asset. The registry MUST reject duplicated primary navigation icon assignments (including silhouette-equivalent duplicates); a CI test shall enumerate declared IDs and contrast across themes. Icon-only controls have accessible names and text tooltips. Settings gear and Connection chain/plug MUST be unmistakably different; use separate glyph families for Wine, Construction and Automations. Do not use Unicode emoji as shipping nav icons.

Use centralized dimension, typography, color and elevation tokens in Qt-friendly code. Theme tokens resolve from OS appearance by default and respond to qfluentwidgets themeChanged. No ad-hoc page QSS palettes that conflict with native light/dark. Preserve reviewed light OpaqueCardWidget and smooth ScrollTableWidget implementation; improve styling with visual snapshots rather than replacing established behavior. System font metric, text scaling and DPI are honored.

Build named reusable patterns with explicit states: PageHeader, AccountScopePicker, BackendStatusPill, EmptyState, PermissionState, Skeleton/Progress, InlineValidationMessage, TaskCard, SectionCard, LabeledField, ConfirmationSummary, SafeActionFooter, AsyncToolbar and DetailDrawer. Prefer existing Fluent controls and qfluentwidgets dialog/InfoBar classes where verified; wrap raw Qt numeric widgets where no proper Fluent control exists. All patterns expose keyboard focus/accessible labels, support compact widths and never display secrets.

## 4. Information architecture and screen routing

Overview is the initial connected landing page, Connection the first-run landing when no approved backend is saved. Routes are semantic (overview, accounts, warehouses, automations?template=wine, automations?template=construction, automations?category=..., activity, settings?section=..., connection), not independent duplicate task widgets. A route carries a nonsecret selected account and presentation filter only. Nav and Home quick actions use the same route dispatcher. Read-only capability catalog is subordinate to Automations. The Settings destination owns Appearance and Reporting controls while the connection state/status affordance remains conveniently reachable. Unknown backend capabilities lead to visible explanatory placeholders, not crashes.

The Account detail content depends on combined authoritative session, permissions and pending nonsecret assistance. Only show Sign in on this Mac if the native browser capability is advertised; preserve all explicit consent, one-use encrypted ticket and server attestation. Host-side recovery is gated by separate disclosure and capability. When a worker is busy or lease blocked, explain unavailability without creating or replacing sessions. No UI element can fabricate authenticated status.

## 5. Task-specific presentation and schema negotiation

Each operation descriptor contains backend task name/kind, ability to dispatch, discovered params and explicit supported data types/defaults, plus non-authoritative UI metadata (friendly title, description, grouping, icon and help). UI-only adapters NEVER change backend parameters, write out-of-schema fields, infer sensitive game values or generate unvalidated city IDs. Controlled inputs map to typed backend metadata. Build task-specific presentation progressively:

- Wine: tavernManager, alertLowWine — target cities if securely supplied, alert/consumption settings and intervals with proper units; use conditional settings only if supported by descriptor.
- Construction: constructionList, research — planning or priority steps only to extent the canonical registry can validate; do not fake a scheduling primitive in UI.
- Alerts/monitoring: alertAttacks, searchForIslandSpaces — readable polling/threshold settings and no accidental notification-secret input.
- Resources/trade: sendResources, resourceTransportManager, consolidateResources, distributeResources, buyResources, sellResources, donationBot — target, quantity and policy controls only with validated allowed values; preserve expert JSON for unsupported nested structures.
- City/military/other: loginDaily, activateMiracle, activateShrine, trainArmy, UpgradeUnits, attackBarbarians, autoBarbarians, autoPirate and advanced engine tasks — typed forms or explicitly honest unsupported/manual descriptions. Do not imply interactive-only capabilities are background automation.

A form renderer may mark fields unsupported and require expert input or disable launch; complexity is not a license to guess a game value. User-created presets are a later feature only if backend/UI schema and safe private persistence are separately specified. All summaries are derived from the exact payload to be submitted and match the consent dialog.

## 6. Compatibility, migration and provenance

Maintain warehouse reporting functions in daedalus.reporting and existing offline export contracts; preserve unknown/zero, per-backend report selection, mixed success/error batch results and island grouping. Do not change game engine or REST schema just for visual design. For missing server metadata, degrade gracefully to an honest generic widget; any new metadata requirement needs a separate additive versioned API proposal before UI implementation.

Ship incremental internal refactors behind stable UI facade/tests: stage 1 tokens/navigation, stage 2 Overview/Connection/Accounts, stage 3 unified Automations and contextual login, stage 4 reports/activity/settings, stage 5 polish/test/release. If refactoring AccountPage/TasksPage creates transient compatibility concerns, add adapters in tests/production until parity is validated. Preserve upstream MIT attribution and GPL-3.0 licensing/provenance; reviewed legacy code only, no source history, account secrets or private assets.

## 7. Verification and acceptance

Automate static icon uniqueness, state mapping, keyboard focus/tab order, secret sanitization, no duplicate mutating requests, stale-generation rejection, exact-origin Keychain reuse, safe demo gating, warehouse report parity and all required permission transitions. Extend offscreen PySide6 interaction tests and CI's genuine Mac Qt build; use controlled fixtures and screenshot output free of credentials. Snapshot/layout inspection on Mac light/dark at minimum/norm/max window sizes is a human signoff gate, not automatically satisfied by green Linux tests.

Run pytest, ruff, OpenSpec strict validation, secret scan and macOS packaging jobs before closing individual tasks. Mark a checkbox only with test evidence in PR. Completion requires owner approval of end-to-end synthetic UX walkthroughs and baseline visual comparisons. Live Gameforge, daemon restart, task receipt/keyring production acceptance and production cutover remain blocked on independent validate-live-authentication checks and MUST NOT be inferred from this UI implementation.

## 8. Rejected alternatives and risks

- Reject full Electron/Web rewrite: loses native app and existing reliable Fluent warehouse widgets.
- Reject three separately maintained Wine/Construction/Automations pages: inconsistent UX and duplicated state.
- Reject direct browser/engine interaction from GUI: violates ADR-001/003/004 and account ownership.
- Reject hiding hard safety constraints merely to make UI simpler. Disclose them as understandable explanations and maintain backend checks.
- Risk: qfluentwidgets version differs across environments. Verify widget imports in CI and provide lightweight wrappers before choosing a specific class.
- Risk: premium visual effects harm contrast, scrolling, performance, Mac signing or resize. Favor accessible, static native-feeling surfaces and smoke-test packaged app.
- Risk: visual polish masks readiness gaps. Every nonready backend/capability remains visibly disabled with next-step guidance.