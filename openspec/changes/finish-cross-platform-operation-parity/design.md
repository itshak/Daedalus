# Design

Build on the archived native implementation and its capability matrix. Keep one authoritative IkaBot engine, single-owner session semantics, account-specific typed inputs, expiring review tickets, durable receipts and explicit human approval. Do not reintroduce editable serialized task settings or raw remote game services.

Use the existing protected-administration status panel as the entry point for audited configuration management. Credential writes require approved secure transport and redacted receipts; do not bypass execution-environment restrictions. Where a direct implementation is unsafe, obtain explicit owner approval for a documented secure equivalent.

Extend the operation manifest rather than treating a catalog entry as full feature coverage. Add shared fixtures and contract versioning, exact per-operation parity tests, responsive accessibility verification and owner-operated acceptance. Before release, verify required GitHub CI, packaged Mac installation, production compatibility and rollback.

The full original design and scope are preserved in original-design.md, original-tasks.md and original-spec-targets.md. Existing active desktop, web and recovery changes must be reconciled rather than silently archived.
