## ADDED Requirements

### Requirement: Headless Linux credentials are encrypted and fail closed without their host key

A Linux service MAY opt in to a protected host-bound encrypted credential store as an alternative to GUI-session Secret Service. Its encryption key SHALL be stored as a root-owned systemd encrypted credential, passed transiently via a service-specific credential directory, and never written in ordinary application configs or argument strings. World cookies and saved identity bindings SHALL be independently encrypted using AES-GCM with account/world/player-specific authenticated context and owner-only directory/file permissions. A missing key, tampered ciphertext, unsafe permissions or altered account identity SHALL fail closed without plaintext or volatile-keyring fallback.

#### Scenario: Headless service restarts without a GUI

- **WHEN** the intended service is supplied its valid host-encrypted systemd credential and the correct private ciphertext files
- **THEN** the exact account's protected saved session can be independently revalidated without starting VNC, SSH forwarding, a lobby login, or an unapproved task

#### Scenario: Systemd encryption key is missing or ciphertext altered

- **WHEN** the service's configured encrypted credential cannot be loaded or a saved account record fails authentication
- **THEN** no plaintext fallback is written, no other account's secret is accepted, and the worker fails safely without a game task
