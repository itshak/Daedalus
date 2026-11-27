## ADDED Requirements

### Requirement: Working scope does not confer authorization
Account scope preferences MUST NOT expand account authorization or reuse a review with an altered target set.

#### Scenario: A stale scoped response arrives
- **WHEN** an earlier scope request completes after a scope change
- **THEN** it cannot populate current targets or enable dispatch
