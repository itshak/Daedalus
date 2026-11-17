## ADDED Requirements

### Requirement: Auditable upstream engine import
Imported public engine source SHALL be traceable to a specific upstream revision and preserve all required license and copyright notices.

#### Scenario: Upstream update review
- **GIVEN** a public engine update is proposed
- **WHEN** it is integrated
- **THEN** maintainers can verify its origin and run regression tests using synthetic identities

### Requirement: Nonconflicting Python namespaces
The `daedalus` controller and upstream `ikabot` engine MUST have nonconflicting imports and installation paths.

#### Scenario: Install the combined application
- **WHEN** the distribution installs the engine and backend
- **THEN** the intended engine module resolves without shadowing the legacy desktop scraper
