## ADDED Requirements

### Requirement: Saved-cookie worker never transports private authentication material
The controller API, metadata file and CLI arguments SHALL NOT contain saved account email, Gameforge tokens, cookies or credentials. The worker SHALL resolve its saved identity locally from a protected OS keyring, SHALL use only the engine's validated cookie-only world request and SHALL close IPC/session/lease on failure and shutdown.

#### Scenario: Worker restore raises a private error
- **WHEN** saved cookie restoration raises an exception containing sensitive data
- **THEN** the external CLI surfaces a sanitized failure without exposing that data
