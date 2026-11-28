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


#### Scenario: Unknown warehouse cargo could overlap another restored transport
- **WHEN** a warehouse checkpoint has pending or accepted-but-unobserved cargo
- **THEN** automatic transport restoration for that account remains held, including other transport workflows
- **AND** independent non-transport monitoring jobs may recover normally

#### Scenario: The approved intent or destination budget is exhausted
- **WHEN** receipt reconciliation proves all approved cargo was submitted or a fresh destination observation proves the remaining storage budget is zero
- **THEN** the completed intent and reason are durably retired, and shall not be restarted merely because space reopens or a later job is approved
