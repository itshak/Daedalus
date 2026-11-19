# Controller API — reviewed account-bound operation data

## ADDED Requirements

### Requirement: Authenticated contextual read models
The controller SHALL expose bounded, typed, sanitized existing-session read endpoints for each UI domain that needs account-specific options. Every returned entity SHALL be bound to an enabled configured account and its verified world/player session, identify source and observation freshness, and exclude cookies, credentials, raw game HTML and arbitrary engine state.

#### Scenario: Wrong account city or building requested
- **WHEN** a caller requests a city or building absent from the selected verified account
- **THEN** the controller rejects that request rather than returning data or reusing another account's cache

#### Scenario: Game session unavailable
- **WHEN** the backing authenticated session is not uniquely present
- **THEN** the endpoint returns a sanitized unavailable result and the desktop leaves the selector disabled

### Requirement: Nonmutating native plan previews
The controller SHALL only offer preview/prepare operations explicitly audited as read-only. Plans SHALL include a hash/revision, scope and expiry; dispatch SHALL independently validate eligibility, required current game state and allowed IkaBot arguments before start.

#### Scenario: Construction preview
- **GIVEN** authoritative city building data and chosen upgrade target
- **WHEN** the client requests a preview
- **THEN** the controller delegates resource and duration computation to approved upstream IkaBot logic, returns a bounded nonsecret plan, and performs no game mutation

#### Scenario: Stale preview after changing account
- **WHEN** the selected account, world, session ownership or building revision changes
- **THEN** the previous plan cannot be dispatched

### Requirement: User-approved per-account task dispatch
The API SHALL preserve durable request IDs, config fingerprint, explicit confirmation, managed task ownership, and unconfirmed-no-retry semantics for native operation flows, including batch modes.

#### Scenario: Ambiguous task result
- **WHEN** the controller cannot establish whether an operation started
- **THEN** it retains the unconfirmed receipt, blocks further launches on that account, and directs the operator to manual reconciliation
