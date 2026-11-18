## ADDED Requirements

### Requirement: Native account metadata editor
The desktop SHALL let the user create, rename, enable, disable and remove account metadata using the protected local/remote API, without storing Gameforge login credentials.

#### Scenario: User confirms a new account record
- **GIVEN** account editing is enabled on the connected backend
- **WHEN** the operator validates and confirms a new world/player account row
- **THEN** the GUI sends only allowed metadata with the current generation and refreshes account views after success

#### Scenario: Backend editing disabled
- **WHEN** the desktop connects to a read-only or task-dispatch backend
- **THEN** metadata editing is disabled and account viewing remains available
