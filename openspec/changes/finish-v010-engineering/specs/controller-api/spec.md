## ADDED Requirements

### Requirement: Separate engineering completion from owner acceptance
The project SHALL maintain one engineering backlog with concrete implementation and automated verification tasks. Historical superseded proposals SHALL retain their requirements, checked and unchecked status and explicit successor or owner dispositions. The stable release gate SHALL remain separate from engineering archival.

#### Scenario: Owner defers manual testing
- **WHEN** remaining human-operated game or device checks are deferred
- **THEN** they SHALL be recorded as not performed in the owner acceptance record and SHALL NOT prevent archival of verified engineering work
- **AND** no stable release or game-effect certification SHALL be inferred

### Requirement: Synthetic cross-platform release regression coverage
The project SHALL exercise the real supported UI, typed controller and protected upstream session boundaries with offline synthetic fixtures, including warehouse and military reads, scoped reviewed tasks and uncertain outcomes, account recovery and access control. The release verification SHALL distinguish automated evidence from production deployment and owner acceptance.

#### Scenario: A supported read or reviewed operation regresses
- **WHEN** a synthetic game response or client contract changes
- **THEN** tests SHALL detect incorrect visible values, scope, unexpected mutation, duplicate dispatch or false success before release
