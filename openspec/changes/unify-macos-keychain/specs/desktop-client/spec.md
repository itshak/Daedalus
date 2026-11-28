## ADDED Requirements
### Requirement: Unified macOS credential authorization
The native macOS client SHALL use one application-owned Keychain master key for persistent backend tokens, saved Gameforge credentials and encrypted server-backup keys. The remaining records SHALL be authenticated ciphertext bound to the exact service and account scope. The client SHALL preserve supervised helper cancellation and never transfer the master through command arguments, environment, files, logs or backend APIs.

#### Scenario: Bulk sign-in after authorization
- **GIVEN** the user has authorized the application master key and accounts are migrated
- **WHEN** the user signs into multiple accounts or retries visible Chrome
- **THEN** the application reuses the unlocked key in private memory and anonymous helper pipes without per-account Keychain queries.

#### Scenario: Legacy migration or denied permission
- **GIVEN** legacy independently protected records or a denied master key request
- **WHEN** the client resolves credentials
- **THEN** it respects existing macOS ACLs, migrates successfully read legacy records without destroying them, and does not repeatedly request a denied master key during the process lifetime. It never falls back to plaintext persistence.
