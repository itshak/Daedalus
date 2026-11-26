# web-control-center Specification

## Purpose
Provide dedicated native web controls for reviewed account-scoped operations.

## Requirements

### Requirement: Reviewed native web operation editors
The website SHALL expose reviewed supported operations through dedicated web-native editors. Catalog-only and read-only views MUST NOT count as completed mutating operations. User-editable JSON task settings and raw plan imports MUST NOT be exposed.

#### Scenario: Operator prepares a supported shipment
- **WHEN** authenticated cities are loaded
- **THEN** actual source and destination city names, resource quantities and fleet options are available
- **AND** the operator reviews the authoritative shipment quote before launch

#### Scenario: Operator queues independently reviewed accounts
- **WHEN** a supported ticket-based workflow is queued for multiple accounts
- **THEN** each account has its own named review and no account-specific city identifiers are broadcast to another

### Requirement: Scoped web receipt history
The website SHALL provide account selection, status filtering, paging and current-page CSV export of bounded controller receipt history.

#### Scenario: A receipt is shown
- **WHEN** a managed task dispatch receipt is displayed
- **THEN** it is not represented as proof of game-operation completion

### Requirement: Military read error clarity
The web control center SHALL use the same authenticated controller military and ship-movements observations as the desktop. It SHALL distinguish a successful empty result from an unavailable account read and map HTTP 503 on those endpoints to a military-specific safe message with connection and refresh guidance, without relaying raw backend errors or initiating game orders.

#### Scenario: Military controller observation is unavailable
- **WHEN** the authenticated military or movements endpoint returns HTTP 503
- **THEN** the web client displays the appropriate military-specific unavailable message for that account instead of a generic backend failure or zero counts

### Requirement: Actual web military unit presentation
The Military page SHALL render each verified city, individual ground unit and ship name, and numeric count in dedicated troop and fleet tables, with totals and observation freshness. It SHALL NOT substitute nested DTO placeholders for unit data. Verified empty city lists SHALL be distinguishable from invalid or unavailable observations.

#### Scenario: Nested city military inventory arrives
- **WHEN** the controller returns a city with nested troops and fleet arrays
- **THEN** the web interface displays every unit name and count, separated by troop and fleet type, without generic controller-details placeholders
- **AND** an explicitly empty array is shown as an observed zero, while malformed or cross-account responses are unavailable

### Requirement: Persistent workspace navigation and warehouse data table
The website SHALL restore the last valid workspace page after reload. The warehouse dashboard SHALL use a sortable data table with city, account, island, resource and capacity columns, search, island/world and resource filters, minimum unsecured stock and the existing 220K filter. Visible totals and exports SHALL follow the filtered report; unknown values MUST NOT be rendered as zero.

#### Scenario: Operator changes warehouse filters or sorting
- **WHEN** the operator selects an island, resource threshold, search term or sort column
- **THEN** the displayed rows and report totals update locally without new game requests and the export follows the visible sorted rows

#### Scenario: Browser reloads on a selected page
- **WHEN** the operator reloads after visiting a valid workspace page
- **THEN** that page is restored; no privileged game payload is persisted for navigation

### Requirement: Bounded private warehouse snapshot reuse
The web dashboard SHALL cache successful account-bound warehouse responses in memory for at most 120 seconds, scoped by operator and account identity, deduplicate concurrent reads and reuse fresh entries when switching scope or returning to the dashboard. Manual refresh SHALL invalidate cached reports and fetch current observations. Expired, failed, offline or invalid observations MUST NOT be represented as current data. Privileged snapshots MUST NOT be stored in persistent browser storage or shared caches.

#### Scenario: Return to warehouse dashboard within freshness window
- **WHEN** the operator navigates away and returns within 120 seconds while online with the same authorized scope
- **THEN** the fresh successful cached data is reused and its fetch time is visible

#### Scenario: Refresh, expiry or network failure
- **WHEN** a snapshot expires, the operator explicitly refreshes or network access becomes unavailable
- **THEN** the dashboard fetches fresh data when online or shows unavailable status; it never replays stale cached data as current

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
The PWA MAY cache public static shell files but MUST NOT store or replay privileged HTML, game snapshots, account details, auth responses or game mutations offline. A mounted authenticated dashboard MAY reuse account-scoped successful observations in volatile memory for at most 120 seconds while online; no privileged data SHALL be persisted in browser storage.

#### Scenario: PWA offline
- **WHEN** the device is disconnected
- **THEN** privileged data is marked unavailable, not represented as a current cached snapshot

### Requirement: Version-gated web deployment
Hosted automatic production builds SHALL occur only on an increasing aligned web version on the production branch. Ordinary pushes, previews, invalid metadata and unavailable history SHALL skip. Explicit authorized manual redeployment SHALL remain possible without removing the persistent policy. Offline CI SHALL continue independently of deployment.

#### Scenario: Ordinary development push
- **WHEN** a main commit does not increase the package version, or a preview branch is pushed
- **THEN** Vercel SHALL skip building it and GitHub CI SHALL still verify the source

#### Scenario: Reviewed version increase
- **WHEN** a main merge increases the version and the package lock agrees
- **THEN** the hosted build MAY proceed under existing project security settings
