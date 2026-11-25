## ADDED Requirements

### Requirement: Reviewed versioned operation coverage
The controller SHALL publish the versioned reviewed operation manifest, including platform availability, review policy and supported scopes. Unsupported operations MUST NOT become executable merely because they are present in the engine registry.

#### Scenario: The engine exposes an unreviewed operation
- **WHEN** the capability catalog is loaded
- **THEN** the operation is unavailable for native launch until reviewed

### Requirement: Account-bound reviewed operation tickets
Supported ticket-based workflows SHALL use nonmutating scoped previews with expiry, validated execution, unique request IDs, durable receipts and independent worker revalidation. One-shot actions MUST NOT be restored as ongoing jobs.

#### Scenario: A previously reviewed preview is stale
- **WHEN** a launch references a stale or mismatched preview
- **THEN** the controller rejects it and requires a fresh preview and review

#### Scenario: A supported selected-account batch is requested
- **WHEN** supported batch execution is approved
- **THEN** each account uses its own validated plan and receipt, and uncertain dispatch stops further execution without automatic replay

### Requirement: Account-scoped receipt history
The controller SHALL expose bounded, bearer-protected, account-scoped receipt history containing only request identity, task, dispatch status and recorded timestamps.

#### Scenario: Older receipt has no timestamp
- **WHEN** a client reads a migrated ledger entry
- **THEN** the unknown timestamp remains unknown and no raw logs or credentials are returned
