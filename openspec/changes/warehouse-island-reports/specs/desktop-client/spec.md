## ADDED Requirements

### Requirement: Native island-grouped warehouse export
The native desktop SHALL let the operator choose island ordering and export a human-readable grouped text report without replacing CSV or JSON exports.

#### Scenario: Group warehouses in the desktop
- **GIVEN** authenticated warehouse snapshots contain two cities with the same validated island coordinates
- **WHEN** the operator enables island grouping
- **THEN** the table orders those cities together and a TXT export prints one island heading for both cities

#### Scenario: Backend snapshot lacks island metadata
- **GIVEN** an older read-only IPC worker reports no island coordinates
- **WHEN** the GUI loads its warehouse results
- **THEN** the page remains usable, unknown island values are displayed as unknown, and exports remain available
