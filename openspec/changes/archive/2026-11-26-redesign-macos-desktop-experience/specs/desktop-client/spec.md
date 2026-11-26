## ADDED Requirements

### Requirement: Coherent macOS-native desktop design system

The Daedalus desktop SHALL provide one centrally defined, accessible PySide6-Fluent-Widgets visual and interaction system for navigation, typography, spacing, surfaces, status, forms, dialogs, tables and inline feedback. It SHALL respect system appearance and user overrides, preserve reviewed legacy warehouse behavior, and avoid inconsistent page-specific palettes or redundant primary pictograms.

#### Scenario: Light and dark appearance

- **GIVEN** the desktop runs on macOS with a supported system light/dark appearance or a locally selected override
- **WHEN** the user opens any supported screen or changes appearance
- **THEN** navigation, cards, icons, tables, input states and dialogs use consistent accessible tokens without text/icon clipping or theme-inappropriate contrast

#### Scenario: Source-resolved icon uniqueness

- **GIVEN** the app registers its primary and utility navigation destinations
- **WHEN** the navigation is constructed
- **THEN** each destination has an unambiguous verified semantic icon, Connection is not represented by the Settings gear, Wine is not represented by the same Play glyph as Automations, and icon-only actions expose accessible names

### Requirement: Unified, account-aware information architecture

The desktop SHALL present Overview, Accounts, Warehouses, Automations and Activity as the main destinations, with clearly identified Connection and Settings utilities; specialized Wine and Construction workflows SHALL remain accessible within the unified Automations experience rather than parallel duplicated task editors. It SHALL retain the current selected account only within the same authorized backend/account scope.

#### Scenario: User enters Wine from Overview

- **GIVEN** a live or synthetic account is selected
- **WHEN** the operator invokes the Wine shortcut
- **THEN** the unified Automations workspace opens with Wine context and the same account selection, without a second independent task editor or dispatch

#### Scenario: Backend identity changes while user is configuring

- **GIVEN** a task draft and account selection belong to backend A
- **WHEN** the operator connects to backend B
- **THEN** the app invalidates A's account-scoped draft/readiness and stale responses, and does not reuse A's token, session states or selections for B

### Requirement: Progressive-disclosure connection experience

The desktop SHALL make verified direct HTTPS with exact-origin OS Keychain persistence the normal first-run/reconnection route, with connection health, demo labeling and troubleshooting presented in understandable states. SSH forwarding SHALL be a separately identified advanced fallback only; neither a Terminal nor a manual SSH tunnel SHALL be required for ordinary approved HTTPS usage.

#### Scenario: First run with protected remote backend

- **GIVEN** the user enters a trusted HTTPS backend origin and valid Daedalus API bearer
- **WHEN** the connection succeeds with the default save preference selected
- **THEN** only the approved exact-origin bearer is saved via an OS credential provider, the desktop shows connected state and an obvious path into Overview, and it does not start tasks

#### Scenario: Secure storage or connection fails

- **GIVEN** the keyring is unavailable, TLS verification fails, or backend authorization is rejected
- **WHEN** the desktop connects or attempts automatic reconnect
- **THEN** it shows differentiated sanitized guidance, never persists a plaintext bearer, never disables TLS checks, never reuses a secret on a different origin, and offers only a safe retry or ephemeral option as appropriate

#### Scenario: User enters demo mode

- **WHEN** the user opens the explicit synthetic preview
- **THEN** the UI prominently marks its backend/data as SYNTHETIC DEMO, disables real task mutations and credential persistence, and does not access saved real game sessions

### Requirement: Contextual account management and recovery UX

The desktop SHALL provide a master/detail Accounts experience where account status, metadata actions, optional monitoring and Sign in on this Mac are understandable and scoped. It MUST keep human authentication assistance and host-side recovery behind capability checks, explicit user initiation and appropriate confirmation, without claiming browser acknowledgment alone authenticates a worker.

#### Scenario: Account needs assisted login

- **GIVEN** an authorized account is unauthenticated and the backend advertises native browser recovery
- **WHEN** it is selected in Accounts
- **THEN** the UI offers one prominent Sign in on this Mac path and explains its account/world binding, manual CAPTCHA possibility, temporary browser, server verification and cancel behavior without showing game credentials

#### Scenario: Recovery cannot proceed

- **GIVEN** a task is active, a prior request is unconfirmed, the backend lacks recovery capability or the assistance ticket is expired
- **WHEN** the user tries to open the relevant recovery action
- **THEN** the UI explains the specific nonsecret blocking state, does not substitute a competing session owner, and does not mark login successful

#### Scenario: Account metadata mutation denied

- **GIVEN** the currently connected controller is read-only or editing is disabled
- **WHEN** the user views Accounts
- **THEN** existing account statuses remain readable and editing actions are disabled with reasons, with no metadata write

### Requirement: Truthful account-first Overview

The desktop SHALL provide contextual account, backend/session and automation/report summaries without inventing game state, and SHALL expose the next safe action for disconnected, ready, partial, paused, needs-assistance and unavailable cases.

#### Scenario: Fresh installed client has no saved connection

- **WHEN** the native application opens without approved backend preferences
- **THEN** it shows a useful connection/demo entry point rather than a blank or implicitly live dashboard

#### Scenario: Snapshot is absent or stale

- **GIVEN** the backend has no authenticated warehouse snapshot, or a recent refresh failed
- **WHEN** Overview renders
- **THEN** it labels the data missing/stale, does not fabricate resources or a fresh timestamp, and routes the operator to a safe refresh or sign-in action

### Requirement: Capability-grounded operation discovery

The Automations workspace SHALL expose discoverable, searchable and categorized operation cards with friendly labels, help and readiness; SHALL distinguish background-dispatchable tasks, interactive-only modules, and unavailable capabilities; and SHALL derive execution permission solely from current backend capabilities, validated metadata and fresh preflight.

#### Scenario: Engine reports an interactive-only operation

- **WHEN** the operator searches for that operation
- **THEN** the catalog may explain it, but the UI does not show an executable Start path or fabricate a background task schema

#### Scenario: Registered task is not ready

- **GIVEN** a matching task is visible but backend preflight reports a nonsecret prerequisite failure
- **WHEN** the user selects it
- **THEN** the app shows actionable readiness guidance and disables Start without generating a task mutation

### Requirement: Task-aware guided configuration with safe fallback

For every dispatchable registered operation, the desktop SHALL provide readable field labels, validated native controls for known supported parameter types/defaults, and task-specific explanatory grouping where supported; it SHALL allow unsupported nested/unknown parameters only through a clearly distinguished, validated advanced editor or mark the operation unsupported. Neither form defaults nor task options may invent game/account identifiers or circumvent the engine's validator.

#### Scenario: Known Wine or Construction task selected

- **GIVEN** the registry supplies a typed schema for a Wine/Construction automation
- **WHEN** the user opens its template
- **THEN** the app presents task-specific fields and unit/required/default guidance through Fluent-compatible controls, without requiring manual JSON composition

#### Scenario: Unknown complex parameter

- **GIVEN** a registered operation exposes an unsupported structured parameter type
- **WHEN** the user chooses that operation
- **THEN** the GUI labels the field as advanced or unsupported and requires explicit validated input rather than guessing a game value or silently discarding it

#### Scenario: Draft becomes stale

- **GIVEN** a form was reviewed against a particular task, account and backend readiness
- **WHEN** the user changes any field, task, account or backend, or readiness becomes stale
- **THEN** the prior review/approval is invalidated and Start cannot emit an unreviewed payload

### Requirement: Clear, guarded automation confirmation and lifecycle

The desktop SHALL separate discovery, configuration/review, running tasks and request history, preserve explicit account-bound mutation consent and authoritative backend validation, present managed task IDs only as expert detail, and never automatically retry an uncertain mutation.

#### Scenario: Operator starts a supported task

- **GIVEN** the selected authenticated account, validated task and config, and fresh backend preflight allow dispatch
- **WHEN** the user reviews a plain-language summary and confirms the exact account/world/task
- **THEN** the GUI sends one account-scoped, uniquely identified request to the existing backend API, protects against double-click and waits for an authoritative receipt before presenting a running state

#### Scenario: Task stop

- **GIVEN** an active Daedalus-managed task belongs to the selected account
- **WHEN** the user explicitly confirms Stop
- **THEN** the desktop sends a targeted stop request using the managed task ID and presents backend-reported progress without stopping unrelated workers

#### Scenario: Launch status is uncertain

- **GIVEN** the backend reports a durable unconfirmed request or an ambiguous transport result
- **WHEN** the user views Automations or attempts another start
- **THEN** the desktop prominently explains manual reconciliation, does not automatically resubmit the mutation, and places acknowledgement behind expert disclosure and explicit verification

### Requirement: Warehouse report parity with polished interaction

The revised Warehouses workspace MUST preserve corrected table scrolling, per-backend report selection, multi-account snapshots, island grouping, unsecured 220K filtering, zero-versus-unknown and the exact CSV/JSON/TXT/grouped-clipboard export contracts while making refresh, filter and export controls coherent and accessible.

#### Scenario: Mixed known and unknown resource values

- **GIVEN** an authenticated snapshot includes a zero amount in one city and missing resource data in another
- **WHEN** the operator filters, groups, copies or exports
- **THEN** known zero remains 0, unknown remains explicitly unknown and no aggregate or export silently replaces missing data with zero

#### Scenario: Partial multi-account request

- **GIVEN** snapshots succeed for one authorized account but fail for another
- **WHEN** the batch result is rendered
- **THEN** the page preserves successful rows, identifies partial failure without private backend error bodies and offers a safe read-only retry

#### Scenario: Filter produces zero visible rows

- **GIVEN** snapshots are present but no city meets the user's 220K filter
- **WHEN** the filter is enabled
- **THEN** the UI states that no rows match the filter, not that there are no warehouses or no connected accounts

### Requirement: Consistent asynchronous feedback and stale-result safety

All GUI API requests MUST be nonblocking, bounded and surfaced through common loading/success/empty/partial/error/permission/offline states. A response from a previous backend, account selection or draft generation MUST NOT update current scoped UI. Safe reads MAY be retried; unconfirmed task starts MUST NOT be retried automatically.

#### Scenario: User switches accounts during a slow snapshot

- **GIVEN** warehouse data is loading for account A
- **WHEN** the user selects account B before the response arrives
- **THEN** A's late response does not overwrite B's current scope and the window remains responsive

#### Scenario: Remote API times out

- **WHEN** a read-only backend call fails while a page is visible
- **THEN** only that page's affected controls show safe retry/staleness guidance and the GUI does not freeze or display tokens

### Requirement: Human-centered Activity and private Settings

The desktop SHALL expose understandable, nonsecret user-visible activity where available, clearly distinguish it from bounded raw local diagnostics and group appearance/reporting/connection preferences into discoverable Settings and Connection controls. It SHALL not fabricate a backend historical audit feed or persist game session material in local UI preferences.

#### Scenario: User requests diagnostics

- **WHEN** the user opens Activity and expands Advanced diagnostics
- **THEN** the application exposes only its bounded sanitized local logs and nonsecret available events, with no API bearer, cookies or worker secrets

#### Scenario: User changes appearance and reports

- **WHEN** the user changes System/Light/Dark or reporting defaults in Settings
- **THEN** the preference applies locally, is validated and privately persisted, without mutating remote game accounts

### Requirement: Accessibility, adaptive layout and visual acceptance

The desktop SHALL provide keyboard-operable, screen-reader-labeled and focus-visible navigation/forms/dialogs, meaningful textual status independent of color/icons, and layouts usable at 900x650 logical pixels through maximized Mac windows. It SHALL be reviewed in light and dark macOS appearance using synthetic content before release.

#### Scenario: Keyboard-only task review

- **WHEN** a keyboard-only user navigates task discovery, changes parameters, views validation and cancels a confirmation
- **THEN** focus order remains logical, the dialog returns focus appropriately, accessible controls are named and no task request is sent on cancel

#### Scenario: Narrow window or large text

- **WHEN** the user resizes to the supported minimum or enlarges UI text
- **THEN** forms and primary actions remain reachable by scrolling/stacking, table overflow is intentional and macOS titlebar controls remain unobstructed

#### Scenario: Visual release gate

- **GIVEN** synthetic flows and automated tests pass
- **WHEN** a redesign implementation is proposed for archival
- **THEN** reviewed Mac screenshots/layouts in both appearance modes, accessibility QA, strict OpenSpec validation, secret scan and packaged-app tests are documented before completion is claimed.
### Requirement: First-class all-account and selected-account workflows

Every user-facing screen that operates on account-scoped data SHALL provide
an unambiguous all-account view or action and a discoverable selection of
multiple accounts wherever the backend supports meaningful, authorized bulk
operation. Safe read-only aggregation SHOULD be one click; scoped mutations
MUST list the affected accounts, require separate explicit approval, preserve
each account's independent game-session ownership, and fail closed if any
prerequisite is missing. Screens for which true multi-account action is not
supported MUST state that limitation rather than silently acting on one
account or pretending that all accounts were processed.

#### Scenario: Print all account warehouses without individually selecting accounts

- **GIVEN** a backend has multiple configured accounts with different session states
- **WHEN** the operator selects All accounts in Warehouses
- **THEN** the desktop requests a single combined read-only report across every
  configured account (including explicit partial failures) with unchanged island
  grouping, 220K filtering, unknown-value handling and clipboard/CSV/JSON/TXT
  output across the included accounts

#### Scenario: Choose a subset of warehouse report accounts

- **GIVEN** several configured accounts are available
- **WHEN** the operator opens Choose accounts and checks a subset
- **THEN** the chosen IDs are displayed with an accurate selection count,
  subsequent Selected accounts reports include only that subset, and the
  nonsecret per-backend selection is retained without changing game account
  enablement or credentials

#### Scenario: Read task status across all accounts

- **WHEN** the operator chooses View all task statuses or View selected statuses
- **THEN** the desktop queries each authorized account, shows running and
  uncertain counts separately, and labels failed accounts unavailable rather
  than fabricating zero running tasks

#### Scenario: Review a mutating automation across selected accounts

- **GIVEN** the operator selects more than one account and a dispatchable task
- **WHEN** the operator reviews the account list, config and multi-account warning
  and explicitly approves the action
- **THEN** the desktop checks preflight for every selected account before the first
  mutating request, uses separate account-bound UUIDs and backend validation for
  each start, and stops dispatch on the first uncertain result without retrying
  or automatically reconciling any request

#### Scenario: One selected account has failed readiness

- **GIVEN** one account in the chosen cohort is not ready or has unresolved receipts
- **WHEN** multi-account preflight runs
- **THEN** no account in that cohort receives a new start request, and the user
  sees exactly which account requires attention


### Requirement: Automatic headless Gameforge authentication with human CAPTCHA only

The Mac desktop SHALL use the prior local `itshak/ikabot` warehouse-bot
authentication lifecycle instead of requiring manual browser login for every
account: first attempt to restore a matching unexpired saved world session;
otherwise log in through the Gameforge lobby in **headless Selenium Chrome**
using securely stored per-account credentials, select the matching game world,
and return only an exact-host secure world cookie to the existing one-time
encrypted server handoff. A visible Selenium Chrome window SHALL open
**only upon detection of an actual user CAPTCHA challenge** and SHALL resume
automatically after the user resolves it. The app MUST NOT solve or bypass
CAPTCHA, fabricate authentication, ship plaintext game secrets through the
backend API or start/duplicate game tasks. If credentials are absent,
the user may supply them once and persist them to a macOS OS-keychain entry
bound to HTTPS backend origin, account ID and world.

#### Scenario: Valid saved session or headless login works

- **GIVEN** an account with an existing verified server session or exact-world
  saved legacy session, or correct stored Gameforge credentials
- **WHEN** the operator chooses All accounts warehouses or automatic login
- **THEN** accounts already authenticated skip login, missing sessions are
  restored or logged in headlessly, and no visible browser or password prompt
  appears when usable Keychain/legacy credentials already exist
- **AND** the server independently verifies world/player and worker ownership
  before any account is reported authenticated

#### Scenario: A real CAPTCHA appears

- **GIVEN** a headless Gameforge login reveals a visible CAPTCHA indicator
- **WHEN** Selenium detects the challenge
- **THEN** only that account opens temporary visible Chrome for the user
  to solve it, no automated CAPTCHA response is attempted, and Selenium
  continues world navigation after the challenge is removed
- **AND** cancellation, timeout or wrong player never authorizes a game task

#### Scenario: A non-CAPTCHA failure occurs

- **WHEN** Gameforge rejects credentials, Chrome fails, the game world
  mismatches, or a normal login times out without a detected challenge
- **THEN** the account is marked unavailable without opening a visible
  browser, leaking credentials or claiming a verified world session

#### Scenario: All-account warehouse run needs some logins

- **GIVEN** a selection of multiple enabled accounts with differing session
  states
- **WHEN** the operator clicks Warehouses All accounts or Selected accounts
- **THEN** the GUI authenticates missing accounts serially using the same
  headless Selenium flow and continues with a combined read-only report
  showing partial failures explicitly, retaining native printing, island
  grouping and export behavior; no game tasks start

#### Scenario: Legacy local warehouse credentials exist

- **WHEN** the operator selects an exact account alias whose previous
  owner-owned `~/.ikabot/config.ini` and `tokens.json` match its world
- **THEN** the Mac may read those source files for the scoped login,
  but it does not modify or upload them, guesses no account association,
  stores new Gameforge credentials only in macOS Keychain, and retains
  the server's existing independent identity attestation
