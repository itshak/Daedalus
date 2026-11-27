## ADDED Requirements

### Requirement: Private bounded telemetry
Telemetry SHALL be account-bound, schema-validated, privately retained and free of credentials, raw game responses, secrets and raw runtime logs. Clients MUST NOT create telemetry events or bypass reviewed task control.

#### Scenario: Telemetry retention or storage failure
- **WHEN** old detail is pruned or the telemetry store becomes unavailable
- **THEN** coverage is explicit and authoritative dispatch and recovery records are preserved
- **AND** no game operation is replayed or authorized by telemetry
