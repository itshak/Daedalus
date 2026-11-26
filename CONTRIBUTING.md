# Contributing to Daedalus

Thank you for helping improve Daedalus. The project is **beta**; its desktop application, API contracts, and upstream IkaBot integration are evolving. Contributions should be focused, reproducible, and safe to test without real accounts.

## Before you start

- Check the [README](README.md), [current implementation status](docs/PROJECT-STATUS.md), [architecture](docs/ARCHITECTURE.md), and [OpenSpec workflow](AGENTS.md).
- Search existing issues and pull requests before opening a duplicate.
- For defects, use the bug report form and reproduce them using the [synthetic demo](docs/SYNTHETIC-DEMO.md) wherever possible.
- For significant behavior or architecture changes, first discuss the design in an issue and create or update an OpenSpec change. Minor documentation and branding fixes do not need an OpenSpec proposal.
- **Never disclose or commit** live accounts, passwords, cookies, Gameforge tokens, browser profiles, production logs, or other private material. Report vulnerabilities using [private vulnerability reporting](SECURITY.md), not a public issue.

## Local development

Daedalus requires Python 3.11+. Install the project and test dependencies from a fresh virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pip install -e ./engine/ikabot pytest-mock
python -m pytest -q tests
python -m ruff check src tests scripts
```

To work on the native desktop GUI, install `python -m pip install -e ".[desktop]"`. For headless Linux desktop tests use `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_desktop.py`. macOS GUI tests should run with `QT_QPA_PLATFORM=cocoa` on an actual Mac. The vendored engine has separate tests under `engine/ikabot/tests/ikabot`.

For normative changes, install the documented version of OpenSpec and run:

```bash
npm install -g @fission-ai/openspec@1.13.0
openspec validate --all --strict --no-interactive
```

## Pull requests

1. Create a branch from the current `main` and keep the diff focused.
2. Add or update tests for behavior changes. Use synthetic fixtures and offline mocks; public CI must never log into a real game account.
3. Update affected documentation, specs, and OpenSpec task checkboxes only when the functionality has actually been verified. Archive a completed OpenSpec change and sync canonical specs according to `AGENTS.md`.
4. Preserve MIT license notices and provenance for vendored IkaBot material. Do not copy private-project history or runtime artifacts.
5. Run the relevant tests and lint locally, and include the exact results or limitations in the pull request.
6. Use a descriptive PR title and explain safety, compatibility, and any user-visible behavior change.

Check your Git identity before committing: `git config user.name` and `git config user.email`. Git commit attribution should reflect the actual contributor. Repository maintainers should use their intended account-specific identity rather than relying on an unrelated global Git configuration.

## Scope and conduct

No CAPTCHA bypasses, credential collection in the GUI, unsafe direct connections to production workers, or new unaudited bot engines. Keep the local/remote session-ownership guarantees and default read-only behavior intact. Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

For usage help, see [SUPPORT.md](SUPPORT.md); for sensitive reports, see [SECURITY.md](SECURITY.md).
