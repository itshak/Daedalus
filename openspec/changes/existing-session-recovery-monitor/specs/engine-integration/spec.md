## ADDED Requirements

### Requirement: Fixed read-only validation of an existing authenticated engine session

The Daedalus-maintained IkaBot IPC overlay SHALL provide a strictly allowlisted action that chooses only a matching in-memory authenticated game session and performs a read-only probe to its own canonical HTTPS world URL. It SHALL return only a boolean and matching world/player identity. It MUST NOT call `Session.from_saved`, start another login, deliver raw HTML, send action tokens across IPC or accept arbitrary URLs.

#### Scenario: Expired or redirected response
- **GIVEN** an already attached world session
- **WHEN** its world response is expired, redirected to lobby or lacks the game marker
- **THEN** the engine SHALL return `session_valid=false` with no cookie or HTML

#### Scenario: Wrong account identity
- **WHEN** a request names a different player or world
- **THEN** no matching session SHALL be selected and no game request SHALL occur
