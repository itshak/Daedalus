## ADDED Requirements

### Requirement: Parameter-aware native task configuration
The desktop SHALL render per-task parameter controls derived from validated built-in engine capability metadata, including required status and primitive typing when safely identifiable.

#### Scenario: A task has an optional numeric parameter
- **GIVEN** the engine registry reports alertAttacks.minutes as an integer with a literal default
- **WHEN** the user selects alertAttacks in the native Tasks page
- **THEN** the GUI shows an integer field and can construct a JSON config with that value

#### Scenario: A complex task has nested parameters
- **GIVEN** the engine registry cannot infer a parameter type from a public signature
- **WHEN** the user selects that task
- **THEN** the GUI offers an explicitly JSON-typed form input plus the advanced JSON editor without guessing a game value

### Requirement: Explicit form review before task dispatch
The desktop MUST NOT launch a task using unreviewed form inputs, and must retain checkbox, confirmation dialog and backend validation for every game-state-changing request.

#### Scenario: A parameter form has edits that have not been applied
- **WHEN** the user clicks Start task after editing form fields without building/reviewing their JSON
- **THEN** the desktop refuses to emit the start action until the draft is reviewed
