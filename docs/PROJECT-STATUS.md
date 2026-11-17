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

The archive folders are dated `2026-11-18`. Their checkboxes reflect **observed** successful CI and prior merges, not projected work.

## Still active

The following umbrella changes have unfinished tasks and were deliberately **not archived**:

- `import-public-ikabot-engine`: the clean engine and experimental CLI are imported, but a validated controller-to-engine worker adapter, failure reconciliation and reviewed production authentication differences remain incomplete
- `unify-authentication`: the existing browser/Selenium login restoration has been inventoried, and host-local lease/state foundations exist; a secure handoff, manual CAPTCHA assistance and real worker recovery still require implementation and tests
- `migrate-native-desktop`: the user-confirmed GUI preview, API client, report filter and basic macOS packaging work; full legacy GUI parity, task workflow editors, island-grouped exports, secure optional preferences and live snapshot wiring remain incomplete

Do **not** mark these changes as entirely done, or claim real game automation is available, until their outstanding tests and features are delivered.

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

The native Mac GUI has been successfully launched by the project owner. GitHub Actions verified the ad-hoc-signed preview bundle and artifact upload. The app is not Apple-notarized. The backend currently does **not** start engine workers, provide secure Selenium session handoff, or support task dispatch, and no real production accounts have been migrated.
