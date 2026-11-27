## ADDED Requirements

### Requirement: Durable logical task identity and evidence-aware statistics
The controller SHALL track logical tasks independently of engine processes and receipts, with account-bound execution runs, typed activity observations and operation-specific statistics. Telemetry MUST NOT authorize or replay operations.

#### Scenario: An approved task is safely restored
- **GIVEN** a task with a trustworthy logical identity and an authorized recovery receipt
- **WHEN** a new engine run is registered
- **THEN** its activities attach to the same logical task and confirmed totals do not reset or double count
- **AND** an uncertain prior dispatch remains governed by existing recovery policy

#### Scenario: Events arrive twice or are missing
- **WHEN** a duplicated or out-of-order observation arrives or telemetry is unavailable
- **THEN** duplicate events do not increase totals and gaps or uncertainty are explicitly represented
- **AND** telemetry failure does not cause a game action or retry

#### Scenario: A task has several shipments
- **WHEN** actual upstream observations confirm multiple dispatches
- **THEN** the task shows distinct shipment count and resource totals at each supported evidence level
- **AND** dispatch confirmation MUST NOT be represented as delivery
