# Implementation status and OpenSpec reconciliation

Last reviewed: **2026-11-18**. The public repository's default branch is `main`.

## Complete and archived

The following changes passed GitHub's offline Python/engine tests, source-security checks, package build, strict OpenSpec validation and relevant native macOS checks before being merged. Their task checklists are complete, their capability deltas are incorporated into `openspec/specs/`, and their proposals/designs/tasks remain available under `openspec/changes/archive/`:

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

The completed archive folders are dated `2026-11-18`. Their checkboxes reflect **observed** successful CI and prior merges, not projected work.

## Existing-session read-only bridge (shipped)

The completed `connect-existing-ipc` change was merged through PR #12, verified in offline CI, and archived with its requirements added to the permanent capability specifications. It has not been tested against any production Gameforge account; no existing account session was changed.

## Still active

The following umbrella changes have unfinished tasks and were deliberately **not archived**:

- `import-public-ikabot-engine`: the clean engine and experimental CLI plus existing-session task adapter are integrated; production authentication differences and durable worker recovery remain incomplete
- `unify-authentication`: the existing browser/Selenium login restoration has been inventoried, and host-local lease/state foundations exist; a secure handoff, manual CAPTCHA assistance and real worker recovery still require implementation and tests
- `migrate-native-desktop`: the user-confirmed native GUI, account/report/task pages, live snapshots through existing sessions and basic macOS packaging work; dedicated per-task parameter forms, island-grouped exports, secure optional preferences and full GUI parity remain incomplete

Do **not** mark these changes as entirely done, or claim real game automation is available, until their outstanding tests and features are delivered.

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

The native Mac GUI has been successfully launched by the project owner. GitHub Actions verified the ad-hoc-signed preview bundle and artifact upload. The app is not Apple-notarized. The backend currently does **not** bootstrap new authenticated game workers or provide Selenium handoff; it does support explicitly opted-in start/list/stop on existing sessions. No real production accounts have been migrated.
