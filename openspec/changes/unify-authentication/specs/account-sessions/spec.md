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

### Requirement: Ephemeral browser recovery without credentials
An explicitly approved local recovery SHALL launch a nonpersistent visible browser, leave authentication and challenges to the human operator, and extract only a secure cookie scoped to the exact configured game-world host after operator confirmation. The account owner lease SHALL remain held through browser closure and successful worker-side identity validation. A remote operator MAY use a protected graphical session on the authoritative host, but SHALL NOT send session secrets over the controller API.

#### Scenario: Human completes a challenge in an ephemeral browser
- **GIVEN** an enabled account, protected keyring binding and no conflicting owner
- **WHEN** the operator completes the visible browser login and explicitly confirms the world page is ready
- **THEN** Daedalus SHALL accept only the exact world-host cookie and SHALL store it only after engine verification

#### Scenario: World cookie does not match the expected account
- **GIVEN** a browser with no secure cookie for the configured world or a worker reporting a different player
- **WHEN** the operator attempts recovery
- **THEN** the application SHALL reject the handoff, close the ephemeral browser and retain the previous keyring binding

### Requirement: Idle-only verified dedicated-worker recovery
A dedicated cookie-only worker SHALL allow a user-approved replacement of its session only while its account lease remains held, the new protected cookie restores the exact configured world/player, and the controller confirms no active or uncertain task. It SHALL stop the old IPC endpoint before publishing the replacement, and SHALL NOT replay a task. Failure after IPC shutdown SHALL retain the lease in a failed state for manual reconciliation.

#### Scenario: Recovery of an idle dedicated worker
- **GIVEN** an owned dedicated worker with no running or uncertain tasks and a newly verified world-cookie binding
- **WHEN** the operator approves a session replacement
- **THEN** the worker SHALL validate the replacement, stop its old IPC endpoint, start the new endpoint, and retain the same account lease

#### Scenario: Uncertain task prevents session replacement
- **GIVEN** an unresolved task dispatch or active engine task
- **WHEN** recovery is requested
- **THEN** the worker SHALL refuse session replacement without stopping its existing IPC endpoint
