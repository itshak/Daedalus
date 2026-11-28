## ADDED Requirements

### Requirement: Reuse reviewed upstream worker assignments
Production orchestration SHALL reuse existing IkaBot worker slider reads and shared assignment helpers, validate actual capacity and verify each staged mutation. Unknown outcomes MUST NOT be blindly retried.

#### Scenario: Donor release succeeds but target fails
- **WHEN** the target assignment is proven not to have been submitted or definitively fails after confirmed donor reduction
- **THEN** safe restoration within the reviewed original donor allocation is attempted only with fresh verified state
- **AND** unresolved state remains visible for review


#### Scenario: An assignment response is ambiguous
- **WHEN** a submitted target assignment times out, returns an unverified response or cannot be confirmed by authoritative readback
- **THEN** no subsequent mutation or blind compensation is allowed
- **AND** the pending receipt and observed allocations remain available for explicit reconciliation
