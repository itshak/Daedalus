## ADDED Requirements

### Requirement: Remaining operation parity and acceptance gate
The controller and both clients SHALL complete the outstanding reviewed operation contracts and account-specific workflows recorded in the preceding implementation matrix. Missing or unsupported options SHALL stay explicitly unavailable rather than become raw execution paths.

#### Scenario: A missing option is requested
- **WHEN** an operator selects a workflow that lacks an authoritative adapter or required native controls
- **THEN** dispatch remains unavailable until the adapter and its verification are implemented

#### Scenario: Full parity release is requested
- **WHEN** release acceptance is evaluated
- **THEN** every original criterion has verified evidence or an explicitly approved protected alternative, and required CI and owner-operated acceptance are complete


### Requirement: Reviewed multi-city military deployment
Supported owned-city deployment SHALL support a single origin or all other owned origins and ground, fleet or combined categories. A reviewed plan SHALL identify all covered routes, account for shared transport capacity once, and revalidate each route before dispatch.

#### Scenario: Shared capacity is insufficient
- **WHEN** aggregate ground cargo exceeds observed available transport capacity
- **THEN** no deployment ticket is issued

#### Scenario: A route becomes stale
- **WHEN** a reviewed route changes before its submission
- **THEN** remaining submissions stop and previously submitted routes are not automatically retried or rolled back


### Requirement: Reviewed multi-city worker assignments
Worker assignment SHALL support selected owned cities and both production projects, with authoritative per-city and per-project observations. The reviewed operation SHALL revalidate each assignment before a single non-retried submission.

#### Scenario: A worker assignment changes after approval
- **WHEN** the city, project or observed slider state differs from the reviewed plan
- **THEN** execution stops before submitting that changed assignment and remaining assignments are not retried automatically


### Requirement: Reviewed recruitment rounds and repetitions
The controller SHALL expose bounded ordered recruitment rounds and repeat cycles across selected owned cities. Each reviewed plan SHALL contain actual per-city unit identities and costs and SHALL require an account-scoped launch ticket. The worker SHALL revalidate the reviewed data and current resources before submitting each round once.

#### Scenario: A later training round is uncertain
- **WHEN** a submitted round cannot be observed in the training queue or the reviewed inventory changes
- **THEN** later rounds stop and are not automatically replayed
