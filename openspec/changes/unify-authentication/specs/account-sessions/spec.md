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
