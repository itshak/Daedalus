## ADDED Requirements

### Requirement: In-memory game-world cookie override is limited to safe restoration

The Daedalus-maintained IkaBot engine SHALL permit an already authenticated game-world cookie override only in an explicit cookies-only restoration call with exact world/player selectors. It MUST NOT send lobby loginLink or blackbox requests or persist the override into upstream saved-session files.

#### Scenario: Override supplied to normal upstream login
- **WHEN** a caller supplies a world cookie override without cookies-only mode
- **THEN** the engine SHALL refuse it before making any network request

#### Scenario: Verified exact world cookie
- **GIVEN** a syntactically valid existing cookie for a saved world/player
- **WHEN** the exact game-world GET validates it
- **THEN** only the verified in-memory engine session MAY use that cookie without creating a new lobby login
