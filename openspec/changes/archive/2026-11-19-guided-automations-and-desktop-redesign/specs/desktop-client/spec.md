## ADDED Requirements

### Requirement: Guided account-first desktop automations

The native Mac desktop SHALL provide account-first navigation, quick access to warehouse and automation workflows, categorized searchable operation selection, and native typed parameter controls. Advanced JSON SHALL be optional. Every task start SHALL remain subject to a separate explicit user confirmation and independently validated backend readiness.

#### Scenario: User starts a supported automation without writing JSON

- **WHEN** a user chooses an authenticated account, selects a background automation, adjusts native controls, sees passing preflight, and confirms launch
- **THEN** the desktop sends a typed task configuration and one unique request ID through the authenticated API without requiring a handwritten JSON document

#### Scenario: User selects an unavailable or unconfirmed task

- **WHEN** task readiness fails or a prior task request remains unconfirmed
- **THEN** the Start control stays disabled and the desktop displays clear prerequisite or manual-reconciliation guidance from the authoritative backend's nonsecret read-only readiness result

### Requirement: Guided private SSH connection

The desktop SHALL offer a button to establish a local SSH tunnel using the user's existing trusted SSH host and identity, without passing credentials in SSH arguments. It SHALL retain advanced HTTPS/loopback URL connections and SHALL close owned tunnels when the application exits or switches backend.

#### Scenario: User has a trusted SSH host and saved API token

- **WHEN** the user chooses the secure SSH connection, their trusted SSH host is reachable, and the API accepts the keychain token
- **THEN** the app performs a private read-only handshake over local port forwarding without a manual Terminal command or a public backend binding

#### Scenario: SSH authentication fails

- **WHEN** the host key or SSH identity cannot be verified
- **THEN** the app fails with a sanitized connection error and does not disable host-key checking or expose the backend to the public network

### Requirement: Default secure HTTPS and OS-Keychain reconnection

The native client SHALL prefer direct TLS-verified HTTPS as its primary connection workflow, without requiring an SSH tunnel on the user's Mac. After an authenticated connection, the default selected preference SHALL save the bearer only in the OS Keychain, associate it with the exact validated HTTPS origin, and automatically reconnect on subsequent launches. Explicit opt-out SHALL allow an ephemeral session. The client MUST NOT silently copy a token to a different hostname, log credentials, or save bearer tokens in plaintext.

#### Scenario: First authenticated HTTPS connection

- **WHEN** the user supplies a TLS-valid Daedalus HTTPS hostname and correct bearer, leaving secure saving selected
- **THEN** the app completes a read-only handshake and saves the token in the OS Keychain and the URL in owner-only settings, without any Mac SSH tunnel

#### Scenario: User relaunches the desktop

- **WHEN** an exact previously approved HTTPS origin and its token exist in the OS Keychain
- **THEN** the app reconnects on startup without reentering either value and without starting a game task

#### Scenario: Different endpoint or missing keychain credential

- **WHEN** the user selects an HTTPS origin other than the one whose bearer was saved, or the Keychain is unavailable
- **THEN** the client does not reuse the old secret or weaken TLS verification, and requests explicit credentials instead
