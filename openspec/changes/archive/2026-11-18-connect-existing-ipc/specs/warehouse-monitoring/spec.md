## ADDED Requirements

### Requirement: Existing engine warehouse snapshots are typed and complete where available
When an explicitly attached authenticated IkaBot session is available, Daedalus SHALL request each city's warehouse resource spans through its existing game session, parse exact numeric values, and preserve missing values as null.

#### Scenario: Unsecured resource spans include exact tooltip numbers
- **GIVEN** an authenticated warehouse page with exact wood and zero wine values
- **WHEN** the IPC bridge returns its sanitized resource fields
- **THEN** the API reports typed integer values and distinguishes zero from missing resources

### Requirement: Unavailable sessions do not yield synthetic inventory
The warehouse endpoint MUST return an unavailable error rather than invented data when no unique matching authenticated engine session can be found.

#### Scenario: Existing IkaBot session is not available
- **WHEN** the desktop requests warehouse data for an account with no attached in-memory session
- **THEN** the server reports HTTP 503 without attempting another login
