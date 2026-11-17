## ADDED Requirements

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
