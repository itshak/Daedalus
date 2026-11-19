# Desktop Client — native automation workflows

## Requirement: Grouped task discovery
The desktop client SHALL present engine operations in a human-readable domain navigation, separate configuration from Running and History, and preserve the exact canonical engine operation identity. Search and category selection SHALL be selection-only. An unavailable or interactive-only operation SHALL display why it is not dispatchable.

### Scenario: Choose a group
- **GIVEN** the authenticated backend returns an operation catalog
- **WHEN** the user selects City & research
- **THEN** the app shows only relevant operation cards and no game task starts

## Requirement: Live domain controls, not guessed JSON values
Every operation SHALL have a reviewed domain-specific interface for all user-facing inputs. City, building, unit, island, resource, market and route choices SHALL be sourced from authoritative account-scoped backend records where required. Unknown/deferred capabilities SHALL be clearly unavailable; expert configuration import MAY exist only as an explicit advanced fallback.

### Scenario: Choose a building upgrade
- **GIVEN** the selected account has verified city and building snapshots
- **WHEN** the user chooses a city and target upgrade level from the building table
- **THEN** the app displays the actual building position, current level and engine-previewed costs and queue, never guessed values

### Scenario: No building information
- **WHEN** building inventory is unsupported or stale
- **THEN** the table shows a non-actionable needs-data state and does not permit launching a fabricated construction plan

## Requirement: Per-account review and nonbroadcast domain plans
The client SHALL maintain drafts per backend origin, account, task and validated snapshot revision. It SHALL require explicit review of nonsecret effects before dispatch and SHALL prevent reuse of city-specific plans or game entity identifiers across accounts.

### Scenario: Several accounts selected
- **WHEN** a user chooses a construction or transport operation for several accounts
- **THEN** separate per-account read/preflight/plan approval is required and no shared city ID is sent to an unrelated account

## Requirement: Accessible, compact operation workspace
The client SHALL expose grouped navigation, appropriate native controls, keyboard paths, labeled inputs, dense but readable tables and scoped progress/error states. On short macOS windows it SHALL scroll vertically without nested form clipping.

### Scenario: Narrow window
- **WHEN** the user sizes a Mac window to 900x650
- **THEN** category navigation, city selector, task controls and review action remain reachable without overlap or clipped inputs
