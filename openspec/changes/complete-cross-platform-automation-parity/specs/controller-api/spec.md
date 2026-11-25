## ADDED Requirements

### Requirement: Reviewed versioned operation contracts
The controller SHALL publish reviewed versioned per-operation availability, draft schemas, inventory requirements, scope and platform policy; it SHALL validate operation-specific drafts and independently enforce authenticated account ownership, typed field bounds and eligibility. AST-inferred opaque parameters MUST NOT be treated as user-editable configuration.

#### Scenario: Invalid city or unknown parameter
- **WHEN** a client submits a draft with another account's city or unknown fields
- **THEN** the controller rejects it before any game mutation

### Requirement: Authoritative effect preview and receipt
The controller SHALL provide side-effect-free operation previews with scope, normalized effect summary, revision or expiry, and a validated execution pathway with unique request IDs, durable receipts and independent live revalidation. One-shot actions MUST NOT be restored as ongoing jobs.

#### Scenario: A previously reviewed preview is stale
- **WHEN** a launch references a stale or mismatched preview
- **THEN** the controller rejects it and requires a fresh preview and review

#### Scenario: A selected-account batch is requested
- **WHEN** supported batch execution is approved
- **THEN** each account uses its own validated plan and receipt, and uncertain dispatch stops further execution without automatic replay
