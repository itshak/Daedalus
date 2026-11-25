## ADDED Requirements

### Requirement: Web operation-specific authorization and safe administrative boundaries
The BFF SHALL validate authenticated operator role, account scope, origin, strict operation-specific schemas, request limits and allowed routes for every privileged operation. The controller bearer, session cookies and provider secrets MUST NOT be returned to the browser.

#### Scenario: Operator requests an unapproved raw engine payload or local-only secret route
- **WHEN** the browser submits the request
- **THEN** the BFF rejects it before forwarding to the engine

### Requirement: Protected administrative workflows
Local browser login and session transfer SHALL remain protected desktop/local workflows. Developer, custom extension and updater functionality SHALL use approved, reviewed management interfaces, not arbitrary command or code execution.

#### Scenario: A web operator needs a secure local session operation
- **WHEN** the operator selects that action
- **THEN** the web provides status and a guided approved local handoff without disclosing session material
