## ADDED Requirements

### Requirement: Bearer-authenticated client-sealed login vault
The controller SHALL accept and return only account-scoped AES-GCM opaque
login envelopes, never a plaintext Gameforge password. Persisted envelopes
MUST use the protected credential store and require a verified account email
binding before writes. Unavailable secrets MUST fail closed.

#### Scenario: Client retrieves a saved login
- **GIVEN** an authorized Mac has a retained Keychain vault key
- **WHEN** it retrieves the account's envelope
- **THEN** the server returns ciphertext only, decryptable only under the
  exact backend origin/account/world identity on the originating Mac

#### Scenario: Account list has protected email binding
- **GIVEN** an independently verified email binding in the protected store
- **WHEN** a bearer-authorized client requests accounts
- **THEN** that email may be returned for account identity display without
  exposing a password, raw cookie or secret key
