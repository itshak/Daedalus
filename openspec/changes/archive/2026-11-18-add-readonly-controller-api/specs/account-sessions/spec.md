## ADDED Requirements

### Requirement: Local account metadata excludes authentication secrets
Daedalus SHALL support a local multi-account TOML configuration with stable IDs, world, player, label and enabled state, while rejecting passwords, cookies, tokens and unsupported fields.

#### Scenario: User accidentally configures a password
- **WHEN** an `accounts.toml` contains a password field
- **THEN** parsing fails with a message directing the user to protected credentials storage

### Requirement: Duplicate account sessions prevented at configuration time
The controller MUST reject duplicate account IDs and duplicate world/player identities.

#### Scenario: Duplicate world/player record
- **WHEN** two account definitions describe the same world/player identity
- **THEN** configuration validation fails before any game session begins
