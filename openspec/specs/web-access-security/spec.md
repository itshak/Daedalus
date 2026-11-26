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

### Requirement: Owner-approved encrypted notification configuration
Desktop and web SHALL permit explicit worker-global Telegram and Discord default replacement or clearing. Browser mutation SHALL require the owner role. Credentials SHALL be encrypted to a one-use, short-lived, identity-and-provider-bound worker key, never echoed or persisted in the clients or decrypted by the controller gateway. Replacement SHALL make one fixed-message test against the supported HTTPS provider without redirects before private atomic persistence. A legacy selected-account override SHALL block global-default modification until reconciled locally.

#### Scenario: Unauthorized or stale configuration
- **WHEN** a caller lacks owner authorization, submits plaintext, or uses an expired or foreign ticket
- **THEN** no provider configuration is written

#### Scenario: Provider test is rejected or uncertain
- **WHEN** the fixed provider test fails or its outcome is uncertain
- **THEN** the existing configuration is retained and no automatic retry occurs

### Requirement: Protected release discovery and diagnostic projection
Desktop and web SHALL expose current controller version, build revision when available, and published project Mac previews with exact release and checksum references. The catalog SHALL be explicitly requested, bounded, read-only and restricted to the fixed public project repository. Synthetic demo MUST remain offline. Clients MUST NOT interpret a preview or checksum link as verified notarization or release acceptance, and MUST NOT expose raw developer cookies, arbitrary commands or unauthenticated game proxy services.

#### Scenario: Untrusted release metadata
- **WHEN** a preview is missing the expected project assets or has a foreign download destination
- **THEN** no download link for that preview is offered

#### Scenario: An operator checks for an update
- **WHEN** the operator requests release discovery
- **THEN** the system displays validated metadata without modifying the controller, desktop or game session

### Requirement: Host-approved extension registration
Desktop and web SHALL expose a bounded, redacted catalog of locally installed, host-approved extensions. The worker SHALL verify the manifest identity and source digest before registering an extension and compare the current registration against the reviewed state. Web mutation SHALL require owner authorization and explicit worker-global consent. Registration MUST NOT download, upload, execute or delete code or disclose local filesystem paths. Legacy per-user overrides SHALL block shared-default mutation.

#### Scenario: An installed extension changes
- **WHEN** its source digest or reviewed registration state differs from the approved or observed value
- **THEN** registration fails without changing the shared configuration

#### Scenario: A previously registered extension is removed from the menu
- **WHEN** the owner confirms unregistering an approved entry
- **THEN** the shared registration is removed without deleting or executing its source file

### Requirement: Human-controlled managed game challenges
Managed piracy SHALL stop on encountering a game challenge without retrieving or solving the challenge or retrying the submission. Both clients SHALL expose an account-scoped stop or notify-and-stop preference, using compare-and-set and explicit confirmation. Browser writes SHALL require owner authorization. Notify-and-stop SHALL require a supported configured notification destination and send at most one fixed notice without challenge material. Managed restart SHALL require a fresh reviewed launch.

#### Scenario: A managed game challenge occurs
- **WHEN** the worker observes a challenge during a managed piracy mission
- **THEN** it stops without invoking an automated solver, fetching challenge material, or submitting an answer

#### Scenario: A preference is changed
- **WHEN** a caller submits a stale, foreign, unsupported or unauthorized policy
- **THEN** no preference is modified

### Requirement: Account-approved network profiles
Both clients SHALL expose redacted host-approved account-specific proxy profiles, with explicit test and save operations. Host-local manifests SHALL control available profiles and whether direct connection is permitted. Browser writes and connectivity tests SHALL require owner authorization. The controller and worker MUST reject caller-supplied endpoints, credentials, arbitrary test destinations and stale or foreign reviews. Before a save, the worker SHALL verify the account has no observed active tasks, make a single fixed public HTTPS test with TLS verification, no redirects and no game authentication, then recheck the approved catalog and saved profile state. Changes SHALL affect only the chosen account's upstream saved network preference and MUST NOT force a reconnect, rotate proxies automatically or bypass game challenges. Provisioning authenticated proxies remains host-local.

#### Scenario: A profile test is unsuccessful
- **WHEN** the fixed HTTPS connectivity check fails or a reviewed state changes during testing
- **THEN** no proxy preference is changed and the caller must refresh before attempting another review

#### Scenario: An account is active or a network profile is unapproved
- **WHEN** a caller attempts to test or save an unapproved profile or the selected account has an observed running task
- **THEN** the worker rejects the request without contacting the proposed endpoint or changing the preference

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
