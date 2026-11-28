## ADDED Requirements

### Requirement: Upstream-first observational instrumentation
The engine integration SHALL reuse upstream action, response and waiting boundaries and emit bounded typed telemetry without adding game requests, changing retry behavior or duplicating gameplay implementations.

#### Scenario: A transport loop waits and resumes
- **WHEN** existing upstream waiting and transport helpers execute
- **THEN** observations record wait intervals and correlated shipment evidence where available
- **AND** telemetry cannot change the wait or dispatch decisions

#### Scenario: A task has no reliable domain observation
- **WHEN** the registry lacks evidence for an operation-specific metric
- **THEN** the metric is explicitly unavailable rather than fabricated
