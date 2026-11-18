# Project Foundation

## Purpose
Keep the public source tree buildable, reviewable and safe from real account secrets from its first commit.

## Requirements

### Requirement: Installable uniquely named package
The project SHALL build a Python distribution provisionally named `daedalus` with an importable `daedalus` namespace and a `daedalus` CLI, without installing a second `ikabot` package.

#### Scenario: Offline bootstrap installation
- **GIVEN** a clean Python 3.11+ environment
- **WHEN** a developer installs the checkout and runs `daedalus doctor`
- **THEN** a valid structured bootstrap status is printed without any network or game login

### Requirement: Public source isolation
The source repository MUST exclude real credentials, browser data, tokens, cookies, session cache, personal account files, and production logs.

#### Scenario: Public import review
- **GIVEN** a developer is porting code from a local legacy checkout
- **WHEN** a patch is submitted
- **THEN** provenance is recorded and synthetic fixtures replace private runtime data

### Requirement: Offline continuous integration
Pull requests SHALL run Python tests, linting, OpenSpec validation, and public-source security checks without game-server access or production credentials.

#### Scenario: Untrusted pull request
- **GIVEN** an external contributor opens a pull request
- **WHEN** CI executes
- **THEN** CI uses read-only permissions and no private credentials or game sessions

### Requirement: Explicit upstream attribution
Imported public IkaBot code MUST retain applicable MIT license notices and be tracked to a source revision.

#### Scenario: Engine import
- **GIVEN** a new engine update
- **WHEN** it is added to Daedalus
- **THEN** its upstream commit and license attribution are recorded and tested

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

### Requirement: Setup diagnostics reflect implemented scope without reading private accounts

The `doctor` command SHALL report known offline preview capabilities and optional dependency availability, SHALL mark uninspected live account and game state as unknown, and SHALL NOT claim production readiness. It MUST NOT read game cookies, account configuration or keyring secrets or make network requests by default.

#### Scenario: User checks base installation
- **WHEN** the user runs `daedalus doctor`
- **THEN** it SHALL produce machine-readable diagnostics for engine source/CLI, server, desktop, existing-session capabilities, and lack of new worker bootstrap/automatic browser login

### Requirement: Synthetic end-to-end API smoke is explicit and isolated

The `doctor --smoke` option SHALL exercise actual authenticated backend API routes in-process using only synthetic demo accounts, warehouses and capabilities. It MUST NOT establish an external socket or contact Gameforge. Missing optional test dependencies or failed isolation SHALL produce a nonzero result with a sanitized error.

#### Scenario: Complete offline smoke
- **WHEN** a user invokes `daedalus doctor --smoke` with test dependencies installed
- **THEN** authorization, synthetic account metadata, capabilities and fake warehouse reporting SHALL pass, and the output SHALL remain labeled synthetic with zero game requests
