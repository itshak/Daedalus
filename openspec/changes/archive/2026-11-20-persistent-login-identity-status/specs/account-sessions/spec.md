## ADDED Requirements

### Requirement: Durable Mac-sealed Gameforge login backups
After explicit account login and independent server identity verification,
Daedalus SHALL permit the Mac to store an account-specific AES-GCM sealed
login in the server's persistent protected credential store. Only the
originating Mac Keychain SHALL hold the decryption key. The absence of a
backup MUST NOT invalidate an independently verified game session.

#### Scenario: Password absent in local Keychain, vault key retained
- **GIVEN** a server-persisted sealed login for this account/world and a matching
Mac Keychain vault key
- **WHEN** the user starts headless Selenium login
- **THEN** the Mac decrypts in memory without sending plaintext credentials
to the Daedalus API and uses a visible browser only for detected CAPTCHA
