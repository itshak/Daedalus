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

The completed archive folders are dated `2026-11-18`. Their checkboxes reflect **observed** successful CI and prior merges, not projected work.

## Read-only existing-session bridge (current feature milestone)

The completed `connect-existing-ipc` change was merged through PR #12, verified in offline CI, and archived with its requirements added to the permanent capability specifications. It has not been tested against any production Gameforge account; no existing account session was changed.

## Still active

The following umbrella changes have unfinished tasks and were deliberately **not archived**:

- `import-public-ikabot-engine`: the clean engine and experimental CLI plus existing-session task adapter are integrated; production authentication differences and durable worker recovery remain incomplete
- `unify-authentication`: the existing browser/Selenium login restoration has been inventoried, and host-local lease/state foundations exist; a secure handoff, manual CAPTCHA assistance and real worker recovery still require implementation and tests
- `migrate-native-desktop`: the user-confirmed native GUI, account/report/task pages, live snapshots through existing sessions and basic macOS packaging work; dedicated per-task parameter forms, secure optional preferences and account-editing parity remain incomplete. Island-grouped TXT reporting is being implemented in the warehouse-island-reports change.

Do **not** mark these changes as entirely done, or claim real game automation is available, until their outstanding tests and features are delivered.

## Current integration change

The archived `connect-existing-ipc` change delivers an **opt-in read-only bridge** to compatible already-authenticated IkaBot sessions. This reads connected account identities, cities and warehouse amounts without any Gameforge credential restoration. It is separate from the explicitly enabled task-control interface and does not create a competing game login. The full native GUI control and Selenium login/assistance work remain open.

## Completed opt-in task-control milestone

The archived `enable-existing-session-tasks` change adds opt-in built-in IkaBot task start/list/stop against existing in-memory authenticated accounts. The engine owns each session; the controller does not open a second login. Only tasks launched through this explicit Daedalus path can be stopped through its managed Process handles. The native Tasks page has a generic JSON config editor and requires confirmation for each mutation. The implementation passed all required GitHub CI, but **an actual isolated-account integration test remains necessary before production use**. Selenium login restoration and distributed session coordination remain separate unfinished changes.

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
