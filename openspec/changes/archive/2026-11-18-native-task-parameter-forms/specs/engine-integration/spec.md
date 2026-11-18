## ADDED Requirements

### Requirement: Offline bounded task parameter metadata
The engine registry SHALL derive form metadata only from parsed public IkaBot source files without importing game modules or evaluating arbitrary expressions.

#### Scenario: Task has a runtime default expression
- **GIVEN** a task default argument is a function call rather than a literal
- **WHEN** offline registry introspection inspects that task
- **THEN** no expression is executed and no fabricated default value is returned
