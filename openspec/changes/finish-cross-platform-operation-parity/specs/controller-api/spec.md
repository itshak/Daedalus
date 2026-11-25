## ADDED Requirements

### Requirement: Remaining operation parity and acceptance gate
The controller and both clients SHALL complete the outstanding reviewed operation contracts and account-specific workflows recorded in the preceding implementation matrix. Missing or unsupported options SHALL stay explicitly unavailable rather than become raw execution paths.

#### Scenario: A missing option is requested
- **WHEN** an operator selects a workflow that lacks an authoritative adapter or required native controls
- **THEN** dispatch remains unavailable until the adapter and its verification are implemented

#### Scenario: Full parity release is requested
- **WHEN** release acceptance is evaluated
- **THEN** every original criterion has verified evidence or an explicitly approved protected alternative, and required CI and owner-operated acceptance are complete
