## ADDED Requirements

### Requirement: Operator-confirmed monitoring and protected assistance notifications

The controller SHALL expose session-monitoring attachment only when explicitly enabled with existing-session task control, SHALL require bearer authorization and exact explicit `confirmed=true` before attaching a lease, and SHALL return only bounded nonsecret assistance ticket summaries. The API MUST NOT accept or distribute Gameforge credentials or session cookies.

#### Scenario: Unauthenticated monitoring command
- **WHEN** a remote client requests monitoring without bearer authorization or consent
- **THEN** the backend SHALL reject it without IPC or game network interaction

#### Scenario: Read pending assistance
- **GIVEN** one or more currently waiting lease-bound assistance tickets
- **WHEN** an authenticated desktop reads pending assistance
- **THEN** it receives only fixed reason, state, account and opaque ticket ID, with no secrets or HTML
