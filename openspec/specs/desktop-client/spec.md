# Desktop Client

## Purpose
Extend the existing native PySide6 GUI to expose every supported engine operation.

## Requirements

### Requirement: Comprehensive task controls
The desktop SHALL expose supported task types through discoverable categories, configuration editors, validation, progress, and error states.

#### Scenario: New registered engine task
- **GIVEN** an engine task has a compatible schema
- **WHEN** the GUI loads the backend task registry
- **THEN** the GUI can present an actionable configuration without terminal keystroke automation

### Requirement: Common local and remote behavior
The GUI MUST use the same API contract in local and remote modes.

#### Scenario: Switching between local and remote
- **WHEN** the user changes backend connection
- **THEN** account status, snapshots and task configuration remain accessible through the same client flows
