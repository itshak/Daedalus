## ADDED Requirements

### Requirement: Safe saved-world-cookie restoration without new lobby login

The Daedalus-vendored IkaBot engine SHALL offer an explicit `cookies_only` restoration mode that validates only previously stored world cookies. That mode MUST NOT query the lobby login token, mint a blackbox, request a loginLink or create a new Gameforge session.

#### Scenario: Saved cookie is expired or redirected
- **GIVEN** invalid cookies for the requested world/player
- **WHEN** the engine attempts cookie-only restoration
- **THEN** it SHALL fail without issuing a lobby login or interactive CAPTCHA request

#### Scenario: Existing valid saved world cookie
- **GIVEN** a valid stored `ikariam` world cookie and exact selected identity
- **WHEN** a world GET returns HTTP 200 on the expected host
- **THEN** the engine MAY report a verified transient saved world session
