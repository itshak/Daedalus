<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/png/daedalus-logo-dark-1600.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/brand/png/daedalus-logo-light-1600.png">
    <img src="assets/brand/png/daedalus-logo-light-1600.png" width="700" alt="Daedalus: golden sun and winged D emblem, with the DAEDALUS name beneath">
  </picture>

  <p><strong>Daedalus for Ikariam — open-source, desktop-first IkaBot control center</strong></p>

  <p>
    <a href="https://github.com/itshak/Daedalus/actions/workflows/ci.yml"><img alt="CI workflow" src="https://github.com/itshak/Daedalus/actions/workflows/ci.yml/badge.svg"></a>
    <a href="LICENSE"><img alt="GPL-3.0-only license" src="https://img.shields.io/badge/license-GPL--3.0--only-blue"></a>
    <img alt="Pre-alpha status" src="https://img.shields.io/badge/status-pre--alpha-orange">
  </p>
</div>

**Status: native desktop with opt-in existing-session task controls and separate protected account metadata editing.** Daedalus includes an adapted PySide6/Fluent GUI (Accounts, Warehouses, Operations, Tasks, Log and Connection), credential-free multi-account metadata, and a bearer-authenticated backend. By default the backend is read-only; an explicit `--enable-task-control` flag allows confirmed start/list/stop of built-in tasks on an **already-authenticated IkaBot game session**, without opening another login. The engine combines IkaBot 7.7.2 and experimental [upstream PR #499](https://github.com/Ikabot-Collective/ikabot/pull/499) (including #502 and #511), which is **not an official stable upstream release**. The Selenium browser-assisted login and durable worker supervisor still remain to be implemented.

Daedalus is an open-source, desktop-first control center intended to integrate the [IkaBot](https://github.com/Ikabot-Collective/ikabot) game automation engine with a multi-account backend and a native PySide6 desktop application.

**Project links:** [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security policy](SECURITY.md) · [Support](SUPPORT.md) · [Implementation status](docs/PROJECT-STATUS.md). This project is experimental and is not yet ready to replace an existing production bot installation.

## Principles

- **One game engine:** reuse public IkaBot task implementations instead of reproducing game operations.
- **One account session owner:** prevent competing logins and duplicate live workers.
- **Complete desktop control:** preserve and expand the existing Fluent/PySide6 interface.
- **Local or remote:** the same authenticated backend API works on a user's computer or a remote Linux server.
- **Authentication recovery:** retain existing Selenium-assisted login, saved cookies, manual login and CAPTCHA assistance; do not assume upstream email/password login works reliably.
- **Secure by default:** no live user credentials, tokens, cookies, browser profiles, or runtime files in source control or public CI.

## Development setup

Requires Python 3.11+ and, for OpenSpec, Node.js:

```bash
python -m pip install -e ".[dev]"
python -m pip install -e ./engine/ikabot pytest-mock
python -m pytest -q tests
python -m pytest -q engine/ikabot/tests/ikabot
python -m ruff check src tests scripts
daedalus --version
daedalus doctor
daedalus engine inventory
daedalus accounts list --config docs/examples/accounts.toml
```

The `engine inventory` command reads engine source files through the Python AST, listing actual IkaBot menu actions and background tasks in JSON. It **does not launch bots or execute tasks**. The upstream CLI/IPC proposal is included, and Daedalus now has an **opt-in existing-session-only read bridge** for city and warehouse data. The controller cannot create new authenticated game workers; already-authenticated compatible workers can run explicitly confirmed built-in tasks only in opt-in task mode.

See [brand assets and app icons](assets/brand/README.md), including light/dark SVG, macOS ICNS, Windows ICO, and web/mobile exports.

## Native Mac GUI preview

The current desktop reuses Fluent navigation, macOS titlebar treatment, Qt theme, scroll tables and thread-safe logging from our existing Mac GUI. It uses the Daedalus backend API for reports and, only when explicitly enabled, task operations. It is a **partial migration**, not a release-ready replacement for the existing scraper or bot control application.

```bash
python -m pip install -e ".[desktop]"
daedalus-desktop
```

Open **Connection**, enter the backend URL and the bearer token from the local backend (see below). Then explore **Accounts**, the 46-operation read-only **Operations** inventory, **Warehouses**, and the optional **Tasks** page. With a separately opted-in editing backend, the **Accounts** page also has confirmed metadata editing controls. The warehouse tab preserves the 220K unsecured-resource filter and CSV/JSON exports. With explicit `--connect-existing-ipc` backend opt-in, it can read real resources through a compatible **already-authenticated** IkaBot session; otherwise the API reports unavailable. The token input is masked and kept in memory, not written to application settings. Remote connections require HTTPS or a protected SSH loopback tunnel.

For UI tests, install `.[dev,desktop]`. On Linux use `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_desktop.py`; on macOS use `QT_QPA_PLATFORM=cocoa python -m pytest tests/test_desktop.py` because Fluent Widgets requires a native macOS window. A dedicated macOS GitHub Actions workflow verifies the Cocoa-backed native Qt controls. See [GUI migration scope](docs/GUI-MIGRATION.md).

**Mac .app preview:** On a Mac, install `.[desktop,macos-build]` and run `python packaging/build_macos_app.py --output-dir dist --adhoc-sign` to create `dist/Daedalus.app` without installing it. The CI build uploads an ad-hoc signed preview archive; it is **not notarized**. Details: [macOS packaging](docs/MACOS-BUILD.md).

## Synthetic Mac desktop demo (no live game session)

To explore the complete native connection/accounts/warehouse reporting and
export views without any real Ikariam account, start a **separately opted-in**
synthetic backend. It never opens a game login, reads private account files or
enables task mutations:

```bash
python -m pip install -e ".[server,desktop]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --demo
# In another terminal: daedalus-desktop
```

Connect the desktop to `http://127.0.0.1:8765` with the same generated
bearer token. The window, Connection and Warehouses pages display
**SYNTHETIC DEMO** to distinguish sample accounts and resources from real
game observations. Demo mode rejects real account files, IPC connections,
task execution and metadata editing. See [synthetic Mac demo walkthrough](docs/SYNTHETIC-DEMO.md).

## Read-only local API

The controller implements metadata, existing-session status, city lookup and optional warehouse reporting. With a second explicit task-control opt-in, it can also dispatch built-in background tasks to the same already-authenticated IkaBot process; it never creates a login. It reads account identities from a private TOML file and does **not** allow passwords, Gameforge tokens, cookies, or account email addresses in that file. Start from [the synthetic example](docs/examples/accounts.toml), saving your own metadata **outside the Git checkout** (default: `~/.config/daedalus/accounts.toml`).

Install the API extra and generate a secret before running it:

```bash
python -m pip install -e ".[server]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --host 127.0.0.1 --port 8765
```

With the server running, clients use `Authorization: Bearer <your-secret>` for `GET /api/v1/accounts`, `GET /api/v1/capabilities`, and `GET /api/v1/warehouses/{account_id}`. `GET /api/v1/health` returns minimal status without authentication. Without explicit existing-IPC integration (or a separately injected snapshot provider), warehouse queries return HTTP 503; **no fake resources are returned**. The server refuses external listening addresses; connect a remote desktop client through an authenticated SSH or private network tunnel. No password login, worker creation, task execution, or live Ikariam request is performed by **default startup**. Game task execution requires both `--connect-existing-ipc` and `--enable-task-control`, with an already-authenticated compatible engine session, plus operator confirmation in the GUI.

**Optional account metadata editor:** Start an editing-only backend with `daedalus serve --enable-account-editing`. The Accounts page can add/edit/enable/disable/remove secret-free account records, each requiring confirmation. It uses owner-only atomic TOML, optimistic revisions and account-lease checks. `--enable-account-editing` is incompatible with `--enable-task-control`; neither editing nor read-only startup performs game login. See [account editing setup and limitations](docs/ACCOUNT-EDITING.md).

**Optional existing-session bridge:** Start the backend with `--connect-existing-ipc --accounts-file ~/.config/daedalus/accounts.toml` on the same machine/user as a **compatible, already-running** IkaBot IPC server. The Accounts page can check engine attachment and Warehouses can fetch read-only snapshots. This path never creates another Gameforge login. See [the full existing-IPC requirements, precautions and testing instructions](docs/EXISTING-IPC.md). **Do not use the current production bot installation as a test worker.**

OpenSpec 1.13 is used for spec-driven changes:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
openspec list
```

See [AGENTS.md](AGENTS.md), [implementation and OpenSpec status](docs/PROJECT-STATUS.md), [architecture](docs/ARCHITECTURE.md), [migration policy](docs/MIGRATION.md), [upstream provenance](engine/UPSTREAM.md), and [security](docs/SECURITY.md). Normative capability requirements live in [openspec/specs](openspec/specs/); completed change records live in [openspec/changes/archive](openspec/changes/archive/).

## Optional task controls — explicit operator opt-in

With a compatible already-authenticated IkaBot engine process on the same host, run `daedalus serve --connect-existing-ipc --enable-task-control`. The native **Tasks** page offers a built-in background operation list, JSON configuration, explicit start/stop confirmation and status for Daedalus-managed child processes. **The default service has no task mutations.** Existing IkaBot tasks started outside Daedalus cannot be stopped from this page. This is not a substitute for the still-unfinished Selenium login assistant or task persistence. See the complete [task control setup, API and safeguards](docs/TASK-CONTROL.md).

## Account-session ownership groundwork

Daedalus includes a host-local OS file lock and authentication-status state machine to prevent duplicate world/player workers **on the same backend host**. The authenticated API reports nonsecret session states for each account. This is groundwork only: **no Gameforge login, browser handoff, or game worker is started** by these components. The lock is not distributed across multiple servers; assign each account to one authoritative backend. See [session ownership and limitations](docs/SESSION-OWNERSHIP.md).

## Safe saved-cookie validation (explicit opt-in; no new login)

Use `daedalus sessions bind-email ACCOUNT_ID` to associate an existing IkaBot saved-user email through the **OS keyring**, then `daedalus sessions probe-saved-cookies ACCOUNT_ID --confirm-read-only-network` to validate old world cookies under the host-local account lease without any lobby loginLink. This performs a genuine read-only world request only when explicitly confirmed; it **never creates or maintains an authenticated game worker**. Use a separate test account and stop unrelated sessions first. See [safe saved-cookie recovery](docs/SAFE-COOKIE-RECOVERY.md).

## Optional monitoring of verified existing IkaBot sessions

Use the --monitor-existing-sessions flag together with --connect-existing-ipc and --enable-task-control only against a compatible already-authenticated IkaBot session on the same host. In Accounts, explicitly confirm Monitor verified session for one account; the backend holds its own host-local lease and checks a fixed read-only world URL. If the session expires, new task starts are blocked and the native desktop receives a nonsecret manual-help notification. Only a trusted worker may validate again. No new login is created and tasks are never automatically replayed. See [existing-session monitoring](docs/EXISTING-SESSION-MONITOR.md).

## Local manual browser-cookie handoff (no remote secret transport)

For an existing IkaBot saved account, a separately authorized local operator can copy an already authenticated world cookie from their own browser and use the hidden terminal action -- daedalus sessions bind-world-cookie ACCOUNT_ID --confirm-read-only-network -- to verify the exact world/player and store it only in the OS keyring. The original browser/CAPTCHA login is completed manually; this does not create a new login, start IkaBot, update an already running worker or send cookies through the controller API. See [local browser-cookie handoff](docs/PRIVATE-WORLD-COOKIE-HANDOFF.md).

## Offline readiness check and synthetic API smoke

Run `daedalus doctor` to see installed preview capabilities and the dependencies actually present. The report marks live account status as not inspected, and does not claim new-worker bootstrap, automatic browser login or production readiness. Use `daedalus doctor --smoke` after installing server/client test dependencies to check the real API routes in-process with only fictional demo data, without Gameforge or an external TCP socket. See [offline readiness instructions](docs/TEST-READINESS.md).

## One-click synthetic Mac demo (no setup or game login)

In the native Connection page, click **Try offline demo — no game login**. Daedalus starts a private loopback-only synthetic backend, connects with an ephemeral in-memory token, shows clearly labeled fictional accounts/cities/resources, and stops the server when the app closes. Neither IkaBot cookies nor real account settings are used. See [native one-click synthetic demo](docs/ONECLICK-DEMO.md).

## Manual authentication assistance protocol (foundation only)

The repository includes a credential-free, lease-bound acknowledgment protocol for **future** trusted worker login assistance. In the native Accounts view, a selected account can request nonsecret assistance status and an explicit manual-step acknowledgment when a compatible trusted in-process broker is injected into the server. This action does **not** authenticate, transfer a cookie, bypass a CAPTCHA, start a login, or resume any game task. The normal CLI does not enable this broker until an actual supervised engine/browser integration is implemented. See [manual authentication assistance and limitations](docs/AUTH-ASSISTANCE.md).

## Candidate public engine CLI (after installing `./engine/ikabot`)

The vendored IkaBot **proposed** CLI supports native task flags such as `--task`, `--config`, `--batch` and `--cities`. To see the supported syntax without logging in, run:

```bash
python -m ikabot --help
```

Task execution requires an already-authenticated compatible IkaBot session and explicit operator opt-in. Test it in an isolated engine environment rather than restarting production accounts. The independent `daedalus engine inventory` command is read-only and reports the upstream CLI's presence separately from Daedalus's own dispatch readiness.

See [the precise upstream merge record](engine/UPSTREAM.md), [the archived OpenSpec CLI/IPC integration change](openspec/changes/archive/2026-11-18-integrate-upstream-cli-ipc/proposal.md) and [current implementation status](docs/PROJECT-STATUS.md).

## Existing-session-only bridge

Daedalus can now connect **read-only** to an already-running instance of the Daedalus-vendored IkaBot engine that supports the new restricted IPC actions. The **Accounts** view has a **Check IkaBot sessions** button, and **Warehouses** can read exact unsecured-resource totals. The backend never restores a game login for these requests; the connection is explicitly opted into with `daedalus serve --connect-existing-ipc`. Task start/stop is separately available behind `--enable-task-control`; the Selenium login assistant remains unfinished. Read [the bridge setup and limitations](docs/EXISTING-IPC.md).

## Repository organization

- `src/daedalus/`: application package, local/remote HTTP client, reporting utilities and authenticated read-only API
- `engine/ikabot/`: public MIT-licensed IkaBot 7.7.2 with proposed, unreleased PR #499 CLI/IPC code
- `server/`: future supervised account workers, task dispatcher, scheduler and policies; not implemented yet
- `src/daedalus/desktop/`: reviewed Fluent GUI with multi-account reports, private appearance preferences and opt-in task controls; remote recovery and live acceptance pending
- `openspec/`: normative specifications, architecture decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Vendored IkaBot is MIT-licensed; its original [license](engine/ikabot/LICENSE) and notices are preserved. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.

### Experimental saved-cookie worker

For explicitly authorized cookie-only startup of one existing authenticated
IkaBot world session (without lobby login), see
[the saved-worker guide](docs/SAVED-WORKER.md). This remains an experimental
path, not a replacement for interactive Gameforge authentication.

## OpenSpec and production scope

The normative, maintained requirements are in [OpenSpec capabilities](openspec/specs/), and completed milestones are preserved under [archived changes](openspec/changes/archive/). Active umbrella changes remain open while their unchecked tasks are genuinely unfinished; they are **not** silently marked complete. The detailed [status and remaining work](docs/PROJECT-STATUS.md) identifies those gaps.

The [saved-cookie worker](docs/SAVED-WORKER.md) is an explicitly opted-in, single-account bootstrap from **previously authenticated** cookies. It does not provide a fresh Gameforge login, browser/CAPTCHA handoff, unattended recovery or live-account certification. The [synthetic demo](docs/SYNTHETIC-DEMO.md) remains the safe first test.

Authentication recovery implementation and limitations: [Human browser recovery](docs/BROWSER-RECOVERY.md).
