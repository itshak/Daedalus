## ADDED Requirements

### Requirement: Owner-approved encrypted notification configuration
Desktop and web SHALL permit explicit worker-global Telegram and Discord default replacement or clearing. Browser mutation SHALL require the owner role. Credentials SHALL be encrypted to a one-use, short-lived, identity-and-provider-bound worker key, never echoed or persisted in the clients or decrypted by the controller gateway. Replacement SHALL make one fixed-message test against the supported HTTPS provider without redirects before private atomic persistence. A legacy selected-account override SHALL block global-default modification until reconciled locally.

#### Scenario: Unauthorized or stale configuration
- **WHEN** a caller lacks owner authorization, submits plaintext, or uses an expired or foreign ticket
- **THEN** no provider configuration is written

#### Scenario: Provider test is rejected or uncertain
- **WHEN** the fixed provider test fails or its outcome is uncertain
- **THEN** the existing configuration is retained and no automatic retry occurs
