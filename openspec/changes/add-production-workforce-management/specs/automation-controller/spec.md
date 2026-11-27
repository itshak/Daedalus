## ADDED Requirements

### Requirement: Resource-priority workforce allocation
A reviewed production allocation SHALL default to prioritizing the selected resource, including requested overcharge, using free citizens first and reallocating from the other production site in the same city only when necessary. An explicit available-population-only option SHALL prohibit donor reductions. No unrelated workforce SHALL be changed.

#### Scenario: Crystal requires more citizens than available
- **GIVEN** a reviewed crystal maximum including overcharge and a wood site in the same city
- **WHEN** free citizens are insufficient
- **THEN** the minimum necessary wood workers are released, crystal is filled to the feasible target, and unused released citizens are restored to wood up to its original allocation

#### Scenario: Exact shortfall cannot be calculated
- **WHEN** an explicitly reviewed fallback is necessary and initial allocations are authoritatively known
- **THEN** the donor can be temporarily emptied, the selected resource maximized and surplus returned to the donor
- **AND** uncertain assignment or ownership MUST stop further writes for reconciliation

#### Scenario: Available population only
- **WHEN** the operator selects the available-only option
- **THEN** the other production site remains unchanged and any target shortfall is reported

#### Scenario: A batch includes multiple accounts
- **WHEN** a resource-specific maximum plan is reviewed and started
- **THEN** only verified matching sites in the frozen selected accounts and cities are changed, using each site's own capacity
