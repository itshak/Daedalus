## ADDED Requirements

### Requirement: Controlled credential migration preserves the exact verified game identity

A session credential migration SHALL read existing private account metadata and a cookie only through authorized local sources, re-attest the exact configured world/player from a fresh TLS-verified nonredirecting read-only game page before promoting any legacy cookie, write it exclusively to protected encrypted storage, and verify readback without logging values. Restart SHALL preserve durable task receipts and SHALL NOT replay previous tasks. A completed backend service restart SHALL NOT be equated with whole-host reboot testing or real owner acceptance.

#### Scenario: Legacy saved cookie does not attest the configured player

- **WHEN** the saved source cookie fails fresh server player/world attestation
- **THEN** no unverified cookie is promoted and the controlled worker restart is blocked

#### Scenario: A prior task request has an uncertain outcome

- **WHEN** an operator identifies a prior uncertain task after confirming no managed task is active
- **THEN** reconciliation may mark only that inspected request with an auditable, nonreplaying receipt; it never asserts that the prior game action succeeded
