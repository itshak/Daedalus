# Vendored public IkaBot engine

## Revision

- **Upstream:** https://github.com/Ikabot-Collective/ikabot
- **Branch:** `master`
- **Commit:** `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579`
- **Version:** 7.7.2
- **Imported:** 2026-11-17
- **License:** MIT, with a verbatim original at `engine/ikabot/LICENSE`
- **Source scope:** `LICENSE`, `README.md`, `MANIFEST.in`, `setup.py`, `ikabot/`, `tests/`, `assets/` (90 files)
- **Source:** Clean upstream public commit, not the customized production server.

## Why it is embedded

This repository is intended to be buildable from one checkout and supports later reviewed extensions to the engine (CLI/IPC, session recovery and warehouse snapshots). It intentionally keeps public IkaBot's `ikabot` package name, while the new application is packaged as `daedalus`.

**Do not install the old private GUI distribution named `ikabot` into this same Python environment.** That old GUI will be ported to Daedalus's own namespace.

## Reproducing the pristine baseline

Use a temporary checkout of public upstream and the pinned commit:

```bash
git clone https://github.com/Ikabot-Collective/ikabot.git /tmp/ikabot-public
mkdir -p engine/ikabot
git -C /tmp/ikabot-public archive 3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579 \
  LICENSE README.md MANIFEST.in setup.py ikabot tests assets | tar -x -C engine/ikabot
```

The upstream test suite remains in `engine/ikabot/tests/ikabot/`. A future IkaBot update should be reviewed in an OpenSpec change, merged deliberately, and validated with offline tests. **Never overwrite private production `/home/debian/ikabot` or its account configuration.**

## JSON CLI / IPC status

The stable imported revision supports IkaBot's legacy positional menu input, not a JSON task API. Upstream PR #499 has proposed `--task`, `--config`, `--batch`, `--cities` and a localhost IPC server, with associated improvements from PRs #502 and #511. Those changes are **not yet in this stable vendored baseline**; they require separate test-gated integration.

The `daedalus engine inventory` command is source-only and does not start a bot, perform login or execute tasks.
