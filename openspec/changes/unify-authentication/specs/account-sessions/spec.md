## ADDED Requirements

### Requirement: Coordinated interactive authentication
A desktop login assistant MUST coordinate with the single account session owner and SHALL NOT initiate an unrequested second game session.

#### Scenario: Remote worker needs human assistance
- **GIVEN** a game worker cannot restore its session
- **WHEN** a user completes login or CAPTCHA with the desktop assistant
- **THEN** the worker validates a protected handoff before resuming automation

### Requirement: Session secrets remain private
The application MUST store live session cookies, tokens and passwords outside the public source tree and CI.

#### Scenario: Successful login
- **WHEN** authenticated session data is saved
- **THEN** it is stored with restricted access and omitted from logs and Git

### Requirement: Host-local human browser assistance
A user-approved local browser recovery SHALL acquire the exact account/world/player lease before opening the official Gameforge lobby and SHALL retain the lease through manual challenge completion, world-cookie verification and protected persistence. The application SHALL NOT collect a password, solve CAPTCHA, expose cookie material over the API, or report authentication success before the engine verifies the configured world and player.

#### Scenario: Human completes a browser challenge
- **GIVEN** an enabled account with an existing protected saved-email binding
- **WHEN** the operator explicitly starts local browser assistance and supplies a world cookie in a hidden terminal prompt
- **THEN** the engine SHALL verify the configured account under the same lease before the cookie is stored in the OS keyring

#### Scenario: Worker already owns the account
- **GIVEN** an existing host-local owner holding the account lease
- **WHEN** the operator requests a second browser-assisted recovery
- **THEN** the application SHALL reject it before opening a browser or prompting for a cookie
### Requirement: Explicit new-task dispatch after verified recovery
The controller SHALL reject a post-recovery task request unless the same trusted worker has validated its game session, the operator explicitly approves a new task, and a fresh idempotency key and secret-free configuration are supplied. A successful approval SHALL be single-use, and an ambiguous dispatch SHALL NOT be automatically replayed.

#### Scenario: Operator attempts to reuse recovery approval
- **GIVEN** a trusted worker has validated a recovered session and dispatched one approved task
- **WHEN** the client submits a different task request with the same recovery ticket
- **THEN** the controller SHALL reject it without another game operation

#### Scenario: Recovery session expires before dispatch
- **GIVEN** a previously verified recovery ticket
- **WHEN** the read-only game-world validation no longer succeeds
- **THEN** the controller SHALL reject task dispatch without consuming an unverified game session
