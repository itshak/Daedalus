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

#### Scenario: Native cookie worker already owns the authenticated account
- **WHEN** an existing controller-local worker holds the exact authenticated lease and protected IPC verifies its identity
- **THEN** the controller adopts that lease before reserving dispatch instead of attempting a second acquisition; failed pre-dispatch ownership checks SHALL NOT create an unconfirmed engine receipt

#### Scenario: A managed warehouse child cannot be registered
- **WHEN** process registration fails before execution
- **THEN** the child SHALL NOT perform a shipment and the controller MUST NOT replay an ambiguous request

#### Scenario: Reviewed cookie-only transport
- **WHEN** a reviewed warehouse task executes on a cookie-only worker
- **THEN** the existing IkaBot sender SHALL attest the current player and use bounded same-world nonredirecting requests, and SHALL NOT automatically replay an uncertain transport POST

#### Scenario: Live acceptance through the existing authorized API
- **WHEN** a trusted host operator prepares a warehouse review
- **THEN** the operator runner SHALL retain the review privately and require the exact explicit request confirmation before a single launch attempt; it MUST NOT equate a launch receipt with delivery

#### Scenario: A managed transfer fails or waits for ships
- **WHEN** the warehouse worker is running or exits before its reviewed cargo is confirmed
- **THEN** the controller SHALL expose a bounded execution stage and separately observed submitted and advisor-verified quantities, and the clients MUST NOT equate worker launch or exit with arrival

#### Scenario: Transport feedback commands are reordered or rejected
- **WHEN** the game returns a reviewed transport response
- **THEN** the worker SHALL classify named feedback independently of command ordering, distinguish rejection from unconfirmed response, verify selected source context before submission, and MUST NOT count unknown outcomes as successful or replay them automatically.

#### Scenario: Shared upstream shipment implementation
- **WHEN** a reviewed warehouse allocation is executed
- **THEN** the worker SHALL normalize the allocation through the existing IkaBot sendResources preparation, use the shared route executor and sender, and enforce warehouse-specific capacity and incoming-cargo rules through an internal policy rather than a separate transport loop

#### Scenario: Verified cookie worker uses the common sender
- **WHEN** the shared sender submits a transport on an already verified cookie-only session
- **THEN** the standard Session.post interface SHALL preserve the upstream transport form, require the exact selected source and a fresh token, and perform one bounded submission without login or replay; contradictory responses MUST remain unconfirmed

#### Scenario: Reviewed shipment exhausts available vessels
- **WHEN** a verified load occupies all available vessels and reviewed cargo remains
- **THEN** the shared upstream waitForArrival mechanism SHALL use its original military-advisor AJAX request through the protected cookie session, await the next fleet event, recheck available vessels, and continue the same reviewed allocation only when ships are available

#### Scenario: Resource Transport Manager waits for vessels
- **WHEN** a recurring consolidation or distribution shipment requires available vessels
- **THEN** it SHALL use the same shared upstream fleet-wait helper as ordinary shipments and warehouse filling before acquiring its shipping lock; the shared route executor SHALL recheck fleet availability before sending
