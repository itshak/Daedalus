## ADDED Requirements

### Requirement: One-click native synthetic demo starts and stops a private temporary backend

The native Connection page SHALL provide an explicitly selected synthetic demo action that launches an isolated local fake backend, automatically connects the desktop through the existing bearer API, and visibly labels all displayed data as synthetic. It MUST NOT require the user to enter or paste an API bearer token for this demo, and SHALL stop its temporary server when the desktop closes.

#### Scenario: User clicks offline demo
- **WHEN** the user explicitly chooses Try offline demo
- **THEN** Daedalus SHALL start a synthetic-only backend on an ephemeral loopback port, connect using an in-memory bearer token and display fictional accounts/warehouses, never real game data

#### Scenario: User closes desktop
- **GIVEN** an embedded demo server is running
- **WHEN** the user closes the native window
- **THEN** its API client and local demo service SHALL be stopped without leaving a live game worker
