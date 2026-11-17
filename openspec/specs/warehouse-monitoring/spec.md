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
