## ADDED Requirements

### Requirement: Native monitoring consent and nonsecret assistance notifications

The Accounts page SHALL offer an explicit monitor action only when the backend indicates that existing-session validation is enabled. The UI SHALL demand a separate confirmation before sending a monitoring request and SHALL show a bounded nonsecret notification for a new waiting assistance ticket without repeating the same notification.

#### Scenario: User cancels monitoring
- **WHEN** the user declines the dialog to monitor a selected account
- **THEN** the desktop SHALL send no monitoring request

#### Scenario: New expired-session ticket
- **WHEN** a connected monitored backend reports a waiting ticket
- **THEN** the desktop SHALL notify the operator without revealing a cookie, token, ticket ID or full game response, and SHALL NOT automatically replay a task
