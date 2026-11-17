# Upstream dependencies, provenance and licenses

## Public IkaBot

- Source: https://github.com/Ikabot-Collective/ikabot
- License: MIT (Copyright (c) 2018 Physics; subsequent contributors retain their rights).
- Baseline imported at `engine/ikabot/`: public version 7.7.2, commit `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579`.
- Verbatim upstream MIT license: [engine/ikabot/LICENSE](../engine/ikabot/LICENSE).
- Source import inventory and reproducible archive command: [engine/UPSTREAM.md](../engine/UPSTREAM.md).
- No production server credentials or local account configuration imported.
- Track future upstream updates in dedicated OpenSpec changes and preserve compatibility when possible.

## Private source migration

The existing GUI implementation and locally modified production bot are **review inputs**, not Git submodules, fork sources or wholesale import candidates. Nothing from their credentials, private configuration, runtime cache, tokens, cookies or logs belongs in public history.

## Desktop licensing

The existing PySide6 Fluent Widgets dependency has separate license conditions. Review these and any other third-party dependencies before shipping the combined desktop binary. Project-original code is GPL-3.0-only, but third-party notices and applicable licenses remain independent.

## Package naming

The intended PyPI distribution, Python import and CLI are all `daedalus`. No PyPI release has been claimed; verify name eligibility before publishing.
