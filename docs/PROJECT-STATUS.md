# Implementation status and OpenSpec reconciliation

Last reviewed: **2026-11-18**. The public repository's default branch is `main`.

## Complete and archived

The following changes have merged implementation and archived OpenSpec requirements. The historical PR checks and local test evidence vary by change; do not interpret this table as live-game certification. Their task checklists are complete, their capability deltas are incorporated into `openspec/specs/`, and their proposals/designs/tasks remain available under `openspec/changes/archive/`:

| Change ID | Shipped capability | Original PR |
| --- | --- | --- |
| `bootstrap-public-monorepo` | Clean open-source package, CI, OpenSpec, license and security boundaries | [Initial foundation](https://github.com/itshak/Daedalus/commits/main/) |
| `add-readonly-controller-api` | Credential-free account TOML, authenticated read-only API, warehouse parser | [#6](https://github.com/itshak/Daedalus/pull/6) |
| `integrate-upstream-cli-ipc` | Reviewed upstream experimental CLI/IPC plus PR #502/#511 fixes | [#7](https://github.com/itshak/Daedalus/pull/7) |
| `enforce-account-session-ownership` | Host-local world/player leases and authentication status states | [#8](https://github.com/itshak/Daedalus/pull/8) |
| `native-desktop-control-center` | Working native Fluent GUI preview and read-only API client | [#9](https://github.com/itshak/Daedalus/pull/9) |
| `package-native-macos-app` | CI-built, ad-hoc signed `Daedalus.app` preview artifact | [#10](https://github.com/itshak/Daedalus/pull/10) |
| `connect-existing-ipc` | Opt-in existing-session read-only IPC, city lookup and warehouse snapshots | [#12](https://github.com/itshak/Daedalus/pull/12) |
| `enable-existing-session-tasks` | Explicit existing-session built-in task start/list/stop and native Tasks UI | [#15](https://github.com/itshak/Daedalus/pull/15) |
| `controlled-task-dispatch` | Restart-safe task request ledger, engine-side replay suppression, bounded task IDs and manual reconciliation | [#14](https://github.com/itshak/Daedalus/pull/14) |
| `warehouse-island-reports` | Sanitized island coordinates, native island ordering, TXT/CSV/JSON warehouse reports | [#18](https://github.com/itshak/Daedalus/pull/18) |
| `secure-connection-preferences` | Opt-in OS keyring bearer storage, private URL settings and manual reconnect | [#20](https://github.com/itshak/Daedalus/pull/20) |
| `native-task-parameter-forms` | Safe typed parameter discovery and reviewed native forms for 23 built-in background tasks, with advanced JSON fallback | [#22](https://github.com/itshak/Daedalus/pull/22) |
| `account-metadata-editor` | Separate opt-in, confirmed native metadata editing with private atomic persistence and active-lease checks | [#25](https://github.com/itshak/Daedalus/pull/25) |
| `assisted-auth-confirmation` | Nonsecret lease-bound human-step acknowledgment with worker-only verification, NOT Gameforge browser integration | [#27](https://github.com/itshak/Daedalus/pull/27) |
| `offline-desktop-demo` | Isolated synthetic Mac GUI/API sample mode with fake account/city/warehouse data and real game side effects blocked | [#29](https://github.com/itshak/Daedalus/pull/29) |
| safe-saved-session-recovery | Explicit lease-guarded OS-keyring-bound world cookie validation, no new lobby loginLink | [#31](https://github.com/itshak/Daedalus/pull/31) |
| existing-session-recovery-monitor | Opt-in verified in-memory session monitoring, nonsecret manual-assistance notifications, worker revalidation and no task replay | [#33](https://github.com/itshak/Daedalus/pull/33) |
| private-world-cookie-handoff | Local hidden-input world-cookie validation and OS keyring binding, no remote cookie transfer | [#35](https://github.com/itshak/Daedalus/pull/35) |
| offline-readiness-doctor | Accurate installed-preview status and isolated in-process synthetic API smoke without game access | [#38](https://github.com/itshak/Daedalus/pull/38) |
| cookie-only-worker-bootstrap | Explicit one-account saved-cookie-only worker with protected exclusive IPC and retained lease; no new login | [#41](https://github.com/itshak/Daedalus/pull/41) |
| desktop-oneclick-synthetic | Explicit temporary local synthetic API with automatic private desktop connection and deterministic cleanup; no game login | [#39](https://github.com/itshak/Daedalus/pull/39) |

The completed archive folders are dated `2026-11-18`. Archive checkboxes reflect merged code and local validation; see individual PR checks for the latest protected CI state. No archive implies real-game production validation.

## Existing-session read-only bridge (shipped)

The completed `connect-existing-ipc` change was merged through PR #12, verified in offline CI, and archived with its requirements added to the permanent capability specifications. It has not been tested against any production Gameforge account; no existing account session was changed.

## Experimental cookie-only worker bootstrap (merged; live validation pending)

PR #41 merged the opt-in single-account worker: it can start a dedicated IPC server from a previously saved and exactly verified world session, retain the account lease, and optionally share it with the existing task controller. The normative worker requirements were subsequently reconciled and archived in `cookie-only-worker-bootstrap`. It cannot initiate Gameforge login or CAPTCHA, and no live account validation has been performed. See [saved worker](SAVED-WORKER.md). This is not production readiness.

## Still active

The following umbrella changes have unfinished tasks and were deliberately **not archived** (the legacy GUI source/license review is complete; full parity is not):

- `import-public-ikabot-engine`: the clean engine and experimental CLI plus existing-session task adapter are integrated; production authentication differences and durable worker recovery remain incomplete
- `unify-authentication`: the existing browser/Selenium login restoration has been inventoried, and host-local lease/state foundations exist; a secure handoff, manual CAPTCHA assistance and real worker recovery still require implementation and tests
- `migrate-native-desktop`: the user-confirmed native GUI, account/report/task pages, live snapshots through existing sessions and basic macOS packaging work; per-task parameter forms and island-grouped reports are delivered. The new opt-in metadata editor covers basic account create/edit/disable/remove, while full legacy parity and authenticated worker recovery remain incomplete.

Do **not** mark these changes as entirely done, or claim real game automation is available, until their outstanding tests and features are delivered.

### Remaining OpenSpec completion gates

As of the reviewed source and license audit, **6 unchecked tasks across 3 active umbrella changes** remain. This is the concrete backlog; none should be marked complete or archived on documentation alone.

| Active change | Remaining gate | Evidence needed before checking off |
| --- | --- | --- |
| `import-public-ikabot-engine` | Reconcile production authentication modifications with upstream without private material | File-by-file reviewed diff, explicit license/provenance and isolated engine regression tests |
| `migrate-native-desktop` | Finish advanced legacy GUI parity | Implemented UI workflows and native desktop regression tests, with no credential leakage |
| `unify-authentication` | Safe browser login and manual CAPTCHA assistance | User-authorized manual browser flow, explicit consent, safe secret handling and mocked failure tests |
| `unify-authentication` | Validated remote handoff or protected remote-browser fallback | Threat model, authenticated transport, host-local ownership and no secret exposure to controller |
| `unify-authentication` | Secure user-approved task resume after real browser recovery | Verified identity, replay protection, explicit per-task approval and crash/retry tests |
| `unify-authentication` | Complete end-to-end recovery verification | Offline failure matrix, secret scan, strict OpenSpec, protected CI and isolated-account validation |

The new `tests/test_openspec_hygiene.py` guard fails CI if an archived change contains an unchecked task, if a completed active change is left unarchived, if an active change is absent from this status document, or if a change's capability has no canonical specification. It enforces consistency; it does not implement the remaining features.


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

The native Mac GUI has been successfully launched by the project owner. GitHub Actions verified the ad-hoc-signed preview bundle and artifact upload. The app is not Apple-notarized. The backend can explicitly bootstrap **one** already-authenticated saved-cookie world session, but cannot perform new Gameforge lobby login, Selenium handoff, or unattended worker recovery. It supports separately opted-in start/list/stop on verified existing sessions. No real production accounts have been migrated.


## Authentication progress (2026-11-18)

The optional ephemeral human-operated Chromium login assistant is implemented in `src/daedalus/browser_recovery.py` and documented in [browser recovery](BROWSER-RECOVERY.md). It keeps world cookies out of the API and checks a matching engine session before keyring persistence. Host-local graphical remote-desktop fallback avoids copying session secrets across machines. Synthetic browser tests do not prove Gameforge compatibility. **A running worker cannot yet receive and validate a replacement world cookie in-place**, so the full `unify-authentication` proposal remains active until that secure engine-side handoff and offline regression tests are delivered. Do not mistake a verified cookie saved for future cookie-only startup for a recovered existing worker.
