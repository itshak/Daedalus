# Upstream dependencies, provenance and licenses

## Public IkaBot

- Source: https://github.com/Ikabot-Collective/ikabot
- License: MIT (Copyright (c) 2018 Physics; subsequent contributors retain their rights).
- Stable baseline: public version 7.7.2, commit `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579`.
- Experimental CLI/IPC overlay: upstream PR #499 head `062feec0f5f6ea5810bfe91126e337a2b86aa3e3`, including follow-up PRs #502 and #511. This is unmerged proposed upstream code and not a released version.
- Imported tree: conflict-free working-tree merge of the two upstream revisions, reproducible as documented in `engine/UPSTREAM.md`.
- Verbatim upstream MIT license: [engine/ikabot/LICENSE](../engine/ikabot/LICENSE).
- Source provenance and reproducible two-commit merge command: [engine/UPSTREAM.md](../engine/UPSTREAM.md).
- No production server credentials or local account configuration imported.
- Track future upstream updates in dedicated OpenSpec changes and preserve compatibility when possible.

## Private source migration

The existing GUI implementation and locally modified production bot are **review inputs**, not Git submodules, fork sources or wholesale import candidates. Nothing from their credentials, private configuration, runtime cache, tokens, cookies or logs belongs in public history.

## Desktop licensing

The existing PySide6 Fluent Widgets dependency has separate license conditions. Review these and any other third-party dependencies before shipping the combined desktop binary. Project-original code is GPL-3.0-only, but third-party notices and applicable licenses remain independent.

## Package naming

The intended PyPI distribution, Python import and CLI are all `daedalus`. No PyPI release has been claimed; verify name eligibility before publishing.

## Production auth reconciliation
The reviewed production IkaBot source differences and safety decisions are
documented in [engine auth source reconciliation](ENGINE-AUTH-RECONCILIATION.md).
Only independently rewritten, secret-free reliability improvements were added;
no local credentials, saved users or runtime files were imported. Production
browser/session acceptance remains pending.
