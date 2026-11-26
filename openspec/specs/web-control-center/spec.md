# web-control-center Specification

## Purpose
Provide dedicated native web controls for reviewed account-scoped operations.

## Requirements

### Requirement: Reviewed native web operation editors
The website SHALL expose reviewed supported operations through dedicated web-native editors. Catalog-only and read-only views MUST NOT count as completed mutating operations. User-editable JSON task settings and raw plan imports MUST NOT be exposed.

#### Scenario: Operator prepares a supported shipment
- **WHEN** authenticated cities are loaded
- **THEN** actual source and destination city names, resource quantities and fleet options are available
- **AND** the operator reviews the authoritative shipment quote before launch

#### Scenario: Operator queues independently reviewed accounts
- **WHEN** a supported ticket-based workflow is queued for multiple accounts
- **THEN** each account has its own named review and no account-specific city identifiers are broadcast to another

### Requirement: Scoped web receipt history
The website SHALL provide account selection, status filtering, paging and current-page CSV export of bounded controller receipt history.

#### Scenario: A receipt is shown
- **WHEN** a managed task dispatch receipt is displayed
- **THEN** it is not represented as proof of game-operation completion

### Requirement: Military read error clarity
The web control center SHALL use the same authenticated controller military and ship-movements observations as the desktop. It SHALL distinguish a successful empty result from an unavailable account read and map HTTP 503 on those endpoints to a military-specific safe message with connection and refresh guidance, without relaying raw backend errors or initiating game orders.

#### Scenario: Military controller observation is unavailable
- **WHEN** the authenticated military or movements endpoint returns HTTP 503
- **THEN** the web client displays the appropriate military-specific unavailable message for that account instead of a generic backend failure or zero counts

### Requirement: Actual web military unit presentation
The Military page SHALL render each verified city, individual ground unit and ship name, and numeric count in dedicated troop and fleet tables, with totals and observation freshness. It SHALL NOT substitute nested DTO placeholders for unit data. Verified empty city lists SHALL be distinguishable from invalid or unavailable observations.

#### Scenario: Nested city military inventory arrives
- **WHEN** the controller returns a city with nested troops and fleet arrays
- **THEN** the web interface displays every unit name and count, separated by troop and fleet type, without generic controller-details placeholders
- **AND** an explicitly empty array is shown as an observed zero, while malformed or cross-account responses are unavailable
