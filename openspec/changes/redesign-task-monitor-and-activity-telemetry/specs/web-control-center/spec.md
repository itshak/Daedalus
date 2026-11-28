## ADDED Requirements

### Requirement: Task-first web monitoring
The web client SHALL replace the primary Activity view with a Tasks monitor, supporting all/selected/one accounts, player names, task status filters, per-operation summaries and responsive accessible details. Existing receipt history and world reports MUST remain accessible.

#### Scenario: Operator selects a running warehouse task
- **WHEN** the task card or row is opened
- **THEN** the detail presents cumulative evidenced metrics, individual expandable activities, waiting and run history, approved configuration and technical receipts
- **AND** unobserved metrics and unavailable accounts are clearly distinguished from zero

#### Scenario: Older backend or incomplete telemetry
- **WHEN** the controller lacks the new capability or event coverage is partial
- **THEN** compatible receipt and lifecycle views remain usable with explicit limits
