## ADDED Requirements

### Requirement: Existing-session IPC requests cannot restore a game login
Daedalus SHALL provide separate, explicit IPC actions for listing in-memory authenticated sessions, reading their cities, and retrieving warehouse resources. Each action MUST refuse missing or ambiguous session identities and MUST NOT call saved-session login restoration.

#### Scenario: World/player has no active in-memory session
- **GIVEN** no authenticated IkaBot session exists for the specified world/player
- **WHEN** the controller invokes an existing-only IPC operation
- **THEN** the operation fails without creating or restoring a session

### Requirement: Warehouse IPC replies expose numeric data only
The IkaBot engine SHALL extract known unsecured-resource and capacity values from authenticated warehouse responses without transmitting raw HTML or action tokens to the controller.

#### Scenario: Warehouse HTML contains a sensitive action field
- **GIVEN** the game page includes resource spans and a hidden actionRequest token
- **WHEN** the controller requests an existing-session warehouse snapshot
- **THEN** the IPC reply includes only resource amounts and city identity; it does not include the hidden token or page markup
