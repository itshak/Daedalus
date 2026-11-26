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

### Requirement: Bound read-only military DTOs
The controller SHALL expose authenticated existing-session military inventory and movement reads with explicit account/world/player checks, bounded list sizes and sanitized names, counts, and server-observed timestamps. It SHALL reject a city belonging to another account rather than returning guessed or cross-account military data.

#### Scenario: Foreign military city
- **WHEN** the source engine returns a unit row whose city is not in the selected account's verified city list
- **THEN** the read fails without displaying any military rows or launching an order

### Requirement: Upstream gameplay waiting compatibility
Native operations SHALL reuse the existing IkaBot operation-specific wait and queue-read contracts rather than create parallel gameplay waiting implementations. Verified cookie workers SHALL preserve the original bounded read-only AJAX request form for audited queue views, reject mutation fields and avoid implicit relogin. Infrastructure scheduling and explicit verification deadlines remain independent.

#### Scenario: Training, upgrade or miracle queue is occupied
- **WHEN** an existing upstream wait function reads the corresponding queue or cooldown on a verified cookie-only worker
- **THEN** the session adapter SHALL perform the exact allowlisted read with current identity and token verification and return the original response shape for the upstream function

#### Scenario: Construction supplies are still in transit
- **WHEN** a reviewed construction supply was dispatched but the destination does not yet have sufficient stock
- **THEN** the worker SHALL use the upstream fleet-arrival estimate and wait helper, recheck actual stock before upgrading and stop at the review deadline rather than infer delivery
