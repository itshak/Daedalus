# Web Access Security

## ADDED Requirements

### Requirement: Closed first-admin provisioning
The web MUST deny private access by default, disable public sign-up, and support an owner-provisioned invitation or secure one-time bootstrap with server-side verified administrator authorization. It MUST NOT publish a default password or let the first anonymous visitor claim ownership.

#### Scenario: Unprovisioned app
- **GIVEN** the initial deployment has no administrator
- **WHEN** an anonymous visitor opens a private route
- **THEN** the server denies private data and offers no unauthenticated owner enrollment

#### Scenario: Expired operator session
- **WHEN** an operator session expires or is revoked
- **THEN** a protected read or mutation is rejected without returning private data

### Requirement: Server-only controller credentials and fixed gateway
The browser MUST NOT receive Daedalus API bearer tokens, SSH credentials, Gameforge passwords, game cookies, login vaults or Supabase service-role secrets. Each protected BFF request SHALL verify web identity and server-side authorization; only allowlisted typed controller operations MAY be forwarded over TLS using a server-only bearer.

#### Scenario: Browser inspects requests
- **WHEN** the authorized browser loads Accounts
- **THEN** browser-visible network requests and rendered assets contain no backend bearer or game credential

#### Scenario: Unknown path or host injection
- **WHEN** a caller supplies an arbitrary target URL, native login-vault route or unapproved method
- **THEN** the BFF rejects it before forwarding any upstream request

### Requirement: Mutations remain authenticated and isolated
All mutations MUST enforce CSRF/origin protection, account/world identity, typed payload constraints, explicit review/consent and existing backend session ownership/revision/idempotency semantics. Web auth alone MUST NOT grant arbitrary IkaBot task dispatch.

#### Scenario: Cross-account payload
- **GIVEN** a reviewed city ID belongs to account A
- **WHEN** a request attempts to use it for account B
- **THEN** the gateway/backend rejects the scope mismatch and no action executes

#### Scenario: Duplicate request
- **WHEN** the same task request is submitted twice or its outcome is uncertain
- **THEN** idempotency/reconciliation prevent a second unreviewed game mutation

### Requirement: Privacy, caching and audit boundaries
The web SHALL use secure cookies, no-store/private headers, conservative CSP, bounded request/response sizes, rate limiting, redacted errors and minimum-necessary audit metadata. Supabase RLS and migrations MUST restrict preferences/audits to authorized principals and SHALL NOT store real game snapshots or credentials.

#### Scenario: Public CDN/cache attempts
- **WHEN** an unauthenticated visitor requests a cached game report or private application document
- **THEN** no privileged account data is disclosed

#### Scenario: Error or telemetry path
- **WHEN** FastAPI returns an error or upstream connectivity fails
- **THEN** user-visible and diagnostic records omit bearer tokens, sensitive response bodies and game login material

### Requirement: Verified secure deployment
Production SHALL be delivered through the requested Vercel project/domain with validated DNS/TLS, backend ingress reachability, server-only secrets, private previews and reversible rollout. It SHALL NOT expose Daedalus worker IPC or weaken backend authentication as a connectivity workaround.

#### Scenario: Production smoke check
- **WHEN** the deployment is checked at `https://daedalus.tongrix.com`
- **THEN** anonymous private requests are denied, authorized BFF→FastAPI reads succeed, and no browser-exposed backend token is present

#### Scenario: Backend unavailable
- **WHEN** Vercel cannot reach the trusted API over verified TLS
- **THEN** the UI reports unavailable and no alternate insecure backend URL is tried
