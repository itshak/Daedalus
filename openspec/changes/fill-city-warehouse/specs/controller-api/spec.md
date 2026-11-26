## ADDED Requirements

### Requirement: Fill an owned city's warehouse for one resource
The controller SHALL offer a one-time, account-scoped transfer of one selected resource from all other owned cities into a chosen owned destination. The reviewed allocation SHALL NOT exceed observed free storage less observed inbound cargo. The worker SHALL check fresh stock, destination identity, storage and inbound cargo before each submission, stop on ambiguous cargo or outcome, and MUST NOT automatically replay interrupted work. The clients SHALL show quantities by source and the overall storage budget, and distinguish observations from guaranteed arrival capacity.

#### Scenario: Incoming cargo consumes warehouse space
- **WHEN** a destination has current free space and already incoming cargo
- **THEN** the available allocation is reduced by the incoming amount, and all reviewed source quantities together fit within that allocation

#### Scenario: Storage becomes unavailable during execution
- **WHEN** fresh observations cannot support a reviewed load
- **THEN** the worker stops or reduces that load within the reviewed limit without exceeding the observed remaining budget

#### Scenario: A warehouse preview cannot be verified
- **WHEN** the selected warehouse, source stock, incoming cargo or fleet observation is unavailable
- **THEN** the clients show a bounded nonsecret failure reason and no launch is authorized; a pending preview is visibly distinguished from a completed review
