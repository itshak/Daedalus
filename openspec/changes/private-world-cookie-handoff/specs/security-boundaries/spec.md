## ADDED Requirements

### Requirement: Manually imported session cookies never traverse public APIs or project files

The CLI SHALL prompt for a world cookie only in an interactive echo-disabled local terminal with separate explicit network consent, and SHALL keep it out of command arguments, environment variables, logs, TOML and HTTP API. Only a verified cookie MAY be stored through a protected OS credential provider, using an account/world/player-specific key.

#### Scenario: No terminal or OS credential provider
- **WHEN** a user attempts to bind a world cookie without a TTY or protected keyring
- **THEN** Daedalus SHALL refuse the handoff instead of printing or writing the secret

#### Scenario: User changes configured world/player
- **WHEN** the account identity changes
- **THEN** the previously imported world cookie SHALL not be reused or disclosed to the changed identity

#### Scenario: Failed cookie re-import
- **WHEN** a newly supplied cookie cannot validate the world/player
- **THEN** the previous verified cookie SHALL remain unchanged in protected storage
