# Daedalus for Ikariam

**Status: engine-import prototype.** The pristine public IkaBot 7.7.2 source is vendored in `engine/ikabot/`. The application does **not yet** contain a game-account backend, an executable JSON task API, or the migrated desktop UI. Its CLI provides offline diagnostics and a source-level operation inventory only.

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
```

The `engine inventory` command reads public engine source files through the Python AST, listing actual IkaBot menu actions and background tasks in JSON. It **does not launch bots, execute tasks or make game requests**. Current stable upstream 7.7.2 does not include the proposed structured JSON task launcher.

OpenSpec 1.13 is used for spec-driven changes:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
openspec list
```

See [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md), [migration policy](docs/MIGRATION.md), [upstream provenance](engine/UPSTREAM.md), and [security](docs/SECURITY.md). Design specifications and proposals live in [openspec](openspec/).

## Repository organization

- `src/daedalus/`: distinct Python application package and offline CLI
- `engine/ikabot/`: clean public IkaBot 7.7.2 source, preserved MIT license
- `server/`: future API and scheduler; not implemented yet
- `desktop/`: future audited PySide6 GUI import; not implemented yet
- `openspec/`: normative specifications, architecture decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Vendored IkaBot is MIT-licensed; its original [license](engine/ikabot/LICENSE) and notices are preserved. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.
