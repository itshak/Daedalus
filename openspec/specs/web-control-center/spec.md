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

### Requirement: Persistent workspace navigation and warehouse data table
The website SHALL restore the last valid workspace page after reload. The warehouse dashboard SHALL use a sortable data table with city, account, island, resource and capacity columns, search, island/world and resource filters, minimum unsecured stock and the existing 220K filter. Visible totals and exports SHALL follow the filtered report; unknown values MUST NOT be rendered as zero.

#### Scenario: Operator changes warehouse filters or sorting
- **WHEN** the operator selects an island, resource threshold, search term or sort column
- **THEN** the displayed rows and report totals update locally without new game requests and the export follows the visible sorted rows

#### Scenario: Browser reloads on a selected page
- **WHEN** the operator reloads after visiting a valid workspace page
- **THEN** that page is restored; no privileged game payload is persisted for navigation

### Requirement: Bounded private warehouse snapshot reuse
The web dashboard SHALL cache successful account-bound warehouse responses in memory for at most 120 seconds, scoped by operator and account identity, deduplicate concurrent reads and reuse fresh entries when switching scope or returning to the dashboard. Manual refresh SHALL invalidate cached reports and fetch current observations. Expired, failed, offline or invalid observations MUST NOT be represented as current data. Privileged snapshots MUST NOT be stored in persistent browser storage or shared caches.

#### Scenario: Return to warehouse dashboard within freshness window
- **WHEN** the operator navigates away and returns within 120 seconds while online with the same authorized scope
- **THEN** the fresh successful cached data is reused and its fetch time is visible

#### Scenario: Refresh, expiry or network failure
- **WHEN** a snapshot expires, the operator explicitly refreshes or network access becomes unavailable
- **THEN** the dashboard fetches fresh data when online or shows unavailable status; it never replays stale cached data as current
