## ADDED Requirements

### Requirement: Local cookie handoff verifies an exact account under the owner lease

The controller SHALL accept a manually obtained game-world cookie only in a local, explicitly confirmed hidden-input flow. The cookie SHALL be validated against exactly one enabled configured account's world/player while holding its host-local identity lease; it SHALL not start a new Gameforge login or automatically resume tasks.

#### Scenario: Browser cookie belongs to another player
- **GIVEN** an existing browser-authenticated world cookie
- **WHEN** exact player/world validation fails
- **THEN** the account remains unverified and the previous saved binding SHALL NOT be overwritten

#### Scenario: Another local worker already owns the account
- **WHEN** a protected local cookie import is requested under an already held account lease
- **THEN** the import SHALL fail before game-world access or keyring writes
