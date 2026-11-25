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
