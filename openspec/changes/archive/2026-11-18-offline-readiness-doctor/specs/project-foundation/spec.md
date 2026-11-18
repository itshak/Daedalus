## ADDED Requirements

### Requirement: Setup diagnostics reflect implemented scope without reading private accounts

The `doctor` command SHALL report known offline preview capabilities and optional dependency availability, SHALL mark uninspected live account and game state as unknown, and SHALL NOT claim production readiness. It MUST NOT read game cookies, account configuration or keyring secrets or make network requests by default.

#### Scenario: User checks base installation
- **WHEN** the user runs `daedalus doctor`
- **THEN** it SHALL produce machine-readable diagnostics for engine source/CLI, server, desktop, existing-session capabilities, and lack of new worker bootstrap/automatic browser login

### Requirement: Synthetic end-to-end API smoke is explicit and isolated

The `doctor --smoke` option SHALL exercise actual authenticated backend API routes in-process using only synthetic demo accounts, warehouses and capabilities. It MUST NOT establish an external socket or contact Gameforge. Missing optional test dependencies or failed isolation SHALL produce a nonzero result with a sanitized error.

#### Scenario: Complete offline smoke
- **WHEN** a user invokes `daedalus doctor --smoke` with test dependencies installed
- **THEN** authorization, synthetic account metadata, capabilities and fake warehouse reporting SHALL pass, and the output SHALL remain labeled synthetic with zero game requests
