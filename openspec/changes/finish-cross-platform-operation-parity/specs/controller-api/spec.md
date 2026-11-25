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


### Requirement: Reviewed construction supply
The controller SHALL support optional owned-city suppliers, bounded exact shortages, optional rounded cargo, trade ships or freighters, and explicit supply-only or supply-then-build execution. It SHALL expose source allocation, remaining shortages and observed fleet and storage capacity. A supplied construction job SHALL NOT be launched from raw configuration or automatically replayed after interruption.

#### Scenario: Supply is insufficient
- **WHEN** the selected sources or destination storage cannot cover the required shortage, or the fleet is unavailable
- **THEN** no launch ticket is issued

#### Scenario: A shipment outcome is uncertain
- **WHEN** a reviewed supply dispatch cannot be confirmed
- **THEN** subsequent construction is not attempted and the job requires manual reconciliation

#### Scenario: Supplies are dispatched
- **WHEN** a combined plan has dispatched its exact cargo
- **THEN** the worker verifies sufficient destination stock and the reviewed construction state before upgrades


### Requirement: Conditional transport delivery model
A shipment review MAY model delivery of all loads using the observed port and fleet parameters when the entire fleet is available, the single route has verified owned-city storage for all cargo and the timing observation is complete. The clients SHALL state the exclusive-fleet, symmetric-return and unchanged-loading assumptions and MUST NOT present the estimate as a guaranteed arrival. Missing observations and concurrent or multiple routes MUST NOT produce a fabricated combined arrival time.

#### Scenario: The reviewed cargo becomes unavailable
- **WHEN** source identity or stock changes between route selection and reservation
- **THEN** the worker stops before reserving or sending the changed cargo

#### Scenario: Multiple loads can be modeled
- **WHEN** a single owned route has a complete timing observation, sufficient storage and the whole fleet available
- **THEN** the review displays a conditional final delivery calculation including intervening return journeys and the last partial load

### Requirement: Exact research advisor choices
The authenticated academy inventory SHALL include a bounded projection of available study choices when the upstream research advisor can be observed. Both native clients SHALL expose a named study selection separately from experiments. The worker SHALL revalidate the exact current advisor entry before launch and before the single non-retried study submission. Missing or changed observations MUST NOT cause an alternate study or experiment to execute.

#### Scenario: Study availability changes
- **WHEN** the selected advisor entry no longer matches the reviewed name and research type
- **THEN** the worker rejects the selection without a study mutation
