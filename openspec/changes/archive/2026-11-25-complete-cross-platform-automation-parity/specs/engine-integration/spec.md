## ADDED Requirements

### Requirement: Source-audited operation coverage manifest
The integration SHALL inventory public menu actions and registered tasks and maintain an explicit coverage entry for each. Missing registry rows SHALL fail the inventory drift test. Coverage status MUST NOT imply full upstream or live acceptance.

#### Scenario: Upstream adds an operation
- **WHEN** the vendored engine inventory changes
- **THEN** the coverage test reports an operation without a reviewed entry

### Requirement: Reviewed external transport recipient verification
Native external shipments and recurring external consolidation SHALL bind the observed island, city and recipient identities, rechecking the receiving identity before dispatch and cargo requests. External routes MUST NOT be automatically restored.

#### Scenario: A reviewed recipient changes
- **WHEN** recipient ownership or eligibility changes before a shipment
- **THEN** the engine stops rather than sends to a changed recipient
