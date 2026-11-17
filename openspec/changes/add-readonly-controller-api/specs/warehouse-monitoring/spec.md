## ADDED Requirements

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
