## ADDED Requirements

### Requirement: Complete source-audited operation coverage
The integration SHALL inventory the union of public menu actions, registered tasks and interactive submenus, and SHALL maintain dedicated reviewed adapters for supported operations. Missing registry rows or missing required platform coverage SHALL fail the parity gate. Interactive-only operations MUST NOT be executed through arbitrary CLI prompt injection or unreviewed module dispatch.

#### Scenario: Upstream adds an operation
- **WHEN** the vendored engine inventory changes
- **THEN** CI reports any operation without a reviewed coverage entry, contract and test mapping

### Requirement: Game-authoritative native planning
Engine adapters SHALL derive city, building, unit, offer, island, route, schedule and other game-dependent options from authenticated scoped observations and independently validate their plans before mutation.

#### Scenario: A route target no longer exists or is not eligible
- **WHEN** a transport draft is prepared or executed
- **THEN** the engine rejects the unavailable target without guessing an identifier or sending resources
