## ADDED Requirements

### Requirement: Saved-session identifiers remain outside Git, TOML and API

The saved IkaBot email association SHALL exist only in a protected OS credential provider, using a key scoped to the current configured account/world/player. Probes SHALL never accept credentials from HTTP, expose saved cookies, persist secret material in project files or include engine exception strings in operator errors.

#### Scenario: Identity metadata changes
- **WHEN** an account changes world or player
- **THEN** its previous saved-session keyring association SHALL NOT be reused for the new identity

#### Scenario: No OS credential store is available
- **WHEN** an operator requests binding or probing with no working keyring
- **THEN** the command SHALL fail safely instead of writing plain-text fallback credentials
