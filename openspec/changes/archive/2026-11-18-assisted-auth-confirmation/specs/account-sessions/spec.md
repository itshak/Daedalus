## ADDED Requirements

### Requirement: Lease-bound manual authentication assistance

The controller SHALL issue a bounded-lifetime, single-use assistance ticket only to a trusted in-process worker holding the matching account identity lease. A ticket SHALL contain only a random identifier, fixed nonsecret reason and status, never cookies, credentials, or session material.

#### Scenario: Operator completes manual login step
- **GIVEN** a currently owned session with a valid assistance ticket
- **WHEN** a human confirms the manual step is complete
- **THEN** the owner SHALL remain unverified and MUST NOT become authenticated solely on human acknowledgment

#### Scenario: Worker independently verifies
- **GIVEN** a confirmed ticket attached to the same lease
- **WHEN** the trusted worker verifies the actual game session
- **THEN** only that worker MAY transition the owner to authenticated
- **AND** failure SHALL require a new manual ticket before another confirmation

#### Scenario: Expired assistance
- **WHEN** an assistance ticket expires
- **THEN** further approvals SHALL be refused and the owner SHALL pause while retaining its account lease
