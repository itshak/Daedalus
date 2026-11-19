# Redesign the complete native macOS desktop experience

## Why

Daedalus now has a functional native PySide6/Fluent shell, warehouse reporting, account metadata, assisted authentication, direct HTTPS/Keychain connection, and guided task dispatch. However, additions were implemented incrementally instead of as a cohesive product. The result is a functional but visually inconsistent app with cluttered account/recovery buttons, three separate automation screens, overly technical task configuration, redundant navigation, indistinguishable icons (Connection and Appearance share FIF.SETTING; Wine and Automations share FIF.PLAY), small fixed-height parameter forms, and raw diagnostics competing with daily actions. An app that can control real, persistent automation needs clear hierarchy, trustworthy status, polished feedback and excellent keyboard/mouse accessibility.

The reviewed legacy warehouse UI is a strength: preserve its Fluent shell vocabulary, opaque light-theme cards, scrolling table behavior, island grouping, 220K filter, export semantics and nonblocking UI. This is a ground-up UX/visual-system redesign of the *newer* product surface, not a rewrite of those proven behaviors.

The archived guided-automations-and-desktop-redesign change (#56) already implemented account-first Home, typed task forms, preflight, default HTTPS/Keychain and optional SSH. This change starts from that implementation and supersedes only its presentation/interaction shortcomings; it MUST NOT regress the shipped secure connection or automation safety.

## What Changes

- Establish a documented Daedalus desktop design system: native-feeling macOS window structure, restrained Fluent components, semantic typography/spacing/materials, clear focus and hover states, harmonious light/dark appearance, fluid resize behavior, icons with unique meanings, and reusable status, cards, empty states, tables, forms, dialogs and toasts.
- Redesign information architecture around Overview, Accounts, Warehouses, Automations and Activity; make Connection a uniquely identifiable connection/status destination and combine appearance/preferences inside a coherent Settings destination. Distinguish Wine/Construction as context-aware automation templates or views rather than duplicate primary-level task editors; retain direct access to their workflows.
- Build a first-run guided Connect/Explore demo experience, understandable persistent secure HTTPS connection, visible status and reconnection, and an advanced-only SSH fallback. Never ask routine users to operate a tunnel, paste a token more than once after approved Keychain saving, or confuse the Daedalus API bearer with Gameforge credentials.
- Make Accounts a clear master/detail workspace, with primary per-account status and Sign in on this Mac action; use progressive disclosure for human assistance and expert host recovery instead of one crowded flat button strip.
- Replace generic introspection-looking task editors with task-aware GUI schemas, descriptions, searchable category cards, safe presets, appropriate native Fluent controls, contextual validation, summary/review/confirmation, live run status and clearly separated uncertain-request reconciliation. Keep unknown parameters in a safe advanced fallback rather than guessing values.
- Preserve and polish the existing warehouse reporting data logic and controls: concise multi-account filters, island grouping, 220K threshold, copy/CSV/JSON/TXT, unknown-versus-zero, informative empty/loading/error states.
- Introduce a shared per-backend/per-account UI view model, navigation/selection preservation, asynchronous requests and coherent notification/refresh behavior so pages never disagree about state.
- Define implementable stages, offline synthetic/Qt interaction tests, visual regression baselines, accessibility checks and review gates before declaring the redesign ready.

## Capabilities

### Modified Capabilities
- desktop-client: new native information architecture, visual design system, guided account/login/automation/reporting flows, status and interaction contracts. No change to the existing REST/IPC security model.

## Compatibility and dependencies

- Follow ADR-001 (one upstream game engine), ADR-003 (single-owner login/recovery), ADR-004 (one API for local and remote clients), ADR-005 (licensing) and the existing canonical desktop-client and security-boundaries specs.
- Use PySide6 with PySide6-Fluent-Widgets (qfluentwidgets). Reuse reviewed migrated widget behavior rather than importing the private legacy project, its history, saved credentials, or assets of unverified provenance.
- Design for current engine registry capabilities and backend permission/readiness flags; never render a feature as executable solely because it is listed in the inventory.
- The separate active validate-live-authentication change remains responsible for owner-supervised real Gameforge/browser/keyring/worker tests. Redesign work shall not claim those live acceptance gates are complete.

## Non-goals

- No new game operations, engine replacement, API bypass, change to task start/stop idempotency or ownership, unattended CAPTCHA, raw game-cookie storage, credential transport, automatic task resumption, backend deployment/cutover, production server modification, or migration of real private data.
- No Electron/browser-shell conversion, macOS-private API dependency, gratuitous glass/animation at the expense of readability, or blanket stylistic replacement of the already-good warehouse reporting controls.
- This OpenSpec change is a planning artifact. UI implementation, release verification and archival are separate future stages and remain unchecked in tasks.md.

## Success criteria

A first-time user can connect and understand account status; a regular user can inspect warehouses, sign in when needed, configure a supported automation with ordinary controls, review/confirm it, and monitor or stop it without encountering JSON, SSH, request IDs or arbitrary PIDs. Expert functions remain discoverable but secondary. Critical mutations retain explicit authorization and backend validation. Every screen looks and behaves like one polished Mac application in both color schemes, at a range of window sizes and with keyboard navigation. Detailed screen mapping, component patterns, states and gates are in ux-blueprint.md, design.md and the delta spec.