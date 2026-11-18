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

### Requirement: Safe production-authentication source reconciliation
Daedalus SHALL review locally modified production IkaBot source against its
pinned public upstream before porting any behavior. Only explicitly audited
nonsecret changes MAY be reimplemented. The process MUST NOT import local
account data, cookie files, credentials, runtime logs or automatic task-launch
behavior into the public engine.

#### Scenario: Review a locally modified production engine
- **GIVEN** a private tracked-source patch against an older public engine
- **WHEN** a maintainer reconciles it
- **THEN** each changed source file receives a documented port, reject or already-upstream disposition and a source-only patch fingerprint
- **AND** no private source archive or runtime credential material is committed

### Requirement: Fail-closed detached engine authentication
The optional native engine login SHALL fail promptly rather than recursively
prompting on exhausted noninteractive input. The external blackbox-token
retrieval helper SHALL use bounded retries only for transport failures and
MUST NOT expose credential-bearing exception strings or API response bodies
through its public errors.

#### Scenario: Token API unavailable in a detached worker
- **GIVEN** no interactive operator terminal and a failed token API request
- **WHEN** the optional native engine login needs manual blackbox assistance
- **THEN** it fails with a nonsecret assistance-required error without prompting for a password, cookie or new Gameforge session

#### Scenario: Token API responds with failure or incompatible parameters
- **WHEN** the API reports HTTP 400/422
- **THEN** the existing single user-agent compatibility request remains available
- **AND** any unauthorized HTTP response or malformed payload fails closed without replaying Gameforge login or displaying the response body
