## ADDED Requirements

### Requirement: Compact table-first native desktop
The desktop SHALL place tabular content above persistent explanatory text and SHALL NOT reserve a permanent detail/action panel beside the Accounts table. It MUST provide a compact Add account button and contextual editing commands.

#### Scenario: Account management in a compact window
- **GIVEN** a user opens Accounts at a typical Mac window size
- **WHEN** no account is selected
- **THEN** the table occupies the primary workspace
- **AND** Add account is a single action in the toolbar
- **AND** recovery and destructive actions are not displayed as a permanent large pane.

### Requirement: Familiar multi-account warehouse workflow
The desktop SHALL retain a first-class all-accounts warehouse action, a selected-subset action, per-account inspection, print and CSV/JSON/TXT exports without changing missing resources into zero.

#### Scenario: Combined report with unavailable accounts
- **WHEN** a user requests all configured accounts' warehouses
- **THEN** each account is queried under its existing session
- **AND** failed accounts remain identified separately
- **AND** the original table and export semantics remain available.

### Requirement: Progressive disclosure throughout the native client
The desktop SHALL default to short titles and compact task controls and SHALL retain expert details through explicit disclosure, tooltips and accessible labels without changing safety or backend confirmation requirements.

#### Scenario: User configures an automation
- **WHEN** a user opens Automations
- **THEN** the account and validated task selectors remain available without an expanded discovery gallery
- **AND** the gallery and advanced JSON remain available on request
- **AND** Start still requires backend readiness and explicit review.
