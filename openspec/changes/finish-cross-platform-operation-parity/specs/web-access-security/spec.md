## ADDED Requirements

### Requirement: Owner-approved encrypted notification configuration
Desktop and web SHALL permit explicit worker-global Telegram and Discord default replacement or clearing. Browser mutation SHALL require the owner role. Credentials SHALL be encrypted to a one-use, short-lived, identity-and-provider-bound worker key, never echoed or persisted in the clients or decrypted by the controller gateway. Replacement SHALL make one fixed-message test against the supported HTTPS provider without redirects before private atomic persistence. A legacy selected-account override SHALL block global-default modification until reconciled locally.

#### Scenario: Unauthorized or stale configuration
- **WHEN** a caller lacks owner authorization, submits plaintext, or uses an expired or foreign ticket
- **THEN** no provider configuration is written

#### Scenario: Provider test is rejected or uncertain
- **WHEN** the fixed provider test fails or its outcome is uncertain
- **THEN** the existing configuration is retained and no automatic retry occurs


### Requirement: Protected release discovery and diagnostic projection
Desktop and web SHALL expose current controller version, build revision when available, and published project Mac previews with exact release and checksum references. The catalog SHALL be explicitly requested, bounded, read-only and restricted to the fixed public project repository. Synthetic demo MUST remain offline. Clients MUST NOT interpret a preview or checksum link as verified notarization or release acceptance, and MUST NOT expose raw developer cookies, arbitrary commands or unauthenticated game proxy services.

#### Scenario: Untrusted release metadata
- **WHEN** a preview is missing the expected project assets or has a foreign download destination
- **THEN** no download link for that preview is offered

#### Scenario: An operator checks for an update
- **WHEN** the operator requests release discovery
- **THEN** the system displays validated metadata without modifying the controller, desktop or game session


### Requirement: Host-approved extension registration
Desktop and web SHALL expose a bounded, redacted catalog of locally installed, host-approved extensions. The worker SHALL verify the manifest identity and source digest before registering an extension and compare the current registration against the reviewed state. Web mutation SHALL require owner authorization and explicit worker-global consent. Registration MUST NOT download, upload, execute or delete code or disclose local filesystem paths. Legacy per-user overrides SHALL block shared-default mutation.

#### Scenario: An installed extension changes
- **WHEN** its source digest or reviewed registration state differs from the approved or observed value
- **THEN** registration fails without changing the shared configuration

#### Scenario: A previously registered extension is removed from the menu
- **WHEN** the owner confirms unregistering an approved entry
- **THEN** the shared registration is removed without deleting or executing its source file
