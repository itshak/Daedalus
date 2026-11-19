# UX blueprint — Daedalus for macOS

This file defines the target UX and serves as the implementer's screen-by-screen checklist. It describes intended behavior, not current implementation or real-account verification.

## 1. What the source audit found

| Present surface and evidence | Keep | Redesign |
| --- | --- | --- |
| FluentWindow navigation in desktop/app.py | Familiar persistent rail, native titlebar adaptation | Both Appearance and Connection use the same settings icon; Wine and Automations use Play; too many parallel destinations |
| HomePage account selector and action cards | Account-first, contextual shortcuts, verified state | Shallow status copy, dead-end unavailable actions, weak overview and inconsistent spacing |
| ConnectionPage | Working TLS/Keychain default, no mandatory SSH; demo supported | Flat URL/token/actions; advanced SSH and synthetic preview need a clearer first-run/connected state |
| AccountsPage | Safe account table, metadata editing, native Mac browser login, lease-aware assistance | Ten-plus controls share one vertical page and appear with equal prominence despite very different risks |
| TasksPage (base/wine/construction) | Validated schema, preflight, controlled start/stop, request ledger, advanced JSON | Three instances of the same giant editor; parameter scroll capped at 225px; no operation-specific language or visual grouping; running/history tables compete with setup |
| OperationsPage | Discoverable registry of supported and interactive-only engine functions | Duplicates automation discovery; overstates affordance of read-only operations |
| WarehousesPage | Reviewed legacy table scrolling, grouped island reports, 220K filter, copy and CSV/JSON/TXT, unknown != zero | Clearer multi-account scope and data provenance, export menu and zero/unknown treatment, polished loading/empty states |
| AppearancePage, LogPage | System/light/dark preferences, bounded sanitized log | Settings scattered across bottom destinations; logs are developer-oriented; activity/recovery require human-friendly summaries |
| APIWorker and existing safety rules | Off-thread network calls, capability checks, safe error strings | Shared loading/cancellation/stale-reply handling and consistent view state, not new transport logic |

## 2. Product language and interaction rules

Daedalus is a Mac desktop *control center*, not a form exposing an engine. Prefer nouns and actions people understand: Connect, Sign in, View warehouses, Create automation, Start, Stop, Try again, Review request. Reserve engine function names, request IDs, PID, host recovery and JSON for details/advanced modes. Say what the app knows, what is unknown and what the user can do next. Never imply a waiting/recovery acknowledgement itself authenticates a worker.

One primary action per panel; secondary actions are quieter; destructive or ambiguous changes receive clearly scoped confirmation. No surprise task starts. Use progressive disclosure: simple path first, precise expert path preserved under disclosure. Buttons name the action; disabled controls explain why and give a next step. Always keep the selected backend and account visible.

## 3. Window and navigation

- Top: macOS traffic-light-safe title region, app identity, connected backend/environment indicator, persistent account picker when appropriate, contextual toolbar actions.
- Primary sidebar order: Overview (home glyph), Accounts (people), Warehouses (stacked storage/box), Automations (unique spark/gear-with-motion symbol), Activity (clock/history). Only five everyday destinations.
- A secondary sidebar/toolbar utility: Connection (distinct link/plug glyph) and Settings (gear); About/help may live in macOS menu or Settings. Appearance is a Settings section with distinct paintbrush/sun visual, not a second primary-level gear.
- Wine (glass/cup glyph) and Construction (building/hammer glyph) become prominent automation templates/filters/shortcut entry points inside Automations. Existing deep links into wine_page and construction_page must redirect to equivalent selected templates without losing account or draft.
- Explore/Operations becomes a read-only Capability Catalog within Automations, clearly labeling interactive-only, background-enabled and unavailable capabilities. Do not mislabel interactive modules as one-click background jobs.
- No two sidebar destinations may share the same pictogram. Icons must be semantic, 16–20pt equivalent, single-weight vector/Fluent-compatible; use verified FluentIcon members or a small vetted in-repo SVG fallback, not unreviewed Unicode emoji, arbitrary generic Play or mismatched third-party filled icons.
- Selection/collapse state is stable when resizing or changing pages. Return to last safe page after reconnect; if backend changes, clear backend-scoped identity/drafts and explain why.
- Keyboard: Cmd+, opens Settings; Cmd+R refreshes the current read-only view; Cmd+F focuses in-page search where applicable; Escape closes disclosure/modal without dispatch. macOS menu/VoiceOver conventions take priority over invented shortcuts. Never bind Return to a mutating Start without focused confirmation.

## 4. Visual language and component rules

- Fluent components with Mac restraint: qfluentwidgets NavigationInterface, CardWidget, PushButton/PrimaryPushButton, ToolButton, ComboBox, SearchLineEdit/LineEdit, SwitchButton, CheckBox, InfoBar, TeachingTip, MessageBox/Dialog, TableWidget, ProgressRing, segmented/tab controls where present. Confirm actual library API and availability before usage; QSpinBox/QDoubleSpinBox and PySide6 controls may be wrapped/styled where Fluent has no equivalent.
- Define one centrally owned token catalog. Proposed baseline: spacing scale 4/8/12/16/24/32px; page max readable content width ~1100px; cards 12–16px corner radius; body 13–14pt equivalent using system text and Dynamic Type compatible Qt font metrics; action/control height ~32–38px on Mac; generous but efficient table row density. Tune against actual macOS renders instead of hardcoding unsupported system font names or platform-private APIs.
- Surface layers: window background, sidebar, cards, grouped controls and subdued dividers. Preserve OpaqueCardWidget's good light-mode legibility, harmonize it with dark mode, keep contrast and affordance; don't imitate opaque acrylic everywhere. Native-feeling depth from hierarchy/spacing rather than bright gradients.
- Palette uses semantic tokens: primary action, neutral, success/ready, warning/recovery, danger/blocked, information, disabled, selection. Color is never the only status cue. Default respects system color scheme; Light/Dark overrides are stable and reversible.
- Text hierarchy: descriptive page title, short subtitle only when needed, section heading, field label, helper/error text; never a wall of CaptionLabels or equal-weight buttons. Use concise tooltips for technical terms and help links for details.
- Responsive window: support first launch at 900x650 logical pixels, comfortable 1200x800, and maximized; scroll vertically rather than clipping form controls. At narrower widths sidebar collapses, dense tables retain deliberate horizontal scrolling, toolbars wrap/overflow and forms stack. Respect titlebar safe region.
- Motion: subtle hover, selection, loading and modal transitions only; obey OS reduced-motion preference where exposed. Avoid pulsing/bouncing or delayed interactions that hide status.
- Visual QA: consistent padding/alignment, no truncated controls or overlapping titlebar, meaningful focus outline, correct resize, crisp 1x/2x assets, no light/dark low-contrast icon surprises.

## 5. Screens and primary journeys

### A. First launch / connect

A friendly setup panel: (1) server address HTTPS field with contextual example, (2) API access token (masked by default, deliberate reveal action), (3) Connect primary button. Secure Mac Keychain saving is selected by default with a direct explanation and explicit opt-out. Validate URL scheme/origin locally before attempting a request. Show Connecting / Connected / Unauthorized / Unreachable / Certificate not trusted / Keychain unavailable as distinct states, with actionable safe copy. Successful connection shows backend label, identity scope, session count and a Continue to Overview path. On next launch, attempt only an approved exact-origin Keychain reconnection; never auto-start or resume game operations. Forget access must be visible and deliberate.

Offer Try synthetic demo as a separate non-production entry at first run; mark its entire window and snapshots SYNTHETIC DEMO, disable mutating controls and never save the demo bearer. Hide SSH fallback behind Advanced networking: trusted host input, explicit connect, verified host key, visible ownership and cleanup. Do not put SSH in onboarding or imply it's mandatory.

### B. Overview

Header: backend health and selected account identity/world. One compact Ready / Needs sign-in / Offline / Paused / Uncertain request state with clear next action. Cards: Warehouse snapshot (last observed time, never fabricated), Running automations (count/state and quick view), Account session (what is verified), Recent activity (last safe events). Quick actions: View warehouses, Create automation, Sign in when blocked. Empty state: connect/add account/demonstration as appropriate, not blank cards. Cards link to exactly the same account context in destination screens.

### C. Accounts / sign-in / recovery

Use left account list/table with world/player/label, session health and small meaningful badges; right detail pane with summary and one contextual primary button (Sign in on this Mac, Check session, or View automations based on backend state). Separate editing via Add account and an Edit details sheet/drawer, with danger zone for disable/remove and contextual confirmation; explain when backend disables editing. Keep report-selection controls in Warehouse scope with optional per-account preference, not a prominent Accounts checkbox.

A Sign in on this Mac guided sheet explains opening a temporary browser and secure single-use handoff, which account/world is targeted, that CAPTCHA is manual, and that the authoritative backend must independently verify the result. Distinct states: browser opening, waiting for human sign-in/CAPTCHA, validating, success, failed verification, canceled, stale/expired ticket, existing active task, not supported. Never display tokens/cookies or claim success before independent worker verification.

Advanced recovery appears only upon explicit expansion and appropriate backend capability. Host-side guide/prepare/rebind and nonsecret manual assistance are separate guided expert flows; retain lease rules, warnings and explicit acknowledgement. Monitoring shows on/off/needs attention clearly with contextual consent.

### D. Warehouses (keep the good parts)

Keep scroll-corrected Fluent table and current reporting semantics. Top toolbar: account or multiple-account scope, Refresh, filters (220K+ and Group by island), and single Export menu containing Copy CSV / Copy grouped text / Save CSV / JSON / TXT. Do not break existing copy/export shortcuts or file formatting. Show last snapshot time *only if provided by backend* and data provenance (live vs synthetic/unknown). Table handles city, island, resources, unsecured amounts and unknown values; unknown prints dash/Unknown, zero prints 0. Group headers are meaningful and keyboard accessible. Aggregate/summary totals include only known amounts and disclose missing counts. Empty states distinguish no accounts, no authenticated session, no city data, filtered-out rows, partial batch failure. A failed account must never silently become a zero warehouse.

### E. Automations

One workspace with three clear areas, not three unrelated pages: Discover (search/category/template gallery), Configure & Review (selected task and account), Running/History (list with state and a focused detail panel). Wine and Construction are featured entry templates; the general catalog includes alerts, resources/trade, city management, military and advanced features.

Discovery cards show friendly task name, 1-line description, category, capability availability, whether it is interactive-only, and setup effort. Choosing a task must not execute anything. Selection preserves only compatible draft settings and never silently migrates config between accounts or tasks.

Use explicit task presentation adapters layered over the validated backend registry: common fields use friendly labels, unit-aware SpinBox/slider where safe, toggles/switches, dropdowns for backend-provided enums, account/city selector for backend-provided valid entities, time/interval controls and grouping for nested arrays/steps. Complex Wine and Construction get carefully designed dedicated form sections and guided presets; other frequently used task types (alerts, transport, trade, construction, research, army) receive task-specific templates one by one. Defaults and preset constraints must come from reviewed capability metadata, never fabricated game identifiers or amounts. Unknown/nested values remain in a clearly labeled Advanced structured JSON editor with validation and nonsecret preview, not an unsafe guessed widget.

Bottom review strip: concise summary of selected account, automation, only changed settings, required prerequisites, estimated side effect where known, and current backend preflight. Start disabled while dirty/unreviewed/unavailable/unconfirmed/stale. After explicit review, a confirmation modal shows exact account/world, task, risk and effect with a separate explicit approval; preserve existing backend confirmed flag, request ID and idempotency. Do not add extra confusing authorizations beyond safety-required consent. Pending UI states prevent double click, while authoritative backend remains source of truth.

Running tab: friendly title, account, started/status, stop action only for Daedalus-managed task ID and explicit confirmation. History: human-readable success/failure/unknown states; request IDs and PID in copyable Details, not top-level navigation. Unconfirmed launches enter prominent Needs reconciliation (never retry automatically) with instructions to inspect actual game/backend state and an expert-only acknowledgement. Do not turn reconciliation into a one-click success-looking button.

### F. Activity and Settings

Activity timeline: user-readable connection, account, session and task events derived from nonsecret server/client data. Filters by account/type/severity; click event for details and raw local bounded diagnostic log under Advanced diagnostics. Never fabricate backend audit events, log secret-bearing payloads or imply complete historical records where backend has none.

Settings groups: Appearance (System/Light/Dark), Reporting (warehouse filter/group default and account selection), Connection (saved exact-origin server, reconnect, forget access, advanced SSH), About/Diagnostics. Connection also has a dedicated accessible navigation utility/status popover; no duplicate unlabeled gear. Preferences are local, private and validated; backend-owned account/session settings are not represented as Mac-only settings.

## 6. Required screen states and microcopy

Every async or gated surface explicitly supports: not configured, loading (skeleton/spinner; block only affected action), ready, empty, partial success, stale/offline, permission-disabled, needs human assistance, validation error, timeout/retryable read, blocked mutation, ambiguous/unconfirmed mutation, and synthetic demo. Use human-centered, secret-free messages such as: 'Can't reach this server. Check the address or your network.'; 'Sign in needed for this account before live warehouses can load.'; 'Start wasn't confirmed. Check the running task and game state before reconciling. Daedalus won't retry it.' Messages must never contain backend exception bodies, bearer, cookies, passwords or personal account email.

All operations that could mutate game state require a current account, fresh capability/readiness, review/confirmation, and state-aware refresh. No automatic retries of mutations after network failure; safe read-only refresh may offer retry. Stale responses tagged with old account/backend/draft generation are discarded.

## 7. Accessibility and test matrix

- Mouse, keyboard-only and VoiceOver-compatible names/roles/tooltips for icons, inputs, status, tab order, dialogs and data tables; focus returns to the initiating control after close; no icon-only unlabeled destructive control.
- Differentiate success/warning/error by icon and text, not hue. Target WCAG 2.2 AA text contrast (4.5:1 normal / 3:1 large) and visible keyboard focus; verify with rendered screenshots.
- Exercise Mac system light/dark, override modes, high contrast where supported, default/larger text and 1x/2x displays; ensure no sensitive text in screenshots, test fixtures or logs.
- Synthetic scenario matrix: never-connected, expired token, untrusted TLS, keyring missing, backend switched, one/many accounts, missing warehouse values, no task registry, task disabled, rejected prerequisites, managed running task, ambiguous receipt, login ticket expired, demo mode, read-only controller and rapid account switching.
- Screenshot/golden visual review for all destinations at 900x650, 1200x800 and maximized, both themes; CI assertions must not rely on nondeterministic pixel-perfect font rasterization across operating systems. Use semantic widget-tree assertions for logic and macOS artifact screenshots for human approval.

## 8. Acceptance walkthroughs

1. Fresh install: choose demo or enter HTTPS+API token, connect without Terminal, relaunch with saved Keychain credential, distinguish real/synthetic and know how to forget access.
2. Multi-account: select one account, see accurate authentication state, navigate Overview → Warehouses → Automations with scope preserved; backend switch never uses old token/selection.
3. Warehouse: load 1+ account reports, distinguish 0 vs unknown, apply 220K filter and island grouping, copy/save all formats with unchanged semantics.
4. Recovery: reach Sign in on this Mac in one contextual action, cancel safely, and receive accurate success/failure/lease/prerequisite feedback (synthetic first; live acceptance is separately gated).
5. Task: choose Wine/Construction/Alerts/Resources, configure through normal widgets, review exact account, confirm once, see running status, stop with confirmation; never be forced to write JSON.
6. Error: disabled read-only controller, missing prerequisites, timeout and unconfirmed request all produce correct nonsecret guidance without duplicate task dispatch.
7. Visual: designer reviews the complete window/navigation, list/detail, modal, empty/partial, hover/focus and light/dark cases and finds no duplicate icons or dead-end workflows.