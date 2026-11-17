## ADDED Requirements

### Requirement: Reproducible public bootstrap
Daedalus SHALL provide an installable, offline-only Python bootstrap that prints its version and reports missing future components honestly.

#### Scenario: CLI doctor before engine import
- **GIVEN** a clean public checkout with no real game accounts
- **WHEN** the user executes `daedalus doctor`
- **THEN** it reports bootstrap status and does not make any network or Gameforge login request

### Requirement: Source checkout is CI-ready
The initial public source SHALL be testable and buildable directly from its checked-out version.

#### Scenario: Automated package build
- **WHEN** CI builds the Python distribution
- **THEN** it uses only the checked-out Daedalus package and does not download the published `ikabot` package for packaging
