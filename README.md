# Daedalus for Ikariam

**Status: read-only controller plus experimental upstream CLI/IPC engine.** Daedalus provides a credential-free local multi-account configuration format, an authenticated read-only API, and an offline task registry. The vendored engine combines public IkaBot 7.7.2 with proposed [upstream PR #499](https://github.com/Ikabot-Collective/ikabot/pull/499), including #502 and #511. This engine code is **not yet an official stable upstream release**. Daedalus does **not yet** connect authenticated workers, execute game tasks through the controller, or include the migrated desktop UI.

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

The `engine inventory` command reads public engine source files through the Python AST, listing actual IkaBot menu actions and background tasks in JSON. It **does not launch bots, execute tasks or make game requests**. Daedalus now contains a reviewed upstream CLI/IPC proposal; it is **not connected to live account workers**, and it does not make every individual task automatically safe or serializable.

## Read-only local API

The initial controller implements metadata and capability reporting, not game automation. It reads account identities from a private TOML file and does **not** allow passwords, Gameforge tokens, cookies, or account email addresses in that file. Start from [the synthetic example](docs/examples/accounts.toml), saving your own metadata **outside the Git checkout** (default: `~/.config/daedalus/accounts.toml`).

Install the API extra and generate a secret before running it:

```bash
python -m pip install -e ".[server]"
export DAEDALUS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
daedalus serve --host 127.0.0.1 --port 8765
```

With the server running, clients use `Authorization: Bearer <your-secret>` for `GET /api/v1/accounts`, `GET /api/v1/capabilities`, and `GET /api/v1/warehouses/{account_id}`. `GET /api/v1/health` returns minimal status without authentication. Warehouse queries explicitly return HTTP 503 until an authenticated game worker is connected; **no fake resources are returned**. The server refuses external listening addresses; connect a remote desktop client through an authenticated SSH or private network tunnel. No password login, worker creation, task execution, or live Ikariam request is performed by merely starting the service.

OpenSpec 1.13 is used for spec-driven changes:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
openspec list
```

See [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md), [migration policy](docs/MIGRATION.md), [upstream provenance](engine/UPSTREAM.md), and [security](docs/SECURITY.md). Design specifications and proposals live in [openspec](openspec/).

## Account-session ownership groundwork

Daedalus includes a host-local OS file lock and authentication-status state machine to prevent duplicate world/player workers **on the same backend host**. The authenticated API reports nonsecret session states for each account. This is groundwork only: **no Gameforge login, browser handoff, or game worker is started** by these components. The lock is not distributed across multiple servers; assign each account to one authoritative backend. See [session ownership and limitations](docs/SESSION-OWNERSHIP.md).

## Candidate public engine CLI (after installing `./engine/ikabot`)

The vendored IkaBot **proposed** CLI supports native task flags such as `--task`, `--config`, `--batch` and `--cities`. To see the supported syntax without logging in, run:

```bash
python -m ikabot --help
```

Actual task execution requires an authenticated IkaBot session and explicit account ownership. It must not be tried against production accounts until the session coordination and backend task adapter are ready. The independent `daedalus engine inventory` command is read-only and reports the upstream CLI's presence separately from Daedalus's own dispatch readiness.

See [the precise upstream merge record](engine/UPSTREAM.md) and [the OpenSpec integration change](openspec/changes/integrate-upstream-cli-ipc/proposal.md).

## Repository organization

- `src/daedalus/`: distinct Python application package, offline CLI and authenticated read-only API
- `engine/ikabot/`: public MIT-licensed IkaBot 7.7.2 with proposed, unreleased PR #499 CLI/IPC code
- `server/`: future supervised account workers, task dispatcher, scheduler and policies; not implemented yet
- `desktop/`: future audited PySide6 GUI import; not implemented yet
- `openspec/`: normative specifications, architecture decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Vendored IkaBot is MIT-licensed; its original [license](engine/ikabot/LICENSE) and notices are preserved. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.
