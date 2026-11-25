# web-access-security Specification

## Purpose
Enforce reviewed web dispatch and protected administrative boundaries.

## Requirements

### Requirement: Typed web operation authorization
The BFF SHALL reject unapproved routes and unvalidated operation-specific drafts, require authenticated operator authorization for mutations and keep controller credentials server-side.

#### Scenario: Operator requests an unapproved raw engine payload
- **WHEN** the browser submits the request
- **THEN** the BFF rejects it before forwarding to the engine

### Requirement: Nonsecret protected administration status
Desktop and web administrative status SHALL be account-scoped and read-only, returning only approved provider status, proxy protocol/port/authentication presence, challenge provider category and extension count. Raw credentials, cookies, endpoints, extension paths and arbitrary commands MUST NOT be exposed.

#### Scenario: A user reads protected settings
- **WHEN** the authenticated account status is requested
- **THEN** only the validated nonsecret projection is displayed and no settings are changed
