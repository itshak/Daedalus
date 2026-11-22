## MODIFIED Requirements

### Requirement: Durable Mac-sealed Gameforge login backups

After explicit account login and independent server identity verification, the Mac MAY store account-scoped AES-GCM sealed credentials for recovery, retaining the decryption key solely in the origin Mac Keychain. Recovery SHALL first attempt headless authentication using decrypted credentials in Mac memory, then permit a visible human-driven browser retry after CAPTCHA or other headless login failure. Plaintext Gameforge credentials MUST NOT enter the controller API or logs.

#### Scenario: Headless form fails with saved credentials
- **WHEN** a saved account's headless Gameforge form fails to authenticate
- **THEN** the operator receives a visible Chrome retry while the encrypted server handoff and owner verification requirements remain in place
