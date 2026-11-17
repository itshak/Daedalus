# Desktop Client

## Purpose
Extend the existing native PySide6 GUI to expose every supported engine operation.

## Requirements

### Requirement: Comprehensive task controls
The desktop SHALL expose supported task types through discoverable categories, configuration editors, validation, progress, and error states.

#### Scenario: New registered engine task
- **GIVEN** an engine task has a compatible schema
- **WHEN** the GUI loads the backend task registry
- **THEN** the GUI can present an actionable configuration without terminal keystroke automation

### Requirement: Common local and remote behavior
The GUI MUST use the same API contract in local and remote modes.

#### Scenario: Switching between local and remote
- **WHEN** the user changes backend connection
- **THEN** account status, snapshots and task configuration remain accessible through the same client flows

### Requirement: Native Fluent desktop control panel
Daedalus SHALL provide an installable PySide6 Fluent desktop with distinct Accounts, Operations, Warehouses, Log and Connection views.

#### Scenario: Desktop opens before any backend exists
- **GIVEN** the native UI is installed
- **WHEN** a user launches `daedalus-desktop` without configured accounts or a live server
- **THEN** the window opens without a game login and offers a backend connection form

### Requirement: Existing warehouse reporting controls
The GUI SHALL preserve the unsecured 220K resource filter and provide CSV/JSON export without converting missing resources to zero.

#### Scenario: Warehouse snapshots contain unknown fields
- **GIVEN** the backend returns missing resource amounts
- **WHEN** a user loads and exports the warehouse table
- **THEN** those fields remain unknown rather than being displayed as zero

### Requirement: UI does not block during HTTP requests
The desktop MUST perform backend network requests off the Qt GUI thread.

#### Scenario: Remote backend is unreachable
- **WHEN** an API connection fails or times out
- **THEN** the UI displays a sanitized error without freezing or exposing the bearer token

### Requirement: No premature task controls
The first native UI MUST show engine operations only as a read-only inventory until task validation and exclusive worker dispatch are implemented.

#### Scenario: CLI support exists but no account worker is connected
- **WHEN** the user opens the Operations page
- **THEN** operations are discoverable and cannot be executed from the UI

### Requirement: Reproducible native macOS preview
Daedalus SHALL provide a macOS application bundle built directly from a checked-out source revision and a named desktop entry point.

#### Scenario: CI preview build
- **GIVEN** a clean source checkout with no account credentials
- **WHEN** the macOS packaging job runs
- **THEN** it produces an identifiable Daedalus.app archive without running Ikariam, modifying /Applications, or loading account sessions

### Requirement: Preview signing is not production notarization
Mac packaging SHALL distinguish local ad-hoc signing from a developer-signed and Apple-notarized release.

#### Scenario: User obtains a CI preview artifact
- **WHEN** the user downloads the app artifact
- **THEN** documentation explains that it is a preview and may be blocked by macOS Gatekeeper without developer notarization

### Requirement: Native desktop can inspect attached engine sessions without account secrets
The desktop SHALL show whether configured accounts match authenticated existing IkaBot sessions, obtained only after an explicit user request, without exposing engine authentication credentials or account emails.

#### Scenario: Operator checks existing session attachment
- **WHEN** the operator clicks Check IkaBot sessions
- **THEN** the Accounts view reports attached/not attached without launching a game login or displaying credentials

### Requirement: Connected warehouse view preserves export semantics
The native warehouse view SHALL display real typed snapshots from an existing authenticated session when available while preserving the unsecured-resource filter and zero/unknown distinction.

#### Scenario: Backend does not have an authenticated engine session
- **WHEN** the operator requests a warehouse snapshot
- **THEN** the desktop displays a sanitized unavailable error and does not fabricate a resource report
