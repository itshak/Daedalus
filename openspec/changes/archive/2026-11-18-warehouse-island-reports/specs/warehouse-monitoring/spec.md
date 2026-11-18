## ADDED Requirements

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
