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
