# Delta: Desktop Client

## ADDED Requirements

### Requirement: Simple per-account and bulk recovery controls

Mac and web controllers SHALL show the backend-sourced recovery status and an explicit **Auto reconnect and restore jobs** policy for one, selected, or all accounts. The interface SHALL expose countdown, browser-use pause, next retry, nonsecret credential availability, resumed/blocked jobs, and Pause, Resume now, Disable and Review jobs actions.

#### Scenario: First-time automatic recovery enablement
- **GIVEN** an existing account with no approved unattended login policy
- **WHEN** the user opens its recovery settings
- **THEN** automatic reconnection SHALL be off, and enablement SHALL explain the possibility of logging the user out of an active game browser plus the task classes eligible for restoration

#### Scenario: Browser-use pause while disconnected
- **GIVEN** an account whose world session was rotated and is counting down
- **WHEN** the user selects Pause until manually resumed
- **THEN** the countdown SHALL change to Paused for browser use without launching a new lobby login or a task

#### Scenario: All-account policy review
- **GIVEN** several selected accounts with different credential availability and restartable task counts
- **WHEN** the owner chooses bulk enablement
- **THEN** Daedalus SHALL show an account-by-account preview, never silently enable unsupported credentials, and report distinct successes, skips and conflicts

#### Scenario: Partial job restoration
- **GIVEN** an account has some safely restored and some manually held jobs
- **WHEN** the client refreshes
- **THEN** it SHALL show the exact restored and blocked counts, reasons and existing idempotency receipt status without claiming complete success
