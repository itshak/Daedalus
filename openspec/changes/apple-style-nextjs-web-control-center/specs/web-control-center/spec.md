# Web Control Center

## Purpose

Provide an accessible, Apple-inspired, browser-based control center that safely exposes the existing Daedalus backend's web-compatible multi-account management and automation workflows.

## ADDED Requirements

### Requirement: Optional Apple-inspired web experience
Daedalus SHALL provide a responsive, installable Next.js web client for the existing controller. It SHALL use the public `apple-design` skill and Apple HIG to guide purposeful hierarchy, immediate feedback, coherent transitions and visual craft. It MUST NOT start Gameforge/Selenium login, duplicate game networking or expose credentials.

#### Scenario: Open Overview
- **GIVEN** an authorized operator and reachable backend
- **WHEN** the browser opens Overview
- **THEN** actual backend account readiness is displayed without creating any game workers

#### Scenario: Login required
- **GIVEN** a game account lacks a valid authenticated session
- **WHEN** the operator opens account details
- **THEN** only desktop-assisted login guidance is shown, never a browser Gameforge credential form

### Requirement: Accessible, adaptive, fluid and interruptible UI
The web SHALL support light/dark, keyboard/screen reader, touch, contrast, reduced-transparency and reduced-motion experiences. Gesture-driven transitions SHALL update from the current presentation state, track the pointer continuously, allow reversal without jumping and use restrained critically damped motion by default.

#### Scenario: Reduced-motion preference
- **GIVEN** a reduced-motion preference
- **WHEN** a task inspector is opened
- **THEN** a gentle/static transition replaces slide/spring movement and keyboard focus remains usable

#### Scenario: Translucency reduction
- **GIVEN** reduced transparency or increased contrast
- **WHEN** content scrolls below navigation
- **THEN** the navigation remains legible with solid/high-contrast materials

### Requirement: Account-aware cross-screen management
Relevant screens MUST support One/Selected/All configured accounts and keep unavailable separate from zero. Scope changes MUST invalidate mismatched city IDs, drafts, previews and confirmations.

#### Scenario: Mixed warehouse availability
- **GIVEN** one connected and one disconnected account
- **WHEN** All accounts is selected
- **THEN** real available data is shown and the disconnected account is labeled unavailable, not zero

#### Scenario: Switch world during a task
- **WHEN** the operator switches to another account/world
- **THEN** previous account plans and city identifiers cannot be submitted to the new scope

### Requirement: Warehouse and military reporting parity
The client SHALL retain all-account/selected account warehouse printing, island grouping, 220K unsecured threshold, TXT/CSV/JSON exports, and read-only military Troops/Fleet/Movements with timestamps and per-account errors.

#### Scenario: Combined print
- **WHEN** the operator requests an All accounts warehouse print report
- **THEN** one report attributes each actual snapshot to its account and never triggers login or worker activity

### Requirement: Purpose-built task editors and explicit confirmation
Each web-supported task SHALL use real authenticated account-scoped cities/buildings/resources/research/routes/units/offers where relevant, backend preflight and authoritative preview, clear per-account effect review and explicit confirmation. A generic JSON editor MUST NOT be the routine UI. Catalogued but interactive-only actions without audited backend adapters MUST remain non-executable.

#### Scenario: Construction review
- **GIVEN** a fresh building list and available engine preview
- **WHEN** the operator chooses a city, building and target level
- **THEN** actual current state and server-produced cost/queue are displayed before approval

#### Scenario: Unsupported action selected
- **WHEN** an interactive-only menu operation lacks a reviewed controller endpoint
- **THEN** the app displays a reason and does not offer an executable Start control

### Requirement: Safe task lifecycle across accounts
The web MUST reuse server preflight, per-account independent plans, durable unique idempotency IDs, existing task ownership, stop authorization and uncertain-result handling. It MUST NOT auto-retry ambiguous mutations or broadcast account-specific identifiers.

#### Scenario: Multi-account execution
- **WHEN** multiple accounts are selected for an operation
- **THEN** separate owned values, previews and confirmations are obtained before any account's execution

#### Scenario: Timed-out task request
- **WHEN** a mutation times out after the request might have reached the backend
- **THEN** its outcome is shown as uncertain and replay remains blocked until authoritative reconciliation

### Requirement: Private network-only game state in PWA
The PWA MAY cache public static shell files but MUST NOT store or replay privileged HTML, game snapshots, account details, auth responses or game mutations offline.

#### Scenario: PWA offline
- **WHEN** the device is disconnected
- **THEN** privileged data is marked unavailable, not represented as a current cached snapshot
