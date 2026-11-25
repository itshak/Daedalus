# Original full-parity targets (historical, not accepted)

## Original target: controller-api

## ADDED Requirements

### Requirement: Reviewed versioned operation contracts
The controller SHALL publish reviewed versioned per-operation availability, draft schemas, inventory requirements, scope and platform policy; it SHALL validate operation-specific drafts and independently enforce authenticated account ownership, typed field bounds and eligibility. AST-inferred opaque parameters MUST NOT be treated as user-editable configuration.

#### Scenario: Invalid city or unknown parameter
- **WHEN** a client submits a draft with another account's city or unknown fields
- **THEN** the controller rejects it before any game mutation

### Requirement: Authoritative effect preview and receipt
The controller SHALL provide side-effect-free operation previews with scope, normalized effect summary, revision or expiry, and a validated execution pathway with unique request IDs, durable receipts and independent live revalidation. One-shot actions MUST NOT be restored as ongoing jobs.

#### Scenario: A previously reviewed preview is stale
- **WHEN** a launch references a stale or mismatched preview
- **THEN** the controller rejects it and requires a fresh preview and review

#### Scenario: A selected-account batch is requested
- **WHEN** supported batch execution is approved
- **THEN** each account uses its own validated plan and receipt, and uncertain dispatch stops further execution without automatic replay


## Original target: desktop-client

## MODIFIED Requirements

### Requirement: Native GUI task controls require confirmation
The desktop SHALL offer a Tasks interface with a configured account, a built-in background task selector, dedicated native controls, and explicit operator confirmation before sending a mutating request. Editable JSON, raw-plan imports and manual engine configuration overrides MUST NOT be exposed.

#### Scenario: Operator selects task start
- **WHEN** the operator chooses a task for a particular world/player
- **THEN** the UI presents a confirmation identifying that account and task
- **AND** it sends the request only after confirmation

### Requirement: Native task creation requires user confirmation
The Fluent GUI SHALL provide discoverable operation-specific native editors and MUST require an explicit authorization checkbox and confirmation dialog before sending a game task request.

#### Scenario: User does not confirm
- **WHEN** the user opens Tasks but leaves confirmation unchecked
- **THEN** no task-launch network request is made

### Requirement: Parameter-aware native task configuration
The desktop SHALL render task-specific native controls derived from reviewed domain schemas and authenticated game data. Opaque engine payloads MUST NOT be user inputs.

#### Scenario: A task has an optional numeric parameter
- **GIVEN** the registered alert polling interval has a verified numeric default
- **WHEN** the operator selects the alert
- **THEN** the GUI shows an appropriately bounded numeric field

#### Scenario: A complex task has nested parameters
- **WHEN** the operator selects the action
- **THEN** the GUI offers dedicated domain selectors and editors, or an explicit unavailable state until the editor is implemented
- **AND** no JSON fallback is offered

### Requirement: Explicit form review before task dispatch
The desktop MUST NOT launch using unreviewed native form inputs and MUST retain explicit checkbox, confirmation dialog and backend validation for every game-state-changing task request.

#### Scenario: A parameter form has edits that have not been applied
- **WHEN** any input, account, or preview changes after review
- **THEN** the desktop invalidates prior approval and requires a fresh review

## ADDED Requirements

### Requirement: Desktop cross-platform operation parity
The desktop SHALL provide the same supported operation contracts and field semantics as the web, including game player names and current/selected/all account scopes, using native Fluent controls and independent per-account plans. The complete registry and parity matrix SHALL be the coverage gate; secure local-only functionality SHALL remain available through reviewed local workflows.

#### Scenario: Operator configures transport
- **WHEN** authenticated cities are loaded for the selected account
- **THEN** actual city names appear in source and destination dropdowns, resource amounts in numeric controls, and valid fleet and schedule options in native controls
- **AND** the reviewed payload uses underlying verified IDs without exposing them as manual inputs

#### Scenario: Account changes after selecting a city
- **WHEN** the operator changes account
- **THEN** old options, draft and approval are invalidated and only the new account's data is selectable


## Original target: engine-integration

## ADDED Requirements

### Requirement: Complete source-audited operation coverage
The integration SHALL inventory the union of public menu actions, registered tasks and interactive submenus, and SHALL maintain dedicated reviewed adapters for supported operations. Missing registry rows or missing required platform coverage SHALL fail the parity gate. Interactive-only operations MUST NOT be executed through arbitrary CLI prompt injection or unreviewed module dispatch.

#### Scenario: Upstream adds an operation
- **WHEN** the vendored engine inventory changes
- **THEN** CI reports any operation without a reviewed coverage entry, contract and test mapping

### Requirement: Game-authoritative native planning
Engine adapters SHALL derive city, building, unit, offer, island, route, schedule and other game-dependent options from authenticated scoped observations and independently validate their plans before mutation.

#### Scenario: A route target no longer exists or is not eligible
- **WHEN** a transport draft is prepared or executed
- **THEN** the engine rejects the unavailable target without guessing an identifier or sending resources


## Original target: web-access-security

# Web Access Security

## Purpose

Enforce typed, reviewed web operation dispatch and protected administrative boundaries.

## ADDED Requirements

### Requirement: Web operation-specific authorization and safe administrative boundaries
The BFF SHALL validate authenticated operator role, account scope, origin, strict operation-specific schemas, request limits and allowed routes for every privileged operation. The controller bearer, session cookies and provider secrets MUST NOT be returned to the browser.

#### Scenario: Operator requests an unapproved raw engine payload or local-only secret route
- **WHEN** the browser submits the request
- **THEN** the BFF rejects it before forwarding to the engine

### Requirement: Protected administrative workflows
Local browser login and session transfer SHALL remain protected desktop/local workflows. Developer, custom extension and updater functionality SHALL use approved, reviewed management interfaces, not arbitrary command or code execution.

#### Scenario: A web operator needs a secure local session operation
- **WHEN** the operator selects that action
- **THEN** the web provides status and a guided approved local handoff without disclosing session material


## Original target: web-control-center

# Web Control Center

## Purpose

Provide full native web automation workflows with shared account-scoped operation contracts.

## ADDED Requirements

### Requirement: Web native operation parity
The website SHALL expose all supported IkaBot operations through dedicated responsive web-native editors matching desktop domain controls and shared typed contracts. Catalog entries alone or read-only inspectors MUST NOT count as completed mutating operations. User-editable JSON settings, imports and raw engine identifier fields MUST NOT be exposed.

#### Scenario: Operator prepares resource transportation
- **WHEN** an authorized operator selects transport and an authenticated account
- **THEN** actual source and destination city dropdowns, five resource quantity fields, fleet and schedule options are displayed
- **AND** the operator can review the authoritative effects and start through the typed controller contract

#### Scenario: Operator selects multiple accounts
- **WHEN** an eligible workflow is configured for selected or all accounts
- **THEN** each account has an independently scoped plan and named review
- **AND** no city-specific ID from one account is broadcast to another

### Requirement: Consistent responsive automation interaction
Web SHALL provide player-first naming with duplicate disambiguation, searchable categories, relevant contextual controls, clear loading/stale/error states, accessible keyboard navigation, EN/RU localization, and readable light/dark responsive layouts.

#### Scenario: A preview is stale or unavailable
- **WHEN** the plan expires, account changes or authoritative data is unavailable
- **THEN** the website invalidates approval and prevents launch until refreshed and reviewed
