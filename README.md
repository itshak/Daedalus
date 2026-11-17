# Daedalus for Ikariam

**Status: foundation / specifications only.** This repository does not yet contain a game engine, account automation service, or functional desktop UI. The CLI currently provides offline project diagnostics only.

Daedalus is an open-source, desktop-first control center intended to integrate the [IkaBot](https://github.com/Ikabot-Collective/ikabot) game automation engine with a multi-account backend and a native PySide6 desktop application.

## Principles

- **One game engine:** reuse public IkaBot task implementations instead of reproducing the game's HTTP operations.
- **One account session owner:** prevent competing logins and duplicate live workers.
- **Complete desktop control:** preserve and expand the existing Fluent/PySide6 interface.
- **Local or remote:** the same validated backend API works on a user's computer or a remote Linux server.
- **Authentication recovery:** retain existing Selenium-assisted login, saved cookies, manual login and CAPTCHA assistance; do not assume upstream email/password login works reliably.
- **Secure by default:** no live user credentials, tokens, browser profiles, cookies, or runtime files in source control or public CI.

## Project setup

Requires Python 3.11+:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
daedalus --version
daedalus doctor
```

OpenSpec 1.13 is used for the design workflow:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
openspec list
```

See [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md), [migration policy](docs/MIGRATION.md), and [security](docs/SECURITY.md). Design specifications and proposals live in [openspec](openspec/).

## Repository organization

- `src/daedalus/`: new application package and CLI skeleton
- `engine/`: future upstream-tracked IkaBot source; **not imported yet**
- `server/`: future API and scheduler; **not implemented yet**
- `desktop/`: future adapted PySide6 GUI; **not imported yet**
- `openspec/`: specifications, architectural decisions and change proposals

## License and provenance

Project-original code is offered under **GPL-3.0-only**. Upstream IkaBot is MIT-licensed; its separate license and required notices must be retained when its code is imported. Other dependencies and imported code require license review before distribution. See [docs/UPSTREAM.md](docs/UPSTREAM.md).

This project is independently developed and is not affiliated with Gameforge or the upstream IkaBot maintainers.
