## ADDED Requirements

### Requirement: Safe restoration of eligible warehouse-fill jobs
Newly approved warehouse-fill jobs SHALL be eligible for automatic restoration only when durable dispatch evidence and fresh owned-city reconciliation establish remaining approved source limits and destination capacity. Legacy or ambiguous jobs MUST remain held for review.

#### Scenario: Restart after confirmed shipment
- **WHEN** an eligible job's authenticated worker is restored following backend restart or reconnection
- **THEN** confirmed shipments, current stock and in-transit cargo constrain a fresh upstream execution of remaining approved allocation
- **AND** original source caps are not increased

#### Scenario: Shipment acknowledgement is uncertain
- **WHEN** durable evidence cannot prove the prior effect
- **THEN** automatic restoration does not dispatch and the reason is shown to the operator
