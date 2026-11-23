# Desktop Client

## Purpose
Extend the existing native PySide6 GUI to expose every supported engine operation.

## Requirements

### Requirement: Comprehensive task controls
The desktop SHALL expose supported task types through discoverable categories, configuration editors, validation, progress, and error states.

#### Scenario: New registered engine task
- **GIVEN** an engine task has a compatible schema
- **WHEN** the GUI loads the backend task registry
- **THEN** the GUI can present an actionable configuration without terminal keystroke automation

### Requirement: Common local and remote behavior
The GUI MUST use the same API contract in local and remote modes.

#### Scenario: Switching between local and remote
- **WHEN** the user changes backend connection
- **THEN** account status, snapshots and task configuration remain accessible through the same client flows

### Requirement: Native Fluent desktop control panel
Daedalus SHALL provide an installable PySide6 Fluent desktop with distinct Accounts, Operations, Warehouses, Log and Connection views.

#### Scenario: Desktop opens before any backend exists
- **GIVEN** the native UI is installed
- **WHEN** a user launches `daedalus-desktop` without configured accounts or a live server
- **THEN** the window opens without a game login and offers a backend connection form

### Requirement: Existing warehouse reporting controls
The GUI SHALL preserve the unsecured 220K resource filter and provide CSV/JSON export without converting missing resources to zero.

#### Scenario: Warehouse snapshots contain unknown fields
- **GIVEN** the backend returns missing resource amounts
- **WHEN** a user loads and exports the warehouse table
- **THEN** those fields remain unknown rather than being displayed as zero

### Requirement: UI does not block during HTTP requests
The desktop MUST perform backend network requests off the Qt GUI thread.

#### Scenario: Remote backend is unreachable
- **WHEN** an API connection fails or times out
- **THEN** the UI displays a sanitized error without freezing or exposing the bearer token

### Requirement: No premature task controls
The first native UI MUST show engine operations only as a read-only inventory until task validation and exclusive worker dispatch are implemented.

#### Scenario: CLI support exists but no account worker is connected
- **WHEN** the user opens the Operations page
- **THEN** operations are discoverable and cannot be executed from the UI

### Requirement: Reproducible native macOS preview
Daedalus SHALL provide a macOS application bundle built directly from a checked-out source revision and a named desktop entry point.

#### Scenario: CI preview build
- **GIVEN** a clean source checkout with no account credentials
- **WHEN** the macOS packaging job runs
- **THEN** it produces an identifiable Daedalus.app archive without running Ikariam, modifying /Applications, or loading account sessions

### Requirement: Preview signing is not production notarization
Mac packaging SHALL distinguish local ad-hoc signing from a developer-signed and Apple-notarized release.

#### Scenario: User obtains a CI preview artifact
- **WHEN** the user downloads the app artifact
- **THEN** documentation explains that it is a preview and may be blocked by macOS Gatekeeper without developer notarization

### Requirement: Direct-download macOS preview release assets

After a verified macOS preview build on the trusted default branch, Daedalus
SHALL publish the DMG **directly as a GitHub prerelease asset** rather than
requiring users to download an Actions-generated ZIP archive. Each prerelease
SHALL identify its exact source revision and include a file checksum. The
release-publishing job SHALL run only for the default branch, after macOS
bundle and mounted-DMG validation succeeds, with write permissions unavailable
to pull-request build jobs. The app SHALL be accurately labeled as ad-hoc
signed and not notarized; the direct download MUST NOT be described as a
Gatekeeper workaround.

#### Scenario: Main-branch macOS build passes validation
- **GIVEN** a trusted main-branch commit with a successful macOS packaging job
- **WHEN** its DMG is verified and publishing begins
- **THEN** a named public prerelease exposes the original `.dmg` as a direct
  download with no Actions ZIP wrapper
- **AND** its tag, release notes and SHA-256 checksum identify the build

#### Scenario: Pull-request build completes
- **WHEN** an unmerged pull request completes its macOS build
- **THEN** no public release is created and the job has no release-write permission

#### Scenario: User installs an unsigned development preview
- **WHEN** the user opens the downloaded DMG and copies its app
- **THEN** documentation explains that unnotarized apps may still require
  macOS first-launch approval, independently of the download container

### Requirement: BlindBase-compatible macOS preview installation

The Daedalus preview disk image SHALL reproduce BlindBase's HFS+ disk-image
layout, including an Applications shortcut and first-run documentation for
app-specific quarantine removal. To reduce manual work without claiming
automatic Gatekeeper bypass, the DMG SHALL additionally include an explicit
user-operated, signature-checking installer that copies Daedalus into the
user's Applications directory and removes `com.apple.quarantine` only from
that verified copy. CI SHALL exercise this flow with synthetic quarantine and
check the integrity of the mounted DMG.

#### Scenario: Operator chooses BlindBase's drag-and-drop installation
- **WHEN** the operator opens a downloaded DMG
- **THEN** the mounted volume shows Daedalus.app, an Applications shortcut,
  and a readme documenting the exact `xattr -cr` first-install step
- **AND** the DMG performs no automatic execution

#### Scenario: Operator uses the explicit installer
- **GIVEN** a correctly signed preview of the expected Daedalus bundle
- **WHEN** the operator runs the included installer from the mounted DMG
- **THEN** the app is copied into the user's Applications directory
- **AND** only that copy's quarantine flag is removed after verification
- **AND** no machine-wide Gatekeeper setting is changed

#### Scenario: Packaged app fails integrity verification
- **WHEN** the included installer encounters a bundle with invalid signing
  or an unexpected bundle identity
- **THEN** it refuses the installation and does not clear quarantine

### Requirement: Native desktop can inspect attached engine sessions without account secrets
The desktop SHALL show whether configured accounts match authenticated existing IkaBot sessions, obtained only after an explicit user request, without exposing engine authentication credentials or account emails.

#### Scenario: Operator checks existing session attachment
- **WHEN** the operator clicks Check IkaBot sessions
- **THEN** the Accounts view reports attached/not attached without launching a game login or displaying credentials

### Requirement: Connected warehouse view preserves export semantics
The native warehouse view SHALL display real typed snapshots from an existing authenticated session when available while preserving the unsecured-resource filter and zero/unknown distinction.

#### Scenario: Backend does not have an authenticated engine session
- **WHEN** the operator requests a warehouse snapshot
- **THEN** the desktop displays a sanitized unavailable error and does not fabricate a resource report

### Requirement: Native GUI task controls require confirmation
The desktop SHALL offer a Tasks interface with a configured account, a built-in
background task selector, a bounded JSON configuration editor, and explicit
operator confirmation before sending a mutating request.

#### Scenario: Operator selects task start
- **WHEN** the operator chooses a task for a particular world/player
- **THEN** the UI presents a confirmation identifying that account and task
- **AND** it sends the request only after confirmation

### Requirement: Disabled backend cannot trigger tasks from GUI
The native Tasks page MUST remain disabled until a connected backend confirms
that explicit task control is enabled.

#### Scenario: GUI connects to a read-only controller
- **WHEN** the backend reports `enabled: false`
- **THEN** the Tasks page cannot launch or stop game tasks

### Requirement: Managed task status and targeted stop are available
The desktop SHALL display task PID, operation, state and start timestamp for
tasks explicitly launched through Daedalus, and SHALL request confirmation
before stopping a selected running task.

#### Scenario: Operator stops one running managed task
- **WHEN** a running task is selected and the operator confirms stopping it
- **THEN** the backend requests termination only of that tracked task

### Requirement: Native task creation requires user confirmation
The Fluent GUI SHALL provide a discoverable Tasks page with a generic JSON task config editor, and MUST require an explicit authorization checkbox and confirmation dialog before sending a game task request.

#### Scenario: User does not confirm
- **WHEN** the user opens Tasks but leaves confirmation unchecked
- **THEN** no task-launch network request is made

### Requirement: Desktop can inspect and stop managed tasks
The GUI SHALL display the engine task lifecycle, and MUST use managed task IDs instead of arbitrary PIDs for stopping and reconciliation operations.

#### Scenario: Operator stops an existing Daedalus-managed child
- **GIVEN** a managed task appears in the task view
- **WHEN** the operator selects and confirms Stop
- **THEN** the desktop sends an authenticated account-scoped stop request

### Requirement: Native island-grouped warehouse export
The native desktop SHALL let the operator choose island ordering and export a human-readable grouped text report without replacing CSV or JSON exports.

#### Scenario: Group warehouses in the desktop
- **GIVEN** authenticated warehouse snapshots contain two cities with the same validated island coordinates
- **WHEN** the operator enables island grouping
- **THEN** the table orders those cities together and a TXT export prints one island heading for both cities

#### Scenario: Backend snapshot lacks island metadata
- **GIVEN** an older read-only IPC worker reports no island coordinates
- **WHEN** the GUI loads its warehouse results
- **THEN** the page remains usable, unknown island values are displayed as unknown, and exports remain available

### Requirement: Opt-in secure desktop connection persistence
The desktop MUST store a bearer token persistently only upon user opt-in and through an operating-system credential provider; it MUST NOT store bearer tokens in ordinary settings or log them.

#### Scenario: User remembers backend connection
- **GIVEN** a protected backend URL and valid token
- **WHEN** the operator selects Remember connection and connects successfully
- **THEN** only its validated URL is written in owner-private settings and the token is stored in the OS keyring

#### Scenario: Credential provider missing
- **GIVEN** the operating system does not expose a keyring backend
- **WHEN** the user requests persistent authentication
- **THEN** the desktop warns without writing a plain-text token or blocking ordinary in-memory connection

### Requirement: User-directed reconnect and forget
The desktop SHALL expose an explicit reconnect action for an in-memory or saved backend identity and a way to forget saved credentials without automatically replaying tasks.

#### Scenario: Backend restarts
- **WHEN** the user requests Reconnect after a transient API failure
- **THEN** only health, account metadata and capability discovery are attempted; game tasks are not resumed or retried

#### Scenario: User forgets preferences
- **WHEN** the operator clicks Forget saved connection
- **THEN** the saved URL and matching keyring secret are deleted where available

### Requirement: Parameter-aware native task configuration
The desktop SHALL render per-task parameter controls derived from validated built-in engine capability metadata, including required status and primitive typing when safely identifiable.

#### Scenario: A task has an optional numeric parameter
- **GIVEN** the engine registry reports alertAttacks.minutes as an integer with a literal default
- **WHEN** the user selects alertAttacks in the native Tasks page
- **THEN** the GUI shows an integer field and can construct a JSON config with that value

#### Scenario: A complex task has nested parameters
- **GIVEN** the engine registry cannot infer a parameter type from a public signature
- **WHEN** the user selects that task
- **THEN** the GUI offers an explicitly JSON-typed form input plus the advanced JSON editor without guessing a game value

### Requirement: Explicit form review before task dispatch
The desktop MUST NOT launch a task using unreviewed form inputs, and must retain checkbox, confirmation dialog and backend validation for every game-state-changing request.

#### Scenario: A parameter form has edits that have not been applied
- **WHEN** the user clicks Start task after editing form fields without building/reviewing their JSON
- **THEN** the desktop refuses to emit the start action until the draft is reviewed

### Requirement: Native account metadata editor
The desktop SHALL let the user create, rename, enable, disable and remove account metadata using the protected local/remote API, without storing Gameforge login credentials.

#### Scenario: User confirms a new account record
- **GIVEN** account editing is enabled on the connected backend
- **WHEN** the operator validates and confirms a new world/player account row
- **THEN** the GUI sends only allowed metadata with the current generation and refreshes account views after success

#### Scenario: Backend editing disabled
- **WHEN** the desktop connects to a read-only or task-dispatch backend
- **THEN** metadata editing is disabled and account viewing remains available

### Requirement: Native confirmation of nonsecret manual login assistance

The desktop SHALL let operators inspect a selected account's nonsecret assistance status and SHALL demand separate affirmative consent to acknowledge a completed human step. It MUST NOT claim that such acknowledgment is worker authentication.

#### Scenario: User cancels or selects another account
- **WHEN** the operator cancels consent or changes the selected account
- **THEN** the client SHALL NOT approve the pending or stale ticket

#### Scenario: User approves the manual step
- **WHEN** the operator confirms a valid current ticket
- **THEN** the client SHALL warn that independent worker validation remains required before automation resumes

### Requirement: Unambiguous native synthetic demo labeling

The desktop SHALL label the connected backend, warehouse resources and window title as SYNTHETIC DEMO whenever the backend identifies itself as a demo. It SHALL NOT visually represent demo amounts as live game observations.

#### Scenario: Demo backend is connected
- **GIVEN** a demo backend with synthetic account fixtures
- **WHEN** the desktop completes the authenticated handshake
- **THEN** the connection and resource views SHALL visibly display a synthetic warning and task controls SHALL remain disabled

### Requirement: Native monitoring consent and nonsecret assistance notifications

The Accounts page SHALL offer an explicit monitor action only when the backend indicates that existing-session validation is enabled. The UI SHALL demand a separate confirmation before sending a monitoring request and SHALL show a bounded nonsecret notification for a new waiting assistance ticket without repeating the same notification.

#### Scenario: User cancels monitoring
- **WHEN** the user declines the dialog to monitor a selected account
- **THEN** the desktop SHALL send no monitoring request

#### Scenario: New expired-session ticket
- **WHEN** a connected monitored backend reports a waiting ticket
- **THEN** the desktop SHALL notify the operator without revealing a cookie, token, ticket ID or full game response, and SHALL NOT automatically replay a task

### Requirement: One-click native synthetic demo starts and stops a private temporary backend

The native Connection page SHALL provide an explicitly selected synthetic demo action that launches an isolated local fake backend, automatically connects the desktop through the existing bearer API, and visibly labels all displayed data as synthetic. It MUST NOT require the user to enter or paste an API bearer token for this demo, and SHALL stop its temporary server when the desktop closes.

#### Scenario: User clicks offline demo
- **WHEN** the user explicitly chooses Try offline demo
- **THEN** Daedalus SHALL start a synthetic-only backend on an ephemeral loopback port, connect using an in-memory bearer token and display fictional accounts/warehouses, never real game data

#### Scenario: User closes desktop
- **GIVEN** an embedded demo server is running
- **WHEN** the user closes the native window
- **THEN** its API client and local demo service SHALL be stopped without leaving a live game worker

### Requirement: Safe legacy account selection and multi-account reports
The native desktop SHALL let operators select accounts for **read-only**
warehouse reporting without modifying account enablement or starting tasks,
and SHALL retain backend-specific selections without storing credentials.

#### Scenario: Select multiple accounts for warehouse reports
- **GIVEN** two configured accounts and a connected read-only backend
- **WHEN** the operator selects them in Accounts and requests selected warehouses
- **THEN** the UI retrieves snapshots off the GUI thread using the existing API, combines identifiable account rows for export and never starts tasks

#### Scenario: One selected account cannot provide a snapshot
- **GIVEN** a multi-account report with one backend snapshot error
- **WHEN** the report finishes
- **THEN** successful rows remain usable, the unavailable account is labeled, and no missing values are silently converted to zero

#### Scenario: Operator switches backend connection
- **WHEN** a new backend handshake succeeds
- **THEN** previously loaded warehouse data is cleared and only that backend's private report selection is applied

### Requirement: Private local appearance and report preferences
The desktop SHALL support System/Light/Dark themes and warehouse filter and
island-grouping defaults without storing or importing game authentication data.

#### Scenario: Save local GUI preferences
- **WHEN** the operator changes appearance or reporting defaults
- **THEN** the settings are applied immediately and atomically persisted to an owner-private, versioned file with no game passwords, bearer tokens or cookies

#### Scenario: Stored GUI settings are unsafe or malformed
- **GIVEN** unexpected fields, unsafe permissions, a symlink or invalid settings
- **WHEN** the desktop starts
- **THEN** it uses safe local defaults and does not import untrusted settings or game credentials

### Requirement: Preserve island-grouped clipboard reporting
The native warehouse view SHALL support copying an island-grouped textual report
in addition to exporting TXT, CSV and JSON.

#### Scenario: Copy a grouped report
- **GIVEN** typed resource snapshots with validated island coordinates
- **WHEN** the operator uses Copy by island
- **THEN** the clipboard holds grouped human-readable text without converting unknown resource amounts to zero

### Requirement: Dedicated native Wine and Construction workflows
The desktop SHALL offer dedicated Wine and Construction pages as convenient
entry points to registered compatible background engine tasks. These pages
MUST reuse the generic Tasks page's typed forms, backend capability gating,
operator confirmations, task status and targeted stop/reconciliation safeguards.

#### Scenario: Wine and construction task discovery
- **GIVEN** a compatible backend advertises alertLowWine, constructionList and an interactive-only constructBuilding command
- **WHEN** the user opens the Wine or Construction page
- **THEN** the respective page offers only registered background tasks for that workflow, with their validated parameter inputs; interactive-only operations remain read-only

#### Scenario: Disabled task execution on dedicated pages
- **GIVEN** the backend has not opted into structured engine task dispatch
- **WHEN** an operator opens either dedicated page
- **THEN** neither page can start, stop or acknowledge a game task

#### Scenario: Authorized task dispatch from dedicated page
- **GIVEN** the backend has enabled a registered background task
- **WHEN** the operator reviews its configuration, checks authorization and confirms start
- **THEN** the page calls the same authenticated API and replay-safe dispatch as generic Tasks without creating an independent login or game worker

### Requirement: Guided account-first desktop automations

The native Mac desktop SHALL provide account-first navigation, quick access to warehouse and automation workflows, categorized searchable operation selection, and native typed parameter controls. Advanced JSON SHALL be optional. Every task start SHALL remain subject to a separate explicit user confirmation and independently validated backend readiness.

#### Scenario: User starts a supported automation without writing JSON

- **WHEN** a user chooses an authenticated account, selects a background automation, adjusts native controls, sees passing preflight, and confirms launch
- **THEN** the desktop sends a typed task configuration and one unique request ID through the authenticated API without requiring a handwritten JSON document

#### Scenario: User selects an unavailable or unconfirmed task

- **WHEN** task readiness fails or a prior task request remains unconfirmed
- **THEN** the Start control stays disabled and the desktop displays clear prerequisite or manual-reconciliation guidance from the authoritative backend's nonsecret read-only readiness result

### Requirement: Guided private SSH connection

The desktop SHALL offer a button to establish a local SSH tunnel using the user's existing trusted SSH host and identity, without passing credentials in SSH arguments. It SHALL retain advanced HTTPS/loopback URL connections and SHALL close owned tunnels when the application exits or switches backend.

#### Scenario: User has a trusted SSH host and saved API token

- **WHEN** the user chooses the secure SSH connection, their trusted SSH host is reachable, and the API accepts the keychain token
- **THEN** the app performs a private read-only handshake over local port forwarding without a manual Terminal command or a public backend binding

#### Scenario: SSH authentication fails

- **WHEN** the host key or SSH identity cannot be verified
- **THEN** the app fails with a sanitized connection error and does not disable host-key checking or expose the backend to the public network

### Requirement: Confirmed backend connection and masked token state

- **WHEN** the native client successfully completes an authenticated backend handshake
- **THEN** it SHALL show a Fluent success notification and persistent connected status
- **AND** the API token input SHALL display a masked configured-value indicator
  without retaining the actual bearer in the UI widget or writing it to logs
- **AND** reconnect SHALL reuse Keychain credentials only for the exact saved HTTPS
  origin; failure SHALL show a safe error and not a misleading success state

#### Scenario: Verified backend connection with saved token

- **GIVEN** a trusted backend origin and a valid token
- **WHEN** the client receives an authenticated connection handshake
- **THEN** the user sees a success notification and a masked token hint
- **AND** the token text is absent from the UI widget, logs and plaintext preferences

### Requirement: Default secure HTTPS and OS-Keychain reconnection

The native client SHALL prefer direct TLS-verified HTTPS as its primary connection workflow, without requiring an SSH tunnel on the user's Mac. After an authenticated connection, the default selected preference SHALL save the bearer only in the OS Keychain, associate it with the exact validated HTTPS origin, and automatically reconnect on subsequent launches. Explicit opt-out SHALL allow an ephemeral session. The client MUST NOT silently copy a token to a different hostname, log credentials, or save bearer tokens in plaintext.

#### Scenario: First authenticated HTTPS connection

- **WHEN** the user supplies a TLS-valid Daedalus HTTPS hostname and correct bearer, leaving secure saving selected
- **THEN** the app completes a read-only handshake and saves the token in the OS Keychain and the URL in owner-only settings, without any Mac SSH tunnel

#### Scenario: User relaunches the desktop

- **WHEN** an exact previously approved HTTPS origin and its token exist in the OS Keychain
- **THEN** the app reconnects on startup without reentering either value and without starting a game task

#### Scenario: Different endpoint or missing keychain credential

- **WHEN** the user selects an HTTPS origin other than the one whose bearer was saved, or the Keychain is unavailable
- **THEN** the client does not reuse the old secret or weaken TLS verification, and requests explicit credentials instead

### Requirement: Native Mac browser login is an explicit first-class GUI action

For an enabled selected account and a capable authenticated backend, the GUI SHALL offer **Sign in on this Mac**, open an off-the-record Gameforge HTTPS browser, allow human challenge completion, and prompt for explicit encrypted handoff approval. It SHALL not read passwords/MFA or write world session cookies to preferences, log output, local accounts files, or an ordinary API request. A disconnected, demo, or non-opted-in server SHALL disable this action.

#### Scenario: User selects an account
- **WHEN** the operator selects an enabled account on a capable HTTPS backend
- **THEN** one native Mac browser sign-in action is available without SSH/VNC instructions

#### Scenario: Native browser is cancelled
- **WHEN** login is cancelled or expires
- **THEN** the browser is destroyed, session handoff is discarded, and no game task is replayed

### Requirement: macOS preview bundles private browser runtime

The signed-preview build SHALL include the Qt WebEngine renderer helper and cryptography dependencies, with synthetic CI checks that do not access real Gameforge credentials.

#### Scenario: macOS preview build
- **WHEN** the native .app is built in CI
- **THEN** the app package includes Qt WebEngine modules and its process helper

### Requirement: Observable headless Gameforge authentication with visible failure recovery

The Mac desktop SHALL use the prior local `itshak/ikabot` warehouse-bot
authentication lifecycle instead of requiring manual browser login for every
account: first attempt to restore a matching unexpired saved world session;
otherwise log in through the Gameforge lobby in **headless Selenium Chrome**
using securely stored per-account credentials, select the matching game world,
and return only an exact-host secure world cookie to the existing one-time
encrypted server handoff. A visible Selenium Chrome window SHALL open on a
detected CAPTCHA or after a failed headless authentication attempt (including
changed login markup, rejected credentials or a page/world timeout), to allow
the user to complete or correct the login. A bounded headless attempt SHALL
leave time for the visible retry, which SHALL remain available until a valid
world session is found, the user cancels or the overall deadline expires.
The app MUST NOT solve or bypass CAPTCHA, fabricate authentication, ship
plaintext game secrets through the backend API or start/duplicate game tasks. If credentials are absent,
the user may supply them once and persist them to a macOS OS-keychain entry
bound to HTTPS backend origin, account ID and world.

#### Scenario: Valid saved session or headless login works

- **GIVEN** an account with an existing verified server session or exact-world
  saved legacy session, or correct stored Gameforge credentials
- **WHEN** the operator chooses All accounts warehouses or automatic login
- **THEN** accounts already authenticated skip login, missing sessions are
  restored or logged in headlessly, and no visible browser or password prompt
  appears when usable Keychain/legacy credentials already exist
- **AND** the server independently verifies world/player and worker ownership
  before any account is reported authenticated

#### Scenario: A real CAPTCHA appears

- **GIVEN** a headless Gameforge login reveals a visible CAPTCHA indicator
- **WHEN** Selenium detects the challenge
- **THEN** only that account opens temporary visible Chrome for the user
  to solve it, no automated CAPTCHA response is attempted, and Selenium
  continues world navigation after the challenge is removed
- **AND** cancellation, timeout or wrong player never authorizes a game task

#### Scenario: A non-CAPTCHA failure occurs

- **WHEN** Gameforge rejects credentials, Chrome fails, the game world
  mismatches, or a normal login times out without a detected challenge
- **THEN** the desktop reports the failure and opens one visible Chrome
  recovery attempt if the browser can start; the operator may correct
  authentication before the overall deadline expires
- **AND** no session is reported verified until an exact-host secure cookie
  passes independent backend player/world attestation

#### Scenario: Server rejects the headless world-cookie handoff

- **GIVEN** the isolated helper successfully restored or obtained an exact-world cookie,
  but the server rejects independent account validation or cookie binding
- **WHEN** the browser's encrypted handoff receives a rejected server receipt
- **THEN** the desktop SHALL NOT report a connected or verified account
- **AND** the client SHALL request a fresh one-use account-scoped challenge and
  attempt one visible-only Chrome login without replaying the rejected saved cookie
- **AND** a second server rejection, cancellation or inability to issue a fresh
  challenge SHALL terminate recovery without claiming success or launching game tasks

#### Scenario: Verified world cookie starts an independently checked worker

- **GIVEN** an explicitly approved Mac browser login with an exact server-verified world/player cookie and enabled cookie-only worker startup
- **WHEN** the backend stores the account-bound cookie in its OS keyring
- **THEN** it SHALL launch an isolated, account-scoped IkaBot child with no cookie, password or lobby token on its command line or environment
- **AND** the child SHALL independently revalidate world/player and expose its protected IPC before the backend reports an authenticated session or connected worker
- **AND** the client SHALL refresh authoritative Session and Worker columns and enable actual warehouse reporting only after verified worker attachment
- **AND** old task processes SHALL NOT be replayed by browser sign-in

#### Scenario: Verified world cookie is saved without an attached worker

- **WHEN** independent server verification returns a cookie-bound receipt but no
  dedicated game worker was reconnected
- **THEN** the desktop SHALL explicitly report "session verified and saved; worker
  not connected" instead of calling the account authenticated
- **AND** the final per-cohort outcome SHALL remain visible after sign-in completes,
  distinguishing saved sessions from independently connected workers
- **AND** the account's authoritative session/worker status SHALL remain unchanged
  until the server actually attaches and validates the game worker

#### Scenario: Actionable sanitized login failure diagnostics

- **WHEN** a browser login, backend challenge or one-use session handoff fails
- **THEN** the Activity page SHALL distinguish the reviewed failure category and
  the stage at which it happened, rather than showing a generic warning only
- **AND** neither the timeline nor technical diagnostics SHALL display plaintext
  passwords, secure cookies or unreviewed Gameforge/API response details

#### Scenario: Connected columns update immediately after verified browser receipt

- **WHEN** a browser handoff receives a server receipt confirming the exact account's new or recovered authenticated IPC worker
- **THEN** the Accounts Session and Worker columns for that identity SHALL become checked immediately, without waiting for all other accounts in the sign-in queue
- **AND** a subsequent authoritative backend refresh SHALL replace the optimistic presentation if the worker has since exited
- **AND** a cookie-bound-only receipt SHALL NOT mark either column connected

#### Scenario: Fluent notices are persistent and stack

- **WHEN** multiple login, backend, or automation notifications are emitted
- **THEN** Fluent notifications SHALL stack in the top right, remain independently closable, and persist at least one minute instead of disappearing after the default short timeout

#### Scenario: Registration tab must never receive saved credentials

- **WHEN** the Gameforge lobby presents sign-in and registration tabs
- **THEN** Selenium SHALL wait for asynchronously loaded tabs and select the sign-in tab by accessible identity or, with exactly two peers, by excluding the uniquely identified registration tab, and
  SHALL type only into one visible login form, never the form selected by
  blind tab index or a registration submit button
- **AND** when it cannot distinguish the form, it SHALL fail closed and offer
  human-visible recovery instead of submitting sensitive data to registration

#### Scenario: Visible Chrome does not repeatedly steal application focus

- **WHEN** a human-visible Selenium login remains pending or navigates to
  the selected game tab
- **THEN** polling SHALL avoid switching to every browser tab on each tick
  or repeatedly bringing Chrome to the foreground, while preserving
  CAPTCHA visibility, cancellation and world verification

#### Scenario: Disposable Chromium profile never invokes persistent Chrome Keychain

- **WHEN** a macOS Selenium browser starts for automated sign-in
- **THEN** it SHALL use a fresh owner-private profile with Chromium's mock
  Keychain only inside that disposable profile, and erase the profile on exit
- **AND** persisted Gameforge credentials, encryption keys and backend bearer
  SHALL continue to require genuine macOS OS-keychain protection
- **AND** a verified legacy world session SHALL be restored without reading
  Keychain credentials; redundant Keychain reads and vault resealing SHALL
  be avoided on other login paths

#### Scenario: Headless login telemetry and isolation

- **GIVEN** a headless Selenium sign-in is requested
- **WHEN** the isolated child starts, checks saved login, loads the lobby,
  submits credentials, waits for the world, falls back to visible Chrome,
  encounters an error or finishes
- **THEN** the GUI SHALL show sanitized timestamped stages in the primary
  Activity timeline and bounded technical diagnostics while the browser runs
- **AND** the child SHALL run outside the GUI event loop, support hard
  cancellation and never log passwords, cookies, full browser URLs or
  unreviewed subprocess output/exception details

#### Scenario: All-account warehouse run needs some logins

- **GIVEN** a selection of multiple enabled accounts with differing session
  states
- **WHEN** the operator clicks Warehouses All accounts or Selected accounts
- **THEN** the GUI authenticates missing accounts serially using the same
  headless Selenium flow and continues with a combined read-only report
  showing partial failures explicitly, retaining native printing, island
  grouping and export behavior; no game tasks start

#### Scenario: Legacy local warehouse credentials exist

- **WHEN** the operator selects an exact account alias whose previous
  owner-owned `~/.ikabot/config.ini` and `tokens.json` match its world
- **THEN** the Mac may read those source files for the scoped login,
  but it does not modify or upload them, guesses no account association,
  stores new Gameforge credentials only in macOS Keychain, and retains
  the server's existing independent identity attestation

### Requirement: Compact table-first native desktop
The desktop SHALL place tabular content above persistent explanatory text and SHALL NOT reserve a permanent detail/action panel beside the Accounts table. It MUST provide a compact Add account button and contextual editing commands.

#### Scenario: Account management in a compact window
- **GIVEN** a user opens Accounts at a typical Mac window size
- **WHEN** no account is selected
- **THEN** the table occupies the primary workspace
- **AND** Add account is a single action in the toolbar
- **AND** recovery and destructive actions are not displayed as a permanent large pane.

### Requirement: Familiar multi-account warehouse workflow
The desktop SHALL retain a first-class all-accounts warehouse action, a selected-subset action, per-account inspection, print and CSV/JSON/TXT exports without changing missing resources into zero.

#### Scenario: Combined report with unavailable accounts
- **WHEN** a user requests all configured accounts' warehouses
- **THEN** each account is queried under its existing session
- **AND** failed accounts remain identified separately
- **AND** the original table and export semantics remain available.

### Requirement: Progressive disclosure throughout the native client
The desktop SHALL default to short titles and compact task controls and SHALL retain expert details through explicit disclosure, tooltips and accessible labels without changing safety or backend confirmation requirements.

#### Scenario: User configures an automation
- **WHEN** a user opens Automations
- **THEN** the account and validated task selectors remain available without an expanded discovery gallery
- **AND** the gallery and advanced JSON remain available on request
- **AND** Start still requires backend readiness and explicit review.

### Requirement: Compact, understandable account identity and status
The Accounts table SHALL prefer the server-verified Gameforge email over
generic imported labels, render Russian world codes as a country flag plus
exact server number, and display enabled/session/worker states as accessible
status glyphs with explanatory tooltips. Unknown worker attachment MUST NOT
be displayed as a negative result. The GUI SHALL offer all-account encrypted
backup of previously saved Mac logins.

#### Scenario: Imported Russian account without a verified world name
- **GIVEN** an account on s58-ru with a verified email but no verified world name
- **WHEN** the Accounts view is rendered
- **THEN** the email and the Russian flag with S58 appear along with clear
  check/X/unknown status indicators
