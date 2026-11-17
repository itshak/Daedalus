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
