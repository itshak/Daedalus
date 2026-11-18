## ADDED Requirements

### Requirement: No plaintext persistent controller tokens
Daedalus SHALL NOT write API bearer tokens to ordinary JSON, TOML, log, or runtime preference files.

#### Scenario: Persistent credential setup
- **GIVEN** the user opts in to storing a backend connection
- **WHEN** the secure credential provider cannot write a secret
- **THEN** no insecure fallback file containing the bearer credential is created
