# Web Control Center

## Purpose

Provide dedicated native web controls for reviewed account-scoped operations.

## ADDED Requirements

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
