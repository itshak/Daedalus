# Controller API

## Purpose
Provide a versioned, authenticated read-only service for local and remote desktop clients before enabling state-changing engine task dispatch.

## Requirements

### Requirement: Authenticated account and capability views
The controller SHALL expose account metadata and engine capability descriptions over versioned HTTP endpoints requiring bearer authentication.

#### Scenario: Unauthorized account enumeration
- **GIVEN** a running controller
- **WHEN** an unauthenticated client requests the account list
- **THEN** the server returns HTTP 401 without account details

### Requirement: Secure development binding
The initial controller CLI MUST bind only to the loopback interface and MUST require a cryptographically unpredictable API bearer token of at least 32 characters.

#### Scenario: Non-loopback bind requested
- **WHEN** an operator requests binding to a non-loopback address
- **THEN** startup fails with instructions to use a protected tunnel

### Requirement: No fabricated account or warehouse activity
Until an authenticated IkaBot worker is connected, the controller MUST report no active game sessions and SHALL return an explicit unavailable response for warehouse snapshots.

#### Scenario: Warehouse snapshot request without worker
- **GIVEN** an account is configured but no snapshot provider exists
- **WHEN** a client requests its warehouse data
- **THEN** HTTP 503 is returned, rather than empty or invented resource totals

### Requirement: Read-only entry point
The first API release MUST NOT offer game-login, background-task dispatch, or state-changing game operations.

#### Scenario: Status request
- **WHEN** an operator calls the API health endpoint
- **THEN** it reports read-only mode and zero connected workers without contacting Ikariam

### Requirement: Versioned bearer-protected read-only API
Daedalus SHALL offer versioned HTTP endpoints for account metadata and engine capabilities, with access controlled by a minimum 32-character bearer token.

#### Scenario: Authorization denied
- **GIVEN** a read-only Daedalus server
- **WHEN** a client omits or submits an invalid bearer token
- **THEN** the account/capability resource is denied without exposing private data

### Requirement: Safe local binding
The initial server MUST listen on loopback only and MUST NOT start any game worker.

#### Scenario: Server started with public interface
- **WHEN** the operator specifies `--host 0.0.0.0`
- **THEN** startup fails before the HTTP server is opened

### Requirement: Explicit unavailable warehouse data
The API MUST return HTTP 503 when no authenticated snapshot provider is available.

#### Scenario: Account without a worker
- **GIVEN** a valid configured account and no game session
- **WHEN** its warehouses are requested
- **THEN** the server reports unavailable, not a zero-value or stale snapshot

### Requirement: Read-only account session status
An authenticated client SHALL be able to query a configured account's nonsecret session state, and an unauthorized client SHALL receive no such state.

#### Scenario: Authentication assistance needed
- **GIVEN** a coordinator has marked an account as needs_assistance
- **WHEN** an authorized desktop client requests the account session endpoint
- **THEN** it receives needs_assistance without receiving credentials or session cookies

### Requirement: Session reads cannot start workers
The controller MUST NOT launch an engine worker, start a game login, or transition account state in response to a read-only status request.

#### Scenario: Account state is queried without a worker
- **WHEN** a client requests account status before any worker is connected
- **THEN** it receives not_connected and no game or IPC action is sent

### Requirement: Desktop bearer tokens use protected transport
The desktop SHALL refuse to send an API bearer token over plaintext HTTP to a non-loopback address.

#### Scenario: User enters remote HTTP URL
- **WHEN** the user enters `http://example.org` with an API token
- **THEN** the client refuses the connection before sending any request

### Requirement: Remote errors do not leak credentials
The desktop MUST sanitize connection and API errors and SHALL NOT print response bodies or bearer tokens in log or exception messages.

#### Scenario: Server includes a secret in an error body
- **GIVEN** a remote server responds with a private token in the body
- **WHEN** a request fails
- **THEN** the UI displays a generic status error without the token

### Requirement: Explicit read-only attachment to an existing engine
The backend SHALL expose optional bearer-protected GET endpoints for already-connected IkaBot account identities and their city lists only when the operator explicitly enables the existing-session IPC bridge.

#### Scenario: The backend starts with default options
- **GIVEN** the controller has a configured account but no explicit IPC attachment
- **WHEN** a desktop client requests connected engine sessions or cities
- **THEN** it receives HTTP 503 and the backend does not start a game session

### Requirement: Only configured accounts are revealed
The controller MUST filter IPC session identities to the enabled accounts in its own metadata configuration.

#### Scenario: An engine process contains other game accounts
- **GIVEN** the IPC worker lists unrelated player identities
- **WHEN** an authorized desktop requests connected accounts
- **THEN** only configured account IDs are returned

### Requirement: Controller IPC access is constrained to local read operations
The IPC transport MUST restrict calls to a fixed read-action allowlist, require a protected loopback discovery descriptor, and reject malformed credentials, stale owner processes and oversized replies.

#### Scenario: A client attempts task launch using the read bridge
- **WHEN** a requester invokes start_task using the read-only IPC connector
- **THEN** the connector refuses the action before opening a network connection

### Requirement: Task mutations require explicit server opt-in
Daedalus SHALL keep task launch/stop disabled by default, and SHALL only offer
mutation operations after the operator enables an existing-session task-control
mode in a loopback-bound, bearer-protected backend.

#### Scenario: Default backend receives a task request
- **GIVEN** a default Daedalus controller with an account configured
- **WHEN** an authorized client submits a task-start request
- **THEN** it receives HTTP 503 and no engine operation is invoked

### Requirement: Backend validates account scope and built-in operations
Task API requests MUST reference configured account identities and packaged
built-in background tasks, with bounded JSON configs and UUID4 request IDs.

#### Scenario: An interactive-only menu operation is requested
- **WHEN** an authenticated client submits a menu-only operation as a task
- **THEN** the API rejects it without forwarding it to IkaBot IPC

### Requirement: Task execution is explicitly opted in and bearer-protected
The controller MUST deny task POST requests unless its operator enabled controlled task dispatch, and MUST require the same bearer authentication as all other account endpoints.

#### Scenario: Default read-only backend
- **WHEN** a user submits a task-start HTTP request without the task-control feature flag
- **THEN** the API returns unavailable without any IPC operation

### Requirement: Validated account-scoped task lifecycle
The task API SHALL accept only known background tasks, secret-free JSON parameter objects, explicit user confirmation and unique request IDs, and SHALL expose managed-task list/stop endpoints.

#### Scenario: Valid authorized task start
- **GIVEN** an enabled account has an already-authenticated engine session and no conflicting owner
- **WHEN** a confirmed, validated task request arrives
- **THEN** the engine launches it through its native task interface and the backend returns its managed task ID

### Requirement: Opt-in protected account metadata editor
The API MUST reject configuration mutations unless the operator explicitly enables editing mode, presents the bearer token, confirms the intended operation and supplies the current configuration revision.

#### Scenario: Concurrent metadata change
- **GIVEN** the metadata file has changed since the editor loaded its generation
- **WHEN** the stale editor submits its changes
- **THEN** the server returns a conflict and does not overwrite the newer config

#### Scenario: Disabled account editing mode
- **WHEN** a client attempts to PUT account metadata to a read-only or task-control server
- **THEN** no write is performed and the endpoint reports editing unavailable

### Requirement: Scoped authenticated manual assistance

The API SHALL require bearer authorization for account-scoped assistance status and explicit one-use confirmation. It MUST NOT allow public clients to create tickets, start game login, provide authentication material or mark an engine session authenticated.

#### Scenario: Stale, duplicate or cross-account ticket
- **WHEN** an operator submits a stale, duplicate or different account's ticket
- **THEN** the API SHALL refuse approval without changing authentication state

#### Scenario: Disabled broker
- **WHEN** a backend has no trusted assistance broker
- **THEN** confirmation SHALL be unavailable and no browser/game operation SHALL occur

### Requirement: Explicit synthetic demonstration backend

The controller SHALL provide a clearly marked, operator-opted-in synthetic demo with sample account identities, cities and warehouse resource reports. The demo SHALL keep the standard authenticated API transport and SHALL identify synthetic content in machine-readable responses.

#### Scenario: Synthetic warehouse view
- **WHEN** a bearer-authorized demo client requests warehouse resources
- **THEN** the controller SHALL return clearly synthetic account-specific sample values with zero distinct from unknown and MUST NOT contact a game session

#### Scenario: Default backend startup
- **WHEN** the controller starts without explicit demo opt-in
- **THEN** it SHALL NOT load synthetic accounts or claim to show genuine reports from unavailable game sessions

### Requirement: Operator-confirmed monitoring and protected assistance notifications

The controller SHALL expose session-monitoring attachment only when explicitly enabled with existing-session task control, SHALL require bearer authorization and exact explicit `confirmed=true` before attaching a lease, and SHALL return only bounded nonsecret assistance ticket summaries. The API MUST NOT accept or distribute Gameforge credentials or session cookies.

#### Scenario: Unauthenticated monitoring command
- **WHEN** a remote client requests monitoring without bearer authorization or consent
- **THEN** the backend SHALL reject it without IPC or game network interaction

#### Scenario: Read pending assistance
- **GIVEN** one or more currently waiting lease-bound assistance tickets
- **WHEN** an authenticated desktop reads pending assistance
- **THEN** it receives only fixed reason, state, account and opaque ticket ID, with no secrets or HTML

### Requirement: Cookie-only worker bootstrap is a separate explicit opt-in
The `serve` command SHALL require an account metadata file, an existing-session IPC connector, an exact saved account ID and an explicit read-only network confirmation before starting any saved-cookie worker. The default API MUST NOT bootstrap an authenticated worker.

#### Scenario: Missing confirmation
- **WHEN** the operator omits the saved-worker network confirmation
- **THEN** CLI setup fails before accessing a saved session

### Requirement: Task controls adopt only the exact authenticated worker lease
An opted-in TaskController SHALL accept the same in-process authoritative authenticated account lease and protected identity-validated IPC endpoint. It MUST NOT acquire a second lease, replay prior tasks or accept a foreign owner's lease.

#### Scenario: Local saved worker has authenticated
- **GIVEN** task control was independently enabled
- **WHEN** the worker holds a verified account lease and IPC identity validation succeeds
- **THEN** task control may use that existing lease for separately confirmed built-in task operations

### Requirement: Bearer-authenticated client-sealed login vault
The controller SHALL accept and return only account-scoped AES-GCM opaque
login envelopes, never a plaintext Gameforge password. Persisted envelopes
MUST use the protected credential store and require a verified account email
binding before writes. Unavailable secrets MUST fail closed.

#### Scenario: Client retrieves a saved login
- **GIVEN** an authorized Mac has a retained Keychain vault key
- **WHEN** it retrieves the account's envelope
- **THEN** the server returns ciphertext only, decryptable only under the
  exact backend origin/account/world identity on the originating Mac

#### Scenario: Account list has protected email binding
- **GIVEN** an independently verified email binding in the protected store
- **WHEN** a bearer-authorized client requests accounts
- **THEN** that email may be returned for account identity display without
  exposing a password, raw cookie or secret key

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

### Requirement: Remaining operation parity and acceptance gate
The controller and both clients SHALL complete the outstanding reviewed operation contracts and account-specific workflows recorded in the preceding implementation matrix. Missing or unsupported options SHALL stay explicitly unavailable rather than become raw execution paths.

#### Scenario: A missing option is requested
- **WHEN** an operator selects a workflow that lacks an authoritative adapter or required native controls
- **THEN** dispatch remains unavailable until the adapter and its verification are implemented

#### Scenario: Full parity release is requested
- **WHEN** release acceptance is evaluated
- **THEN** every original criterion has verified evidence or an explicitly approved protected alternative, and required CI and owner-operated acceptance are complete

### Requirement: Reviewed multi-city military deployment
Supported owned-city deployment SHALL support a single origin or all other owned origins and ground, fleet or combined categories. A reviewed plan SHALL identify all covered routes, account for shared transport capacity once, and revalidate each route before dispatch.

#### Scenario: Shared capacity is insufficient
- **WHEN** aggregate ground cargo exceeds observed available transport capacity
- **THEN** no deployment ticket is issued

#### Scenario: A route becomes stale
- **WHEN** a reviewed route changes before its submission
- **THEN** remaining submissions stop and previously submitted routes are not automatically retried or rolled back

### Requirement: Reviewed multi-city worker assignments
Worker assignment SHALL support selected owned cities and both production projects, with authoritative per-city and per-project observations. The reviewed operation SHALL revalidate each assignment before a single non-retried submission.

#### Scenario: A worker assignment changes after approval
- **WHEN** the city, project or observed slider state differs from the reviewed plan
- **THEN** execution stops before submitting that changed assignment and remaining assignments are not retried automatically

### Requirement: Reviewed recruitment rounds and repetitions
The controller SHALL expose bounded ordered recruitment rounds and repeat cycles across selected owned cities. Each reviewed plan SHALL contain actual per-city unit identities and costs and SHALL require an account-scoped launch ticket. The worker SHALL revalidate the reviewed data and current resources before submitting each round once.

#### Scenario: A later training round is uncertain
- **WHEN** a submitted round cannot be observed in the training queue or the reviewed inventory changes
- **THEN** later rounds stop and are not automatically replayed

### Requirement: Reviewed construction supply
The controller SHALL support optional owned-city suppliers, bounded exact shortages, optional rounded cargo, trade ships or freighters, and explicit supply-only or supply-then-build execution. It SHALL expose source allocation, remaining shortages and observed fleet and storage capacity. A supplied construction job SHALL NOT be launched from raw configuration or automatically replayed after interruption.

#### Scenario: Supply is insufficient
- **WHEN** the selected sources or destination storage cannot cover the required shortage, or the fleet is unavailable
- **THEN** no launch ticket is issued

#### Scenario: A shipment outcome is uncertain
- **WHEN** a reviewed supply dispatch cannot be confirmed
- **THEN** subsequent construction is not attempted and the job requires manual reconciliation

#### Scenario: Supplies are dispatched
- **WHEN** a combined plan has dispatched its exact cargo
- **THEN** the worker verifies sufficient destination stock and the reviewed construction state before upgrades

### Requirement: Conditional transport delivery model
A shipment review MAY model delivery of all loads using the observed port and fleet parameters when the entire fleet is available, the single route has verified owned-city storage for all cargo and the timing observation is complete. The clients SHALL state the exclusive-fleet, symmetric-return and unchanged-loading assumptions and MUST NOT present the estimate as a guaranteed arrival. Missing observations and concurrent or multiple routes MUST NOT produce a fabricated combined arrival time.

#### Scenario: The reviewed cargo becomes unavailable
- **WHEN** source identity or stock changes between route selection and reservation
- **THEN** the worker stops before reserving or sending the changed cargo

#### Scenario: Multiple loads can be modeled
- **WHEN** a single owned route has a complete timing observation, sufficient storage and the whole fleet available
- **THEN** the review displays a conditional final delivery calculation including intervening return journeys and the last partial load

### Requirement: Exact research advisor choices
The authenticated academy inventory SHALL include a bounded projection of available study choices when the upstream research advisor can be observed. Both native clients SHALL expose a named study selection separately from experiments. The worker SHALL revalidate the exact current advisor entry before launch and before the single non-retried study submission. Missing or changed observations MUST NOT cause an alternate study or experiment to execute.

#### Scenario: Study availability changes
- **WHEN** the selected advisor entry no longer matches the reviewed name and research type
- **THEN** the worker rejects the selection without a study mutation

### Requirement: Reviewed fixed tavern servings
Both clients SHALL expose one-time fixed-percent tavern servings separately from equilibrium schedules. Each selected tavern SHALL have a verified serving-option observation and exact named current/target consumption review. The worker SHALL revalidate all selected rows before mutation, recheck each current row immediately before non-retried submission, and observe the new serving level before proceeding.

#### Scenario: The reviewed serving changes
- **WHEN** an observed serving option or current level differs from the reviewed draft
- **THEN** the worker stops without substituting another target

### Requirement: Verified island monitoring scope
Both clients SHALL allow explicit all-owned island monitoring or selected verified owned/external coordinates. A failed lookup SHALL invalidate its previously selected external entry. The controller SHALL reject malformed coordinates and arbitrary island identifiers; the worker SHALL resolve and confirm the exact coordinates again.

#### Scenario: An external island lookup fails
- **WHEN** an external coordinate cannot be verified
- **THEN** the client does not add it to the review or silently broaden the intended selection

### Requirement: Private aggregate map report export
Managed world scans SHALL store only bounded aggregate island observations in an identity-bound private report store, with opaque server-owned identifiers. Authenticated clients SHALL list completed reports and validate each bounded page before exporting a complete CSV. Raw player names, account identifiers from game responses, filesystem paths and unprojected game objects MUST NOT be exported. Local legacy dumps remain protected local.

#### Scenario: A report is requested for another identity
- **WHEN** the selected authenticated account does not own the report
- **THEN** the worker rejects access without revealing the other account or its report data

#### Scenario: A report page is inconsistent
- **WHEN** metadata, offsets, count or unique island identities do not agree across pages
- **THEN** no completed export is offered

#### Scenario: The scan radius is zero
- **WHEN** the approved region radius is zero
- **THEN** the scan covers only the selected center coordinate

### Requirement: Reviewed reward, distribution and trade operations

The controller SHALL obtain bounded account-scoped daily advisor, exact distribution or market observations before issuing a short-lived operation-specific launch ticket. Both native clients SHALL independently validate the reviewed quantities, scope and applicable cost or storage observations and MAY queue separately reviewed accounts. A ticket SHALL NOT authorize another account or operation. Generic launch SHALL reject these operations. The worker SHALL reject a changed distribution allocation or changed market quote before the affected submission. A reviewed listing SHALL NOT overwrite existing listings. Observations SHALL NOT be presented as guaranteed future rewards or proof of game-side execution.

#### Scenario: Independent multi-account review
- **WHEN** each selected account has its own valid reviewed ticket
- **THEN** the batch dispatches only those reviewed configurations with independent receipts

#### Scenario: A quote or allocation changes
- **WHEN** the worker finds a changed reviewed quote or distribution allocation
- **THEN** the worker stops rather than substituting a different transaction

### Requirement: Account-attested policy reviews
Research, tavern, miracle, shrine and workshop native workflows SHALL issue account-scoped, expiring review tickets using existing authenticated inventory observations and strict typed drafts. Both clients SHALL independently check the selected scope and relevant observed choices, state or targets. Independent reviewed batches SHALL preserve account-specific configurations and receipts. Generic launch SHALL NOT bypass the reviewed endpoints. Current observations SHALL NOT be presented as guarantees of future eligibility, cost or successful game execution.

#### Scenario: A selected workshop or academy is unavailable
- **WHEN** the current authenticated inventory does not contain the reviewed selection or its eligible target
- **THEN** the controller rejects the review rather than substituting another city or option

### Requirement: Reviewed recurring operation scopes

Consolidation, recurring transport, donation, island monitoring, aggregate reports and the existing human-controlled fortress mission workflow SHALL require independent account-bound launch reviews. Transport SHALL verify current owned-city stock, free storage, selected fleet observations and exact external recipient identity where applicable. Donation SHALL verify selected city identity and stock. Island monitoring SHALL verify selected coordinates or the observed all-owned scope. Map review SHALL verify report storage availability and aggregate-only output. Fortress review SHALL preserve mandatory human challenge stop. Current observations MUST NOT be represented as guaranteed future cargo, donation, availability or completion.

#### Scenario: A selected account scope is invalid
- **WHEN** a requested city, external recipient, island or fortress is not verified for the current account
- **THEN** no launch ticket is issued

#### Scenario: An operator queues multiple accounts
- **WHEN** each account is independently reviewed
- **THEN** each launch uses its own expiring ticket and durable request identifier without sharing another account's configuration

### Requirement: Military read failure and observation contract
The authenticated account-scoped military and ship-movements endpoints SHALL return bounded, source-backed observations for the exact existing session, with verified city membership and observation timestamps. They SHALL return a sanitized unavailable result when an observation cannot be verified, rather than invent zero counts or start a game login or order. Backend diagnostics SHALL identify the failing military read and configured account scope using nonsecret error categories without exposing raw engine exceptions, cookies, tokens or game HTML.

#### Scenario: Successful empty movements versus unavailable inventory
- **WHEN** an authenticated movement read succeeds with no movements, or a military read fails
- **THEN** the successful empty result is distinguishable from a failed read, and the latter returns HTTP 503 with a military-specific safe error and backend warning

#### Scenario: Production read-only acceptance
- **WHEN** an authorized operator validates the deployed military feature using an existing authenticated account
- **THEN** actual owned cities and unit counts are observed through the API, the movements endpoint is checked, and a subsequent read verifies that the worker remains available; no game orders are issued
- **AND** public CI uses offline synthetic fixtures only

### Requirement: Fill an owned city's warehouse for one resource
The controller SHALL offer a one-time, account-scoped transfer of one selected resource from all other owned cities into a chosen owned destination. The reviewed allocation SHALL NOT exceed observed free storage less observed inbound cargo. The worker SHALL check fresh stock, destination identity, storage and inbound cargo before each submission, stop on ambiguous cargo or outcome, and MUST NOT automatically replay interrupted work. The clients SHALL show quantities by source and the overall storage budget, and distinguish observations from guaranteed arrival capacity.

#### Scenario: Incoming cargo consumes warehouse space
- **WHEN** a destination has current free space and already incoming cargo
- **THEN** the available allocation is reduced by the incoming amount, and all reviewed source quantities together fit within that allocation

#### Scenario: Storage becomes unavailable during execution
- **WHEN** fresh observations cannot support a reviewed load
- **THEN** the worker stops or reduces that load within the reviewed limit without exceeding the observed remaining budget

#### Scenario: A warehouse preview cannot be verified
- **WHEN** the selected warehouse, source stock, incoming cargo or fleet observation is unavailable
- **THEN** the clients show a bounded nonsecret failure reason and no launch is authorized; a pending preview is visibly distinguished from a completed review

#### Scenario: Native cookie worker already owns the authenticated account
- **WHEN** an existing controller-local worker holds the exact authenticated lease and protected IPC verifies its identity
- **THEN** the controller adopts that lease before reserving dispatch instead of attempting a second acquisition; failed pre-dispatch ownership checks SHALL NOT create an unconfirmed engine receipt

#### Scenario: A managed warehouse child cannot be registered
- **WHEN** process registration fails before execution
- **THEN** the child SHALL NOT perform a shipment and the controller MUST NOT replay an ambiguous request

#### Scenario: Reviewed cookie-only transport
- **WHEN** a reviewed warehouse task executes on a cookie-only worker
- **THEN** the existing IkaBot sender SHALL attest the current player and use bounded same-world nonredirecting requests, and SHALL NOT automatically replay an uncertain transport POST

#### Scenario: Live acceptance through the existing authorized API
- **WHEN** a trusted host operator prepares a warehouse review
- **THEN** the operator runner SHALL retain the review privately and require the exact explicit request confirmation before a single launch attempt; it MUST NOT equate a launch receipt with delivery

#### Scenario: A managed transfer fails or waits for ships
- **WHEN** the warehouse worker is running or exits before its reviewed cargo is confirmed
- **THEN** the controller SHALL expose a bounded execution stage and separately observed submitted and advisor-verified quantities, and the clients MUST NOT equate worker launch or exit with arrival

#### Scenario: Transport feedback commands are reordered or rejected
- **WHEN** the game returns a reviewed transport response
- **THEN** the worker SHALL classify named feedback independently of command ordering, distinguish rejection from unconfirmed response, verify selected source context before submission, and MUST NOT count unknown outcomes as successful or replay them automatically.

#### Scenario: Shared upstream shipment implementation
- **WHEN** a reviewed warehouse allocation is executed
- **THEN** the worker SHALL normalize the allocation through the existing IkaBot sendResources preparation, use the shared route executor and sender, and enforce warehouse-specific capacity and incoming-cargo rules through an internal policy rather than a separate transport loop

#### Scenario: Verified cookie worker uses the common sender
- **WHEN** the shared sender submits a transport on an already verified cookie-only session
- **THEN** the standard Session.post interface SHALL preserve the upstream transport form, require the exact selected source and a fresh token, and perform one bounded submission without login or replay; contradictory responses MUST remain unconfirmed

#### Scenario: Reviewed shipment exhausts available vessels
- **WHEN** a verified load occupies all available vessels and reviewed cargo remains
- **THEN** the shared upstream waitForArrival mechanism SHALL use its original military-advisor AJAX request through the protected cookie session, await the next fleet event, recheck available vessels, and continue the same reviewed allocation only when ships are available

#### Scenario: Resource Transport Manager waits for vessels
- **WHEN** a recurring consolidation or distribution shipment requires available vessels
- **THEN** it SHALL use the same shared upstream fleet-wait helper as ordinary shipments and warehouse filling before acquiring its shipping lock; the shared route executor SHALL recheck fleet availability before sending

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

### Requirement: Minimize divergence from upstream operation implementation
Daedalus SHALL retain upstream game request construction and shared operation helpers as the source of truth. Native reviews SHALL supply validated arguments to the same operation functions or extracted original request builders. Cookie-session compatibility SHALL be isolated at the existing session boundary and SHALL NOT admit arbitrary mutation parameters through read-only forms. Intentional engine deviations MUST have a documented rationale and regression tests.

#### Scenario: Equivalent CLI and reviewed request
- **WHEN** the interactive CLI and native reviewed adapter execute the same supported building, layout, deployment or market selection operation
- **THEN** the underlying request form SHALL match the original upstream payload; the reviewed caller SHALL retain account, stale-plan and no-replay protection

#### Scenario: Upstream preserved helper changes
- **WHEN** a protected upstream helper differs from the recorded merged upstream baseline
- **THEN** the regression check SHALL flag the change for explicit review rather than silently accepting a rewritten game algorithm

### Requirement: Exact revision release verification
A released backend, web client and Mac package SHALL identify their verified compatible source revisions. The project SHALL retain incomplete automated and manual acceptance evidence separately. Manual owner acceptance MAY be deferred but MUST NOT be recorded as passed.

#### Scenario: A required build has not succeeded
- **WHEN** the matching Mac packaging or required CI has not succeeded
- **THEN** the release is not represented as verified and an older artifact is not substituted
