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
