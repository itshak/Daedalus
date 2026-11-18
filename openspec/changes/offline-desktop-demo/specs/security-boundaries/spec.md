## ADDED Requirements

### Requirement: Demo mode cannot attach real accounts or execute automation

An explicit synthetic demo SHALL reject real account paths, IPC descriptors, injected snapshot providers, existing authenticated sessions, task execution, account editing and game login. It SHALL retain bearer authorization for all account/report data and loopback-only host binding.

#### Scenario: Demo is combined with production flags
- **WHEN** an operator requests demo mode with real account, IPC, task control or editing options
- **THEN** startup SHALL fail before opening any game client or account file

#### Scenario: Client attempts to modify game state in demo
- **WHEN** a client attempts to start a game task, attach an existing IkaBot session or edit an account
- **THEN** the controller SHALL reject it without network or game side effects
