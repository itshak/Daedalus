## ADDED Requirements

### Requirement: Periodic authoritative account status refresh

The desktop monitoring poll SHALL refresh both backend account session state and worker connection status. Known invalid owned sessions SHALL NOT be displayed as connected workers; a failed account-status poll SHALL replace stale success indicators with unknown rather than implying current authentication.

#### Scenario: External login invalidates a native session

- **GIVEN** an open desktop Accounts screen showing authenticated and connected
- **WHEN** the backend reports session loss on a subsequent monitoring poll
- **THEN** both account indicators SHALL reflect the new authoritative state without requiring a manual refresh.
