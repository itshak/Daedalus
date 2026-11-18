## ADDED Requirements

### Requirement: Unambiguous native synthetic demo labeling

The desktop SHALL label the connected backend, warehouse resources and window title as SYNTHETIC DEMO whenever the backend identifies itself as a demo. It SHALL NOT visually represent demo amounts as live game observations.

#### Scenario: Demo backend is connected
- **GIVEN** a demo backend with synthetic account fixtures
- **WHEN** the desktop completes the authenticated handshake
- **THEN** the connection and resource views SHALL visibly display a synthetic warning and task controls SHALL remain disabled
