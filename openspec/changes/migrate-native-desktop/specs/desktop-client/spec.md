## ADDED Requirements

### Requirement: Preserve existing Fluent report UX
Daedalus SHALL retain the current application's native resource table, filtering and export interactions while exposing additional engine modules.

#### Scenario: Migrated remote report
- **GIVEN** resource results returned by a remote Daedalus backend
- **WHEN** a user opens the existing report workflow
- **THEN** the familiar filtering, display and exports work without a separate Selenium game login
