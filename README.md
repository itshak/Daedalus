# Daedalus for Ikariam

**Status: native desktop preview with opt-in controlled engine task execution.** Daedalus now includes an adapted PySide6/Fluent desktop shell with Accounts, Warehouses, Operations, Log and Connection pages, a credential-free local multi-account configuration format, an authenticated read-only API, and a task registry. The engine combines public IkaBot 7.7.2 with proposed [upstream PR #499](https://github.com/Ikabot-Collective/ikabot/pull/499) (including #502 and #511), which is **not an official stable upstream release**. The GUI can start/list/stop Daedalus-managed tasks **only after the backend operator explicitly enables task control and a compatible existing IkaBot session is already authenticated**. It cannot yet log in, complete browser-assisted authentication, or migrate live production workers.

Daedalus is an open-source, desktop-first control center intended to integrate the [IkaBot](https://github.com/Ikabot-Collective/ikabot) game automation engine with a multi-account backend and a native PySide6 desktop application.

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

The `engine inventory` command reads engine source files through the Python AST, listing actual IkaBot menu actions and background tasks in JSON. It **does not launch bots or execute tasks**. The upstream CLI/IPC proposal is included, and Daedalus now has an **opt-in existing-session-only read bridge** for city and warehouse data. The controller still cannot create authenticated workers or launch tasks.

## Native Mac GUI preview

The current desktop reuses the Fluent navigation, macOS titlebar treatment, Qt theme, scroll tables and thread-safe logging patterns from our existing Mac GUI, while replacing direct Selenium data fetching with the Daedalus read-only backend API. It is a **partial migration**, not a release-ready replacement for the existing scraper or bot control application.

```bash
python -m pip install -e ".[desktop]"
daedalus-desktop
```

Open **Connection**, enter the backend URL and the bearer token from the local backend (see below). Then explore **Accounts**, the 46-operation read-only **Operations** inventory, and **Warehouses**. The warehouse tab preserves the 220K unsecured-resource filter and CSV/JSON exports. With explicit `--connect-existing-ipc` backend opt-in, it can read real resources through a compatible **already-authenticated** IkaBot session; otherwise the API reports unavailable. The token input is masked and kept in memory, not written to application settings. Remote connections require HTTPS or a protected SSH loopback tunnel.

For UI tests, install `.[dev,desktop]`. On Linux use `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_desktop.py`; on macOS use `QT_QPA_PLATFORM=cocoa python -m pytest tests/test_desktop.py` because Fluent Widgets requires a native macOS window. A dedicated macOS GitHub Actions workflow verifies the Cocoa-backed native Qt controls. See [GUI migration scope](docs/GUI-MIGRATION.md).

**Mac .app preview:** On a Mac, install `.[desktop,macos-build]` and run `python packaging/build_macos_app.py --output-dir dist --adhoc-sign` to create `dist/Daedalus.app` without installing it. The CI build uploads an ad-hoc signed preview archive; it is **not notarized**. Details: [macOS packaging](docs/MACOS-BUILD.md).

## Optional engine task control

A fully separate, **opt-in** task controller is available for compatible already-authenticated IkaBot sessions. Start the backend with **both** `--connect-existing-ipc` and `--enable-task-control` on the engine host; it remains bound to loopback. The native **Tasks** view then offers task selection, JSON parameter editing, explicit authorization/confirmation, start/list/stop, and manual reconciliation of uncertain launches. A private SQLite request ledger prevents automatic replay across backend restarts; no task arguments or credentials are stored. Without the opt-in flag all game-task mutation endpoints return HTTP 503.

See [task-control setup, safety and API](docs/TASK-CONTROL.md). The existing game engine must already hold the correct logged-in world/player session. **Do not test by restarting or upgrading your current production bots.** Automated CI never contacts Gameforge.

## Read-only local API

The controller implements metadata, existing-session status, city lookup and optional warehouse reporting—not game task execution or login automation. It reads account identities from a private TOML file and does **not** allow passwords, Gameforge tokens, cookies, or account email addresses in that file. Start from [the synthetic example](docs/examples/accounts.toml), saving your own metadata **outside the Git checkout** (default: `~/.config/daedalus/accounts.toml`).

Install the API extra and generate a secret before running it:

```bash
python -m pip install -e ".[server]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --host 127.0.0.1 --port 8765
```

With the server running, clients use `Authorization: Bearer <your-secret>` for `GET /api/v1/accounts`, `GET /api/v1/capabilities`, and `GET /api/v1/warehouses/{account_id}`. `GET /api/v1/health` returns minimal status without authentication. Without explicit existing-IPC integration (or a separately injected snapshot provider), warehouse queries return HTTP 503; **no fake resources are returned**. The server refuses external listening addresses; connect a remote desktop client through an authenticated SSH or private network tunnel. No password login, worker creation, task execution, or live Ikariam request is performed by merely starting the service.

**Optional existing-session bridge:** Start the backend with `--connect-existing-ipc --accounts-file ~/.config/daedalus/accounts.toml` on the same machine/user as a **compatible, already-running** IkaBot IPC server. The Accounts page can check engine attachment and Warehouses can fetch read-only snapshots. This path never creates another Gameforge login. See [the full existing-IPC requirements, precautions and testing instructions](docs/EXISTING-IPC.md). **Do not use the current production bot installation as a test worker.**

OpenSpec 1.13 is used for spec-driven changes:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
openspec list
```

See [AGENTS.md](AGENTS.md), [implementation and OpenSpec status](docs/PROJECT-STATUS.md), [architecture](docs/ARCHITECTURE.md), [migration policy](docs/MIGRATION.md), [upstream provenance](engine/UPSTREAM.md), and [security](docs/SECURITY.md). Normative capability requirements live in [openspec/specs](openspec/specs/); completed change records live in [openspec/changes/archive](openspec/changes/archive/).

## Account-session ownership groundwork

Daedalus includes a host-local OS file lock and authentication-status state machine to prevent duplicate world/player workers **on the same backend host**. The authenticated API reports nonsecret session states for each account. This is groundwork only: **no Gameforge login, browser handoff, or game worker is started** by these components. The lock is not distributed across multiple servers; assign each account to one authoritative backend. See [session ownership and limitations](docs/SESSION-OWNERSHIP.md).

## Candidate public engine CLI (after installing `./engine/ikabot`)

The vendored IkaBot **proposed** CLI supports native task flags such as `--task`, `--config`, `--batch` and `--cities`. To see the supported syntax without logging in, run:

```bash
python -m ikabot --help
```

Actual task execution requires an authenticated IkaBot session and explicit account ownership. It must not be tried against production accounts until the session coordination and backend task adapter are ready. The independent `daedalus engine inventory` command is read-only and reports the upstream CLI's presence separately from Daedalus's own dispatch readiness.

See [the precise upstream merge record](engine/UPSTREAM.md), [the archived OpenSpec CLI/IPC integration change](openspec/changes/archive/2026-11-18-integrate-upstream-cli-ipc/proposal.md) and [current implementation status](docs/PROJECT-STATUS.md).

## Existing-session-only bridge

Daedalus can now connect **read-only** to an already-running instance of the Daedalus-vendored IkaBot engine that supports the new restricted IPC actions. The **Accounts** view has a **Check IkaBot sessions** button, and **Warehouses** can read exact unsecured-resource totals. The backend never restores a game login for these requests; the connection is explicitly opted into with `daedalus serve --connect-existing-ipc`. This does not yet provide game task start/stop or the Selenium authentication assistant. Read [the bridge setup and limitations](docs/EXISTING-IPC.md).

## Repository organization

- `src/daedalus/`: application package, local/remote HTTP client, reporting utilities and authenticated read-only API
- `engine/ikabot/`: public MIT-licensed IkaBot 7.7.2 with proposed, unreleased PR #499 CLI/IPC code
- `server/`: future supervised account workers, task dispatcher, scheduler and policies; not implemented yet
- `src/daedalus/desktop/`: reviewed Fluent desktop preview; task launch and login assistance pending
- `openspec/`: normative specifications, architecture decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Vendored IkaBot is MIT-licensed; its original [license](engine/ikabot/LICENSE) and notices are preserved. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.
