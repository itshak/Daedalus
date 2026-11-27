## ADDED Requirements

### Requirement: Versioned scoped logical task read model
The controller SHALL expose bounded, versioned read-only logical-task summaries, detail, statistics and paginated events with account identity validation and evidence completeness. Existing task and receipt interfaces MUST remain compatible.

#### Scenario: Operator opens a task detail
- **GIVEN** an authorized account scope
- **WHEN** the client requests a logical task and its activities
- **THEN** the controller returns only that account's typed observations, run references and safe statistics with pagination and freshness

#### Scenario: Invalid or cross-account query
- **WHEN** a cursor, filter, task identity or account binding is invalid
- **THEN** the request fails closed without exposing other task data
