## ADDED Requirements

### Requirement: Global working account context
The web shell SHALL provide persistent all, selected or one-account scope applied to every relevant page and automation editor, without widening server authorization.

#### Scenario: Operator narrows the scope
- **GIVEN** an automation preview for an account outside the new scope
- **WHEN** the operator changes the global scope
- **THEN** the old preview is invalidated and player/city selectors offer only in-scope eligible targets
- **AND** an empty scope never expands to all accounts
