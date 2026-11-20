## ADDED Requirements

### Requirement: Compact, understandable account identity and status
The Accounts table SHALL prefer the server-verified Gameforge email over
generic imported labels, render Russian world codes as a country flag plus
exact server number, and display enabled/session/worker states as accessible
status glyphs with explanatory tooltips. Unknown worker attachment MUST NOT
be displayed as a negative result. The GUI SHALL offer all-account encrypted
backup of previously saved Mac logins.

#### Scenario: Imported Russian account without a verified world name
- **GIVEN** an account on s58-ru with a verified email but no verified world name
- **WHEN** the Accounts view is rendered
- **THEN** the email and the Russian flag with S58 appear along with clear
  check/X/unknown status indicators
