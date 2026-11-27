# Implementation status and OpenSpec reconciliation

Last reviewed: **2026-11-26**, against merged desktop and beta baseline `f22f098` and final preparation work. The repository is preparing beta `0.1.0` (web SemVer `0.1.0`); stable release is **NOT TESTED / NOT APPROVED**.

## Current engineering backlog

**Active OpenSpec implementation changes:** [`finish-v010-engineering`](../openspec/changes/finish-v010-engineering/tasks.md) and [`add-production-workforce-management`](../openspec/changes/add-production-workforce-management/tasks.md). Six prior proposals were archived as superseded, not certified complete; all 122 previously unchecked tasks have a disposition. See [reconciliation and evidence](V010-RECONCILIATION.md), [permanent operation coverage](operation-coverage.json) and [owner-only acceptance](V010-OWNER-ACCEPTANCE.md) ([issue #60](https://github.com/itshak/Daedalus/issues/60)). Engineering closure does not waive stable release acceptance. E3 automated integration coverage, E4 recovery engineering and E5 automated UI QA are implemented; E1 remaining upstream compatibility, E2 deployment security and E6 release engineering remain open.

Merged revision `f22f098` has a published Mac preview DMG/checksum, successful native desktop, engine, package, web and security workflows. A Windows Python 3.12 post-merge test hit a cold Node subprocess timeout; the final preparation change extends that bounded test allowance and requires a fresh CI result. The live backend was healthy in a read-only check; its checkout had identical backend/engine source to main. Actual game-changing task effects, full reboot, live restoration and final authenticated UI acceptance remain unverified. No new production changes were performed for the consolidation.

### Implemented baseline

- 49 registered/catalogued operations: 33 native, 15 existing views, one protected-local cookie operation. Coverage is still partial; no full option-level or live acceptance claim.
- Native Mac and Next.js web interfaces, actual account/city selectors, independent typed reviews, receipt history, reviewed dispatch, multi-account read-only reports, protected administration and upstream-first integration.
- Warehouse filling uses shared upstream sendResources / fleet waits, bounded capacity and incoming cargo policy, protected cookie transport, reviewed receipts and offline multi-load regression tests. Real delivery remains an owner test.
- Recovery defaults on for enabled accounts on a properly configured monitored daemon, with persisted pause/disable, protected server credentials, verified rebind, 300-second grace and fenced safe-job restoration. New owned-city fixed cargo uses per-batch write-ahead receipts; unknown and unsupported work stays manual.
- PR #109 fixed protected military reads; owner confirmed Mac inventory. PR #110 added actual web troop/fleet tables, persistent navigation and a sortable/filterable warehouse dashboard with private 120-second online cache.

## Desktop sign-in observability and connection feedback (2026-11-22)

PR [#85](https://github.com/itshak/Daedalus/pull/85) updates the existing
isolated Mac headless Selenium login to open one visible Chrome recovery when
the headless authentication cannot complete, including non-CAPTCHA failures.
Sanitized browser stages now feed the primary Activity timeline and rotating
local diagnostics without exposing credentials or cookies. Verified backend
handshakes display Fluent success feedback; the token input retains only
a masked placeholder, not the secret itself. Offline synthetic tests cover
these behaviors; **real Gameforge login/CAPTCHA and visual Mac acceptance are
NOT TESTED / NOT APPROVED**, and remain in
[owner acceptance issue #60](https://github.com/itshak/Daedalus/issues/60).
This release does not certify any live automation or backend deployment.

## Archived implementation and superseded proposals

The following changes have implemented and archived OpenSpec requirements. The historical PR checks and local test evidence vary by change; do not interpret this table as live-game certification. Completed requirements and explicit supersession dispositions are recorded; their capability deltas are incorporated into `openspec/specs/`, and their proposals/designs/tasks remain available under `openspec/changes/archive/`:

| Change ID | Shipped capability | Original PR |
| --- | --- | --- |
| `unify-global-account-scope` | Persistent scoped web/native account context, scoped reads and reviewed-target invalidation; synthetic verification, no live acceptance | [#119](https://github.com/itshak/Daedalus/pull/119) |
| `apple-style-nextjs-web-control-center` | Web client and BFF baseline; outstanding engineering/owner items transferred; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-apple-style-nextjs-web-control-center/consolidation-record.md) |
| `delayed-session-reconnect-and-task-restoration` | Recovery and fixed-cargo baseline; outstanding safety verification transferred; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-delayed-session-reconnect-and-task-restoration/consolidation-record.md) |
| `fill-city-warehouse` | Shared upstream warehouse filling; owner delivery acceptance deferred; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-fill-city-warehouse/consolidation-record.md) |
| `native-automation-workflows` | Native editors, upstream integration and military read fixes; remaining options transferred; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-native-automation-workflows/consolidation-record.md) |
| `redesign-macos-desktop-experience` | Native Fluent redesign and Selenium baseline; automated QA and owner review separated; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-redesign-macos-desktop-experience/consolidation-record.md) |
| `verify-and-release-cross-platform-parity` | Release verification and operation coverage consolidated into successor; superseded, not fully accepted | [Disposition](../openspec/changes/archive/2026-11-26-verify-and-release-cross-platform-parity/consolidation-record.md) |
| `complete-cross-platform-automation-parity` | Reviewed native workflow baseline; unfinished original requirements retained in the consolidated successor; no live acceptance | [#97](https://github.com/itshak/Daedalus/pull/97) |
| `finish-cross-platform-operation-parity` | Delivered expanded reviewed operation workflows; detailed parity and release gates transferred to the consolidated successor | [#97](https://github.com/itshak/Daedalus/pull/97) |
| `observable-selenium-login-and-connection` | Visible Chrome recovery after headless failure, sanitized live Activity stages and Fluent backend-success/masked-token feedback | [#85](https://github.com/itshak/Daedalus/pull/85) |
| `persistent-login-identity-status` | Encrypted Mac-bound server login backups, protected email identities, Russian world flags and accessible account/session/worker status indicators | Pending PR for this change |
| `bootstrap-public-monorepo` | Clean open-source package, CI, OpenSpec, license and security boundaries | [Initial foundation](https://github.com/itshak/Daedalus/commits/main/) |
| `add-readonly-controller-api` | Credential-free account TOML, authenticated read-only API, warehouse parser | [#6](https://github.com/itshak/Daedalus/pull/6) |
| `integrate-upstream-cli-ipc` | Reviewed upstream experimental CLI/IPC plus PR #502/#511 fixes | [#7](https://github.com/itshak/Daedalus/pull/7) |
| `enforce-account-session-ownership` | Host-local world/player leases and authentication status states | [#8](https://github.com/itshak/Daedalus/pull/8) |
| `native-desktop-control-center` | Working native Fluent GUI preview and read-only API client | [#9](https://github.com/itshak/Daedalus/pull/9) |
| `package-native-macos-app` | CI-built, ad-hoc signed `Daedalus.app` preview artifact | [#10](https://github.com/itshak/Daedalus/pull/10) |
| `connect-existing-ipc` | Opt-in existing-session read-only IPC, city lookup and warehouse snapshots | [#12](https://github.com/itshak/Daedalus/pull/12) |
| `compact-native-desktop-ui` | Table-first Accounts with compact Add and context menu; original Ecobot warehouse semantics and smaller Overview, Automations, Settings, Activity and Connection | Compact native UI update |
| `enable-existing-session-tasks` | Explicit existing-session built-in task start/list/stop and native Tasks UI | [#15](https://github.com/itshak/Daedalus/pull/15) |
| `controlled-task-dispatch` | Restart-safe task request ledger, engine-side replay suppression, bounded task IDs and manual reconciliation | [#14](https://github.com/itshak/Daedalus/pull/14) |
| `warehouse-island-reports` | Sanitized island coordinates, native island ordering, TXT/CSV/JSON warehouse reports | [#18](https://github.com/itshak/Daedalus/pull/18) |
| `secure-connection-preferences` | Opt-in OS keyring bearer storage, private URL settings and manual reconnect | [#20](https://github.com/itshak/Daedalus/pull/20) |
| `native-task-parameter-forms` | Safe typed parameter discovery and reviewed native forms for 23 built-in background tasks, with advanced JSON fallback | [#22](https://github.com/itshak/Daedalus/pull/22) |
| `account-metadata-editor` | Separate opt-in, confirmed native metadata editing with private atomic persistence and active-lease checks | [#25](https://github.com/itshak/Daedalus/pull/25) |
| `assisted-auth-confirmation` | Nonsecret lease-bound human-step acknowledgment with worker-only verification, NOT Gameforge browser integration | [#27](https://github.com/itshak/Daedalus/pull/27) |
| `offline-desktop-demo` | Isolated synthetic Mac GUI/API sample mode with fake account/city/warehouse data and real game side effects blocked | [#29](https://github.com/itshak/Daedalus/pull/29) |
| `safe-saved-session-recovery` | Explicit lease-guarded OS-keyring-bound world cookie validation, no new lobby loginLink | [#31](https://github.com/itshak/Daedalus/pull/31) |
| `existing-session-recovery-monitor` | Opt-in verified in-memory session monitoring, nonsecret manual-assistance notifications, worker revalidation and no task replay | [#33](https://github.com/itshak/Daedalus/pull/33) |
| `private-world-cookie-handoff` | Local hidden-input world-cookie validation and OS keyring binding, no remote cookie transfer | [#35](https://github.com/itshak/Daedalus/pull/35) |
| `offline-readiness-doctor` | Accurate installed-preview status and isolated in-process synthetic API smoke without game access | [#38](https://github.com/itshak/Daedalus/pull/38) |
| `cookie-only-worker-bootstrap` | Explicit one-account saved-cookie-only worker with protected exclusive IPC and retained lease; no new login | [#41](https://github.com/itshak/Daedalus/pull/41) |
| `desktop-oneclick-synthetic` | Explicit temporary local synthetic API with automatic private desktop connection and deterministic cleanup; no game login | [#39](https://github.com/itshak/Daedalus/pull/39) |
| `migrate-native-desktop` | Audited nonsecret Fluent GUI parity: account editing/report selection, multi-account snapshots, dedicated Wine/Construction workflows, private appearance and grouped exports | [#52](https://github.com/itshak/Daedalus/pull/52) |
| `guided-automations-and-desktop-redesign` | Account-first native navigation, guided controls, task preflight/rejection safety, direct HTTPS + Mac Keychain auto-reconnect, optional advanced SSH fallback | [#56](https://github.com/itshak/Daedalus/pull/56) |
| `import-public-ikabot-engine` | Audited pinned public engine and six-file production source diff; safe bounded token API retries, noninteractive fail-fast and explicit rejected credential/auto-launch code | [#53](https://github.com/itshak/Daedalus/pull/53) |
| `unify-authentication` | Worker-verified, lease-held manual recovery and secure authentication protocol across several PRs | [#51](https://github.com/itshak/Daedalus/pull/51) |
| `native-mac-browser-login` | Ephemeral Mac WebEngine, encrypted one-time session transfer, independent server-side world/player attestation and idle worker rebind | [#57](https://github.com/itshak/Daedalus/pull/57) |
| `persist-headless-credentials` | Host-encrypted persistent credential collection, receipt reconciliation and service restart/startup-order regression | [#59](https://github.com/itshak/Daedalus/pull/59) |
| `validate-live-authentication` | Offline/field-preflight implementation archived; **unperformed owner-only acceptance is still open in [issue #60](https://github.com/itshak/Daedalus/issues/60)** | [archive record](https://github.com/itshak/Daedalus/tree/main/openspec/changes/archive/2026-11-19-validate-live-authentication) |

The archive folders retain historical task checkboxes. Superseded changes include explicit per-task disposition records; unchecked work is not silently marked complete. The outstanding manual gates were transferred
explicitly to [issue #60](https://github.com/itshak/Daedalus/issues/60),
without claiming they were performed.

## Existing-session read-only bridge (shipped)

The completed `connect-existing-ipc` change was merged through PR #12, verified in offline CI, and archived with its requirements added to the permanent capability specifications. A later owner-approved isolated field smoke verified one saved game identity and read-only city/warehouse IPC on a dedicated worker; it was not a production-wide certification.

## Experimental cookie-only worker bootstrap (merged; live validation pending)

PR #41 merged the opt-in single-account worker: it can start a dedicated IPC server from a previously saved and exactly verified world session, retain the account lease, and optionally share it with the existing task controller. The normative worker requirements were subsequently reconciled and archived in `cookie-only-worker-bootstrap`. It cannot initiate Gameforge login or CAPTCHA; one subsequent isolated saved-cookie live validation passed, while task execution and recovery acceptance remain pending. See [saved worker](SAVED-WORKER.md). This is not production readiness.

## Guided desktop and task safety improvements (2026-11-19, synthetic validation)

The reviewed implementation in PR #56 adds account-first Home navigation, simpler
Automations categories and native parameter widgets, server-side alerts
prerequisite checks, clear deterministic pre-launch rejection statuses, and
direct private-origin HTTPS, default macOS Keychain credential saving and
automatic saved-HTTPS reconnection. An opt-in Mac-owned SSH tunnel remains only
an advanced fallback; normal operation requires no SSH on the Mac.
The existing Gameforge cookie and Daedalus API bearer remain distinct;
notification webhooks and bot tokens are never accepted in task JSON.

The archived implementation change `guided-automations-and-desktop-redesign`
is separate from the remaining owner-dependent real-account acceptance gates. The owner has confirmed the live Mac warehouse path but has **not**
verified game task launch/stop, remote login recovery, reboot keyring
persistence or a production-wide cutover. Installing a new macOS CI preview
artifact is required to test redesigned native controls.

## Native Mac browser login implementation (archived 2026-11-19)

The completed `native-mac-browser-login` implementation now offers first-class **Sign in on this Mac**, a temporary off-record Qt WebEngine Gameforge browser, optional encrypted email binding, single-use account-bound X25519/AES-GCM cookie exchange over authenticated HTTPS, and server-side independent player verification. It preserves an idle dedicated worker's account lease and denies recovery for active or unconfirmed tasks. Synthetic offline API, engine, GUI, WebEngine cleanup and cryptography tests
passed, and PR #59's macOS packaging pipeline passed. The controlled daemon
restart and existing-account read-only warehouse checks succeeded without
dispatching a new game operation. **A physical host reboot, real Mac
Gameforge/MFA/CAPTCHA login, dedicated rebind, game task and production
approval remain unverified** in [issue #60](https://github.com/itshak/Daedalus/issues/60).
See [native Mac login](NATIVE-MAC-LOGIN.md).

## Secret-free deployment preflight (2026-11-19)

The operator can run `daedalus doctor --smoke --deployment-check` to obtain a
read-only ledger/keyring metadata audit. On the current Monjo host, the audit
originally reported one unresolved task receipt and no durable protected
keyring file. On 2026-11-19 the receipt was inspected and operator-reconciled,
and the independently verified Monjo cookie and email binding were migrated
to host-encrypted, reboot-persistent systemd credentials. A controlled Daedalus
service restart recovered Monjo (authenticated, seven warehouses, zero tasks)
and enabled native Mac login without VNC. Deployment metadata now shows a
clear task ledger and encrypted credential files. The **host reboot and owner
real-game acceptance** remain unverified. The isolated new-version
backend's encrypted browser challenge start/cancel workflow passed with
synthetic account metadata and **no** Gameforge network requests; this does
not replace owner-run Mac login, game task or reboot acceptance. The full
Mac-first plan lives in [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md).

## Current OpenSpec work and owner acceptance

The remaining v0.1.0 engineering work is tracked in `finish-v010-engineering`. The separate v0.1.1 proposal `unify-global-account-scope` is being implemented and verified; it does not authorize a production deployment. Owner-only game, physical-device and production approval checks remain deferred and unpassed in [V010-OWNER-ACCEPTANCE.md](V010-OWNER-ACCEPTANCE.md) and [issue #60](https://github.com/itshak/Daedalus/issues/60). The headless-first Selenium workflow allows one visible recovery for a detected challenge or a failed headless attempt; no automated challenge solving. See the archived redesign for historical visual plans.

## Opt-in account metadata editor (shipped)

The `account-metadata-editor` change adds a separate confirmed, bearer-protected metadata-only backend mode and native account edit controls. It persists only validated account identifiers, worlds, players, labels and enabled flags with an optimistic generation, owner-only atomic write and local identity-lease check. Editing is incompatible with task dispatch. It does not log into Gameforge or migrate any production bot.

PR #25 passed Linux, Windows, macOS Fluent UI, engine tests and ad-hoc macOS packaging CI and was merged on 2026-11-18. The normative requirements are archived in OpenSpec. See [account editing](ACCOUNT-EDITING.md).

## Manual authentication assistance acknowledgment (protocol shipped)

The archived `assisted-auth-confirmation` change adds a **nonsecret ticket/approval handshake** guarded by the trusted worker's host-local account lease. The desktop can display manual-help reasons and acknowledge a completed human step, but cannot mark an account authenticated, transfer browser cookies, launch Gameforge login or resume tasks. Only a trusted in-process worker can verify a session. The default API keeps the broker disabled; there is **no production worker adapter yet**. See [manual help protocol](AUTH-ASSISTANCE.md). PR #27 passed protected Linux/Windows/macOS checks and merged on 2026-11-18; the normative protocol requirements are archived. This milestone does not complete `unify-authentication`.

## Isolated synthetic Mac demo (shipped)

The archived `offline-desktop-demo` change adds a separately opted-in `daedalus serve --demo` preview with two fictional account identities and nonsecret sample cities/warehouses. The backend refuses real account files, IPC, task controls, login assistance brokers and account editing in this mode. The native window, connection and warehouse views are explicitly labeled **SYNTHETIC DEMO**; no Gameforge login or production data are used. A real loopback HTTP smoke test and the full offline Python tests passed. See [synthetic demo walkthrough](SYNTHETIC-DEMO.md). PR #29 passed Linux, Windows, macOS native Cocoa UI and ad-hoc preview packaging CI and merged on 2026-11-18; its canonical requirements are archived. This demo is not an authenticated game session.

## Safe saved-cookie validation (shipped)

The archived `safe-saved-session-recovery` change adds a strict, opt-in, cookie-only probe to the Daedalus-vendored engine, an OS-keyring binding for one saved IkaBot account, and an explicit, lease-guarded CLI read-only world validation. It never requests a new lobby login link, starts tasks or creates a persistent worker; this is **not full authentication recovery or production cutover**. PR #31 passed protected CI and was merged on 2026-11-18; requirements archived. See [safe recovery protocol](SAFE-COOKIE-RECOVERY.md).

## Existing-session recovery monitor (protocol shipped)

The archived existing-session-recovery-monitor change extends the optional existing-session controller with fixed read-only world validation, account-owner leases, automatic detection of lost sessions and human assistance notification/worker revalidation. No new Gameforge login, worker bootstrap, Selenium assistance or task replay occurs; only explicitly attached existing sessions are probed. See [existing-session monitoring](EXISTING-SESSION-MONITOR.md). PR #33 passed required protected CI and merged on 2026-11-18; the normative requirements are archived. Browser handoff, CAPTCHA and newly started workers remain unfinished.

## Private local browser-cookie handoff (shipped opt-in)

The archived private-world-cookie-handoff change adds an optional hidden terminal prompt to import and verify a browser-authenticated world cookie against an existing saved IkaBot user. The cookie is stored only in the OS keyring on the authoritative host and never sent through the controller API; failed verification does not replace the old binding. This is not Selenium browser login, remote cookie transport or a persistent game worker. See [private cookie handoff](PRIVATE-WORLD-COOKIE-HANDOFF.md). PR #35 passed protected CI and merged on 2026-11-18; canonical requirements are archived. Server-side player attestation and new worker bootstrap remain outstanding.

## Honest offline readiness check (shipped)

The archived `offline-readiness-doctor` change replaces outdated hardcoded CLI diagnostics with preview-accurate feature and optional-dependency reports, and adds an isolated in-process FastAPI synthetic smoke test. Live accounts, real game integration and production readiness are not claimed. PR #38 passed protected CI and merged on 2026-11-18; requirements archived. See [offline test readiness](TEST-READINESS.md).

## Verified recovery dispatch guard (internal, not a complete browser flow)

The trusted in-process existing-session monitor now provides a single-use post-recovery dispatch guard: explicit operator approval, the exact worker-verified recovery ticket, a fresh world validation, a new UUIDv4 request and a new secret-free task configuration are required. The approval is consumed before any potentially ambiguous IPC dispatch. A bearer-protected endpoint now exposes this narrowly scoped explicit new-task operation to a trusted desktop client; it does **not** create a browser login, replay prior task state, or complete the remaining `unify-authentication` recovery tasks. Real browser login, remote handoff, desktop approval UI and end-to-end account verification remain open.

## One-click native synthetic Mac demo (implementation archived)

The archived `desktop-oneclick-synthetic` change adds an explicit Connection-page action that starts a temporary loopback-only synthetic backend and connects with an in-memory token. Data stays fictional, task control is disabled and closing the app stops the demo. The full local regression run completed with 609 passing Python tests, 9 skipped, and 107 passing subtests; strict OpenSpec and isolated wheel build also passed. The protected native macOS packaging/smoke checks remain mandatory merge gates, not evidence of live Gameforge login. See [one-click demo](ONECLICK-DEMO.md).

## Existing-session integration architecture

The archived `connect-existing-ipc` change delivers an **opt-in read-only bridge** to compatible already-authenticated IkaBot sessions. It reads connected account identities, cities and warehouse amounts without Gameforge credential restoration. A separate explicitly enabled task-control interface can start and stop only managed background tasks. No part of this attachment creates a competing game login; new worker bootstrap and Selenium login/assistance remain open.

## Completed opt-in task-control milestones

PRs #15 and #14 deliver an opt-in, managed IkaBot task lifecycle for already-authenticated in-memory sessions. The engine owns each session; the controller never starts another game login. The native Tasks page requires a checkbox and separate confirmation, supplies a unique UUID4 request ID, and exposes managed-task IDs instead of arbitrary PIDs.

The controller durably records only safe request metadata and configuration hashes, while the engine independently suppresses duplicate UUID dispatches. Ambiguous timeouts are not automatically replayed; they must be inspected and explicitly reconciled. The engine validates built-in task identity, enforces a bounded active task count and terminates newly created children if process-list registration fails. All 17 required/optional CI checks for PR #14 succeeded, including the Mac preview build. Full local offline verification: 134 Daedalus tests and 299 engine tests, with 9 skipped and 107 engine subtests.

**Production limitation:** no real Gameforge account was used by these tests. An isolated-account integration run, secure authentication bootstrap and handoff, browser-assisted recovery, distributed coordination and supervised worker restarts remain necessary before any production cutover.

## Current source of truth

Normative capability requirements live in `openspec/specs/<capability>/spec.md`. Archived change deltas are historical evidence, **not separate competing specifications**. An active OpenSpec proposal describes only the changes that are still planned. The source code, `README.md` and `docs/` must agree with the current implementation.

## Branch protection

On 2026-11-18, `main` was protected for all contributors (including administrators): linear history, PR-only changes, conversation resolution, no force pushes/deletions, and six required status checks:

- Python 3.11 / ubuntu-latest
- OpenSpec strict validation
- Detect accidental credentials
- Engine unit tests / Python 3.11
- macOS Fluent UI / Python 3.11
- Build unsigned-preview Daedalus.app

This documents **code quality policy**, not any policy on an individual's choice to run third-party bots. No special account-ban ADR was added.

## Release and production status

The native Mac GUI has launched successfully, and GitHub Actions verifies
unsigned-preview macOS bundles. The app is not Apple-notarized. It now offers
headless-first Mac Gameforge login with visible fallback and encrypted exact-account session
handoff, plus independently attested saved-cookie bootstrap on the Linux
worker. Daedalus does not automate CAPTCHA/MFA; eligible monitored recovery uses protected credentials and independent verification.
The controlled host service restart and one existing account's authenticated
read-only warehouses passed. Real Mac browser recovery, live task trial,
dedicated rebind and whole-host reboot still need owner testing. No
production-wide cutover is approved (issue #60).


## Earlier local-browser prototype (historical, 2026-11-18)

The opt-in host-local Chromium recovery prototype remains documented in
[browser recovery](BROWSER-RECOVERY.md). It was superseded as the default UX
by native Mac WebEngine + encrypted HTTPS handoff in #57. An idle dedicated
worker can now validate a replacement world session under its existing lease;
it must still fail closed if active tasks, uncertainty or mismatched identity
are present. The real-world flow has not passed owner acceptance (issue #60).


## Authentication offline scope archived; live integration remains open

The `unify-authentication` and `native-mac-browser-login` archived implementation changes cover single-owner leases, Mac browser and encrypted HTTPS handoff, OS keyring, independent world/player verification and idle-only dedicated-worker recovery. They do **not** claim successful real Gameforge login/CAPTCHA, real-world dedicated rebind, task dispatch acceptance or production cutover. Those supervised tests remain open in
[owner acceptance issue #60](https://github.com/itshak/Daedalus/issues/60).
Archiving the implementation is not production authorization.

Offline headless Chromium verification on the development host: `tests/test_browser_recovery.py` **7 passed**, using intercepted synthetic pages; no Gameforge traffic.

## 2026-11-20: Account identity and encrypted login backup

The Accounts view now prioritizes verified Gameforge email addresses over
imported placeholder labels, formats officially identified Russian worlds with flag, name and server
number, and uses accessible check/X/unknown indicators for account enabling,
game sessions and IkaBot worker attachment. The login prompt uses verified
email from the server. Mac Keychain keeps local credentials and encrypts
opt-in backups for the persistent protected Linux store; the API never serves
plaintext passwords. A background action migrates previously saved Mac logins.
Accounts with no recoverable credentials still require one-time input.
The live deployment and actual Mac acceptance remain separately owner-controlled.
