# Daedalus for Ikariam

**Status: read-only controller prototype.** Public IkaBot 7.7.2 is vendored in `engine/ikabot/`, and Daedalus provides a small authenticated read-only API, local account metadata, and an offline task registry. It does **not yet** connect authenticated game workers, start game tasks, offer the proposed JSON IPC dispatcher, or include the migrated desktop UI.

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

The `engine inventory` command reads public engine source files through the Python AST, listing actual IkaBot menu actions and background tasks in JSON. It **does not launch bots, execute tasks or make game requests**. Current stable upstream 7.7.2 does not include the proposed structured JSON task launcher.

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

## Repository organization

- `src/daedalus/`: distinct Python application package, offline CLI and authenticated read-only API
- `engine/ikabot/`: clean public IkaBot 7.7.2 source, preserved MIT license
- `server/`: future supervised account workers, scheduler and policies; not implemented yet
- `desktop/`: future audited PySide6 GUI import; not implemented yet
- `openspec/`: normative specifications, architecture decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Vendored IkaBot is MIT-licensed; its original [license](engine/ikabot/LICENSE) and notices are preserved. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.
