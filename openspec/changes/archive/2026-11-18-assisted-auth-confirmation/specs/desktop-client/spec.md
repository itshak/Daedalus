## ADDED Requirements

### Requirement: Native confirmation of nonsecret manual login assistance

The desktop SHALL let operators inspect a selected account's nonsecret assistance status and SHALL demand separate affirmative consent to acknowledge a completed human step. It MUST NOT claim that such acknowledgment is worker authentication.

#### Scenario: User cancels or selects another account
- **WHEN** the operator cancels consent or changes the selected account
- **THEN** the client SHALL NOT approve the pending or stale ticket

#### Scenario: User approves the manual step
- **WHEN** the operator confirms a valid current ticket
- **THEN** the client SHALL warn that independent worker validation remains required before automation resumes
