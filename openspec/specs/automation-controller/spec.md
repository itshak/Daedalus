# Automation Controller

## Purpose
Schedule game tasks safely and reconcile desired policy with observed game state.

## Requirements

### Requirement: Idempotent policy reconciliation
The controller MUST check live state and pending operations before repeating any state-changing request.

#### Scenario: Service restart during upgrade
- **GIVEN** a construction job may have been accepted before restart
- **WHEN** the controller resumes
- **THEN** it checks current building and task state before scheduling an additional upgrade

### Requirement: Native transport execution
Wine and construction-supply policies SHALL delegate transport execution to upstream engine modules.

#### Scenario: Planned wine shipment
- **WHEN** the policy calculates a needed wine transfer
- **THEN** a validated engine transport operation is requested rather than using a second HTTP game client
