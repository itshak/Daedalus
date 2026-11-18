## ADDED Requirements

### Requirement: Existing-session monitoring keeps account ownership and requires verified recovery

Only an explicitly opted-in controller MAY monitor an already-authenticated IkaBot engine session after a human confirms the intended account and its exact in-memory game identity is verified. It SHALL retain its host-local account lease across expiration and human assistance. Failed validation SHALL block subsequent task dispatch; successful validation after human acknowledgment SHALL require the same trusted monitor to check the real game session.

#### Scenario: Existing session expires during monitoring
- **GIVEN** an exact existing IkaBot session with a Daedalus monitoring lease
- **WHEN** a read-only world validation finds session expiration or rotation
- **THEN** the owner SHALL transition to assistance and a new game task SHALL NOT be dispatched

#### Scenario: Manual completion cannot restore a failed session
- **GIVEN** a pending one-use assistance ticket
- **WHEN** the user acknowledges the manual step but the worker's validation fails
- **THEN** the owner SHALL remain unverified and require a new assistance ticket without automatic task replay

#### Scenario: Monitoring remains disabled
- **WHEN** the operator starts the default controller without monitoring opt-in
- **THEN** the controller SHALL NOT open game-world validation requests or initiate a new login
