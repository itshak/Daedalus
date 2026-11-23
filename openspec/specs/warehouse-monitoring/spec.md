# Warehouse Monitoring

## Purpose
Expose exact city warehouse resources from the engine's authenticated game session.

## Requirements

### Requirement: Distinguish unsecured and total resources
Snapshots SHALL represent total stock, unsecured stock and storage capacity as distinct fields per city and resource.

#### Scenario: Resource snapshot
- **GIVEN** a city has a valid authenticated session
- **WHEN** a warehouse snapshot is requested
- **THEN** values are fetched using the existing engine session and explicitly tagged as totals or unsecured quantities

### Requirement: Preserve existing reporting UX
The desktop SHALL retain city and island grouping, export formats and the unsecured-resource filter after migration.

#### Scenario: Existing filter used remotely
- **WHEN** the user enables the current 220K unsecured-resource threshold
- **THEN** the same filtered results appear from server snapshots without a second browser login

### Requirement: Extract exact unsecured resources from warehouse HTML
Daedalus SHALL parse unsecured values from the known `js_plunderable_*` spans and SHALL prefer exact tooltip values over abbreviations.

#### Scenario: Rounded visible value and exact tooltip
- **GIVEN** the warehouse shows a visible abbreviated value and an exact tooltip value
- **WHEN** the HTML is parsed
- **THEN** the exact tooltip quantity is preserved in the structured snapshot

### Requirement: Missing resources are unknown
Warehouse snapshots MUST represent absent resource values as null, not zero.

#### Scenario: Incomplete warehouse markup
- **GIVEN** an HTML response with only one resource span
- **WHEN** a snapshot is produced
- **THEN** absent resource fields are null and parsed zeroes remain zero

### Requirement: Existing engine warehouse snapshots are typed and complete where available
When an explicitly attached authenticated IkaBot session is available, Daedalus SHALL request each city's warehouse resource spans through its existing game session, parse exact numeric values, and preserve missing values as null.

#### Scenario: Unsecured resource spans include exact tooltip numbers
- **GIVEN** an authenticated warehouse page with exact wood and zero wine values
- **WHEN** the IPC bridge returns its sanitized resource fields
- **THEN** the API reports typed integer values and distinguishes zero from missing resources

### Requirement: Unavailable sessions do not yield synthetic inventory
The warehouse endpoint MUST return an unavailable error rather than invented data when no unique matching authenticated engine session can be found.

#### Scenario: Existing IkaBot session is not available
- **WHEN** the desktop requests warehouse data for an account with no attached in-memory session
- **THEN** the server reports HTTP 503 without attempting another login

### Requirement: Sanitized island identity for attached warehouse snapshots
The engine SHALL expose only validated numeric island coordinates already available from its existing authenticated city inventory, and SHALL not create a separate game session to obtain grouping metadata.

#### Scenario: City coordinates are present
- **GIVEN** an authenticated engine session returns a city with coordinates `[1:2]`
- **WHEN** a warehouse snapshot is read
- **THEN** the response includes the nonsecret island coordinate `1:2`

#### Scenario: Unexpected coordinate data
- **GIVEN** city inventory contains a malformed coordinate field
- **WHEN** the engine creates a warehouse snapshot
- **THEN** it uses null island identity rather than exposing that field

### Requirement: Grouped text reports preserve resource semantics
The desktop SHALL support ordering cities by island and exporting readable grouped TXT while retaining the existing CSV/JSON formats and known-resource 220K filter.

#### Scenario: Unknown resources and grouped export
- **GIVEN** a known island has multiple cities and at least one missing resource quantity
- **WHEN** the user enables island grouping and saves TXT
- **THEN** the cities are grouped by island, missing values display as unknown, and numeric zero remains zero


### Requirement: Exact original IkaBot "Copy by island" layout

The desktop SHALL reproduce the original author's private `itshak/ikabot`
`src/ikabot/report.py::format_text_islands` output (including Russian
resource names, grouping, ordering, separators, whitespace, tabs, commas
and trailing newline) for **Copy by island**, and for Save TXT / print
when **By island** is selected. Machine-readable CSV and JSON are unaffected.

The legacy layout groups all selected account cities by `(island coordinates,
island resource)`, omits account/world headings, orders resource categories
marble → wine → crystal → sulfur → other, sorts coordinates numerically,
and sorts cities within each island by the descending sum of unsecured goods.
Every island section uses `===== coordinates (Ресурс) =====`, blank line,
city `Название (capacity)`, `============`, then five tab-separated
resource lines `Лес`, `Вино`, `Мрам`, `Хруст`, `Сера` with comma-grouped
numbers. The existing 220K filter SHALL apply before grouping.

The engine SHALL provide the sanitized island tradegood from the already
authenticated city inventory so island labels and grouping are correct;
the IPC adapter SHALL whitelist allowed resource identifiers. A missing
numeric field SHALL remain unknown (`—`) rather than be falsely printed as
zero; for complete city snapshots, text must match the original exactly.

#### Scenario: Multi-account island clipboard is byte-for-byte legacy compatible

- **GIVEN** two or more connected accounts with cities on the same coordinates and tradegood
- **WHEN** the user selects **Copy by island**
- **THEN** the copied text SHALL have one island header, no account headings, original tab and blank-line layout, numeric comma separators, and descending city order
- **AND** copied text ends with the same trailing newline as the legacy exporter

#### Scenario: 220K filtering and print/save island mode

- **WHEN** the 220K filter and By island options are enabled
- **THEN** below-threshold cities SHALL be excluded before grouping, and Save TXT and the print preview SHALL use the same legacy island output as the clipboard
- **AND** CSV and JSON exports SHALL preserve their existing machine-readable representation
