## ADDED Requirements

### Requirement: Supervised real-account authentication acceptance
Production cutover SHALL require a supervised real-account test confirming that the authoritative worker validates the actual server-side player identity and that a remote desktop can direct a human to the authorized host-local browser recovery without transferring session secrets over the controller API.

#### Scenario: Owner authorizes supervised recovery
- **GIVEN** an isolated, explicitly authorized account and one authoritative worker host
- **WHEN** the owner performs a browser login or manual challenge and requests recovery
- **THEN** the worker SHALL validate the game-world session and independently attest the configured player before any new user-approved task is dispatched
