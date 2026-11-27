## ADDED Requirements

### Requirement: Explicit recovery eligibility
The controller SHALL expose task-specific recovery eligibility and reason to authorized clients, distinguishing desired running intent from actual active execution.

#### Scenario: A legacy fill task has no checkpoint
- **WHEN** the operator views saved jobs
- **THEN** the task is shown as manual review rather than automatically restorable or running
