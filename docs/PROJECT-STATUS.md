# Implementation status and OpenSpec reconciliation

Last reviewed: **2026-11-19** (limited field smoke; acceptance still open). The public repository's default branch is `main`.

## Automatic recovery implementation (active OpenSpec; approval pending)

The `delayed-session-reconnect-and-task-restoration` change is **ACTIVE and PARTIALLY IMPLEMENTED**. It now includes an opt-in per-account 300-second grace timer, a private versioned SQLite desired-job and idempotent resume journal, exact-account encrypted server-side Gameforge lobby-token import, an isolated IkaBot engine recovery supervisor behind an explicit backend startup flag, a narrow verified safe-task allowlist, Mac and Next.js recovery controls and synthetic API/UI/session tests. Existing accounts are disabled by default and a new verified world/player worker is required before any restart.

**Not complete:** There is no verified unattended Gameforge live recovery yet; `alertAttacks`, self-funded native `constructionList` target plans, and recurring source-retained-stock `consolidateResources` / `resourceTransportManager` policies can reconcile after recovery. Fixed-quantity shipments remain manual until per-route delivery receipts establish what remains; older manual-class jobs must be reviewed once. Existing legacy task names/PIDs do not contain sufficient configuration for blind restoration. The source-code work is not a claim of production approval; the future owner-supervised browser takeover and task replay-prevention trial remain outstanding. The implementation change MUST stay active until its unchecked checklist and acceptance gates are resolved. See the [implementation guide](AUTOMATIC-RECOVERY.md), [OpenSpec tasks](../openspec/changes/delayed-session-reconnect-and-task-restoration/tasks.md) and [design](../openspec/changes/delayed-session-reconnect-and-task-restoration/design.md).

## Planned Apple-inspired Next.js web control center — PR #72

The `apple-style-nextjs-web-control-center` OpenSpec change is **ACTIVE, PLANNING ONLY, NOT IMPLEMENTED**. It proposes a responsive Apple-inspired Next.js/Refine/shadcn web application at `daedalus.tongrix.com`, with closed Supabase web authentication and a secure Vercel server-only gateway to the existing FastAPI/IkaBot controller. It includes an Apple design skill–based interaction and accessibility blueprint, web-safe feature-parity inventory, multi-account warehouse and automation controls, desktop-only Selenium login boundary and an entirely unchecked implementation checklist. No web build, provisioning, backend change, DNS, deployment, live task, visual acceptance or production cutover has been performed. Keep active until the implementation and owner-operated acceptance gates pass; see [proposal](../openspec/changes/apple-style-nextjs-web-control-center/proposal.md).

## Active native Mac redesign

The `redesign-macos-desktop-experience` OpenSpec change remains active while implementation work is completed incrementally. PR #63 merged the Fluent shell, first-class all-account warehouse reporting, selected-account task workflows and a macOS preview. The follow-up implementation consolidates three automation editors into one, adds Accounts master/detail, safe keyboard shortcuts, a filtered local Activity timeline, backend-grounded enum pickers, draft consent invalidation and duplicate-launch protection. Human macOS visual/VoiceOver walkthroughs and real-account acceptance are deferred to the owner and are **not** recorded as passing. Do not archive the redesign change until its remaining implementation tasks are reconciled.

The latest implementation work also adds capability-derived automation
discovery cards; account-selectable Running/History with opt-in expert IDs;
an Overview whose read-only summaries distinguish unobserved, successful and
unavailable snapshots; Settings controls for per-backend **all/selected**
warehouse reporting; contextual HTTPS/Keychain failures; and explicit
per-backend task/draft invalidation on origin change. Source-level Python
compilation and patch whitespace checks passed on the development server;
the PySide6-Fluent runtime, physical Mac layout/VoiceOver and live Gameforge
workflow have **not** been exercised in this branch. The redesign OpenSpec
remains active until reviewed build and UX gates are satisfied.

## Active native automation workspace — PR #68 (draft, unfinished)

The `native-automation-workflows` OpenSpec change is **ACTIVE and UNFINISHED**.
It implements category tabs, actual authenticated city pickers, a bounded read-only
IkaBot IPC/API for real owned-city building levels, a construction building table
with draft upgrade targets, and safe rejection of cross-account city/plan reuse.
Raw construction planner JSON is hidden from the normal UI, with expert import
retained for previously prepared engine plans. Resource distribution has native
resource/mode choices and source-backed participating-city multi-selection;
research and tavern management have account-bound city subsets. Daily reward collection has native wine/wood/luxury city destinations and verified favour-task choices.

The remaining implementation is substantial: IkaBot's authoritative, read-only
construction cost/shipment/ETA planner; native executable construction queue;
dedicated domain UI and verified game DTOs for the full IkaBot catalog;
per-account review previews and final Mac accessibility/visual acceptance.
**The current draft is NOT production-ready and MUST NOT be archived or merged
until the required engine planner, UI, contract tests and acceptance gates are
completed.** See [full UX feature audit](AUTOMATION-UX-AUDIT.md),
[design](../openspec/changes/native-automation-workflows/design.md) and
[remaining checklist](../openspec/changes/native-automation-workflows/tasks.md).

## Complete and archived

The following changes have implemented and archived OpenSpec requirements. The historical PR checks and local test evidence vary by change; do not interpret this table as live-game certification. Their task checklists are complete, their capability deltas are incorporated into `openspec/specs/`, and their proposals/designs/tasks remain available under `openspec/changes/archive/`:

| Change ID | Shipped capability | Original PR |
| --- | --- | --- |
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

The archive folders are dated `2026-11-18` and `2026-11-19`. Archive
checkboxes reflect completed implementation and local validation, not owner
real-game certification. The outstanding manual gates were transferred
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

**One OpenSpec implementation change is active:** `redesign-macos-desktop-experience`.
Its native Fluent UX work is in progress, with tested initial navigation, multi-account
warehouse reporting, selected-account task status/dispatch guards and contextual
settings. The full visual design, native Mac screenshots, task-specific forms,
accessibility audit and owner approval are **not complete** and the change is
not archived. The earlier `validate-live-authentication` was archived on
2026-11-19 after its seven implementation/preflight tasks were verified.
Its three former unchecked owner-only tasks were **transferred as unperformed** into
[owner acceptance issue #60](https://github.com/itshak/Daedalus/issues/60)
and [LIVE-ACCEPTANCE.md](LIVE-ACCEPTANCE.md), not marked passed or waived.

### Remaining owner-only acceptance gates — NOT TESTED / NOT APPROVED

| Owner gate | Evidence needed |
| --- | --- |
| Real Mac browser/MFA/CAPTCHA and encrypted world-cookie exchange | Authorized isolated-account evidence, server attestation and read-only comparison |
| Worker rebind/expiry/manual recovery and one explicit task trial | Same lease, no duplicate operation, observed game effect and stop |
| Host reboot durability and automatic HTTPS reconnect | Controlled full reboot under safe maintenance window, verified encrypted store |
| Release/cutover approval | Sanitized owner results for every gate, plus explicit owner decision |

The current implementation fails closed on unrecognized game-world player
markup and refuses uncertain/replayed task dispatch. Green CI (including
synthetic Playwright, Qt/Fluent, Linux/Windows/macOS, packaging and OpenSpec)
does not replace live acceptance. The OpenSpec hygiene regression checks
now allow an empty active-change set but continue to reject unchecked
archived tasks and require visible owner acceptance tracking.

## Headless-first Gameforge sign-in parity (implementation pending Mac acceptance)

The UI redesign now includes the local `itshak/ikabot` warehouse-bot
authentication sequence: headless Selenium Chrome login, exact-world
`tokens.json` restore, opt-in legacy `config.ini` alias migration,
account+world+HTTPS-origin macOS Keychain credentials, and a visible Chrome
window **only when a CAPTCHA is detected**. The Accounts page provides
single/all/selected sign-in; Warehouses All accounts refreshes missing
sessions before aggregating snapshots. Session handoff still uses the
existing one-time encrypted, exact-account server verification and cannot
start or replay a task. Offline Selenium and synthetic Qt tests exercise
the new coordinator without contacting Gameforge. **Live Mac login,
CAPTCHA, owner reboot and game-task acceptance remain unverified** in
[issue #60](https://github.com/itshak/Daedalus/issues/60). This OpenSpec
change remains active until remaining implementation and review gates close.

## Native Fluent desktop redesign (implementation in progress, 2026-11-19)

The active `redesign-macos-desktop-experience` change now has an account-aware
five-destination Fluent shell (Overview, Accounts, Warehouses, Automations, Activity),
distinct Connection and Settings icons, scrolled settings/account/task pages,
and consolidated Wine/Construction entry points in the Automations workspace.
Warehouses expose **All accounts** (one click), **Selected accounts** (custom picker)
and **This account**, preserving island grouping, the 220K filter, missing-vs-zero
semantics and grouped text/CSV/JSON exports. Automations can inspect running
statuses for all or selected accounts. Starting a task for selected accounts
requires an explicit review, checks each account before any dispatch, generates
a unique request per account and halts on the first uncertain receipt without
retrying. The backend remains the authority and no live operations were run by
the synthetic UI implementation.

This is an incremental implementation, not yet complete production/visual
acceptance. macOS preview/CI results and remaining tasks are tracked in the
open change; issue #60 separately tracks owner-only real-game approval.

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
**manual** Mac Gameforge browser login and encrypted exact-account session
handoff, plus independently attested saved-cookie bootstrap on the Linux
worker. Daedalus does not automate CAPTCHA/MFA or unattended account login.
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
