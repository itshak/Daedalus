## ADDED Requirements

### Requirement: Explicit lease-bound, cookie-only saved-session probing

The controller SHALL permit an operator to probe previously stored world cookies only after explicit confirmation, only while holding the account/world/player host-local lease, and only for one exact configured enabled identity. The probe SHALL release the lease and close any transient session after returning.

#### Scenario: Another Daedalus process owns the account
- **GIVEN** a matching account lease is already held
- **WHEN** a cookie-only probe is requested
- **THEN** the probe SHALL fail without calling the game provider

#### Scenario: Stored cookies do not validate the configured player
- **WHEN** the cookie-only engine returns an expired or another player's session
- **THEN** the result SHALL report manual recovery required and MUST NOT mark the configured account authenticated
