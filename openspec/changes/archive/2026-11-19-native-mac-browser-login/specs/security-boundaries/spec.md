## ADDED Requirements

### Requirement: Remote Mac session material is encrypted for a one-use identity-bound handoff

A backend explicitly opted in to native browser recovery MAY receive encrypted world-cookie material only through a time-limited, single-use public-key challenge scoped to the exact fixed configured account/world/player identity. It MUST require the existing API bearer, trusted HTTPS for remote access, authenticated encryption, protected OS-keyring storage after independent world verification, and sanitized failures. The endpoint MUST reject raw plaintext game cookies, passwords, unrelated profiles, expired challenges and replays.

#### Scenario: Browser session is submitted
- **WHEN** the native Mac user explicitly authorizes one world-cookie handoff
- **THEN** the API receives ciphertext, a one-time client public key and nonce only; no plaintext world cookie or Gameforge identity appears in request fields, logs, responses or project files

#### Scenario: Envelope is tampered with or replayed
- **WHEN** an attacker changes ciphertext, identity binding, or reuses a consumed ticket
- **THEN** decryption/validation fails closed and no worker or verified cookie is replaced
