## ADDED Requirements

### Requirement: Preserve existing Fluent report UX
Daedalus SHALL retain the current application's native resource table, filtering and export interactions while exposing additional engine modules.

#### Scenario: Migrated remote report
- **GIVEN** resource results returned by a remote Daedalus backend
- **WHEN** a user opens the existing report workflow
- **THEN** the familiar filtering, display and exports work without a separate Selenium game login

### Requirement: Safe legacy account selection and multi-account reports
The native desktop SHALL let operators select accounts for **read-only**
warehouse reporting without modifying account enablement or starting tasks,
and SHALL retain backend-specific selections without storing credentials.

#### Scenario: Select multiple accounts for warehouse reports
- **GIVEN** two configured accounts and a connected read-only backend
- **WHEN** the operator selects them in Accounts and requests selected warehouses
- **THEN** the UI retrieves snapshots off the GUI thread using the existing API, combines identifiable account rows for export and never starts tasks

#### Scenario: One selected account cannot provide a snapshot
- **GIVEN** a multi-account report with one backend snapshot error
- **WHEN** the report finishes
- **THEN** successful rows remain usable, the unavailable account is labeled, and no missing values are silently converted to zero

#### Scenario: Operator switches backend connection
- **WHEN** a new backend handshake succeeds
- **THEN** previously loaded warehouse data is cleared and only that backend's private report selection is applied

### Requirement: Private local appearance and report preferences
The desktop SHALL support System/Light/Dark themes and warehouse filter and
island-grouping defaults without storing or importing game authentication data.

#### Scenario: Save local GUI preferences
- **WHEN** the operator changes appearance or reporting defaults
- **THEN** the settings are applied immediately and atomically persisted to an owner-private, versioned file with no game passwords, bearer tokens or cookies

#### Scenario: Stored GUI settings are unsafe or malformed
- **GIVEN** unexpected fields, unsafe permissions, a symlink or invalid settings
- **WHEN** the desktop starts
- **THEN** it uses safe local defaults and does not import untrusted settings or game credentials

### Requirement: Preserve island-grouped clipboard reporting
The native warehouse view SHALL support copying an island-grouped textual report
in addition to exporting TXT, CSV and JSON.

#### Scenario: Copy a grouped report
- **GIVEN** typed resource snapshots with validated island coordinates
- **WHEN** the operator uses Copy by island
- **THEN** the clipboard holds grouped human-readable text without converting unknown resource amounts to zero
