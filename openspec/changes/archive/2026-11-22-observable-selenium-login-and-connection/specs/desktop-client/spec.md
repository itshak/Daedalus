## MODIFIED Requirements

### Requirement: Observable headless Gameforge authentication with visible failure recovery

The Mac desktop SHALL first restore an exact-world session or attempt Gameforge sign-in in isolated headless Selenium Chrome. On a detected CAPTCHA or an unsuccessful headless login, it SHALL open one temporary visible Chrome to let the human finish or correct authentication. Headless attempts SHALL use a bounded deadline reserving time for visible recovery, and only an exact-world secure cookie that passes independent server world/player attestation SHALL be treated as authenticated. The browser MUST NOT solve CAPTCHA or dispatch game tasks.

#### Scenario: Headless sign-in fails without CAPTCHA
- **GIVEN** an account with saved credentials and a changed Gameforge form or rejected credentials
- **WHEN** the first headless attempt fails
- **THEN** the desktop opens visible Chrome for human correction and displays sanitized recovery progress

### Requirement: Confirmed backend connection and masked token state

On a successful authenticated backend handshake, the desktop SHALL present a Fluent success notification and a persistent connected state. It SHALL replace the sensitive API token text with a masked configured-value placeholder and SHALL retain the bearer only in the authenticated client and, when opted in, the OS Keychain for the exact HTTPS origin.

#### Scenario: Successful connection
- **WHEN** a valid backend and bearer complete the HTTPS handshake
- **THEN** the user sees a success notification and masked token-configured indicator
- **AND** raw bearer material is absent from the input widget and logs
