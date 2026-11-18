## ADDED Requirements

### Requirement: Dedicated IPC is exclusive to the verified saved worker
The engine SHALL register an already-authenticated cookie-only restored session with a new protected loopback IPC owner only if no running IkaBot IPC owner can be found. It MUST NOT join an unrelated IPC server, run a new Gameforge login or replace another worker.

#### Scenario: Existing IPC owner detected
- **GIVEN** another existing IPC owner responds on the host
- **WHEN** the local saved worker tries to start its dedicated IPC
- **THEN** startup fails closed without replacing that owner's session or credentials
