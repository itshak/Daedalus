# Upstream dependencies, provenance and licenses

## Public IkaBot

- Source: https://github.com/Ikabot-Collective/ikabot
- License: MIT (Copyright (c) 2018 Physics; subsequent contributors retain their rights).
- No public IkaBot source has been imported at this foundation stage.
- On import, keep a verbatim copy of its MIT LICENSE in the engine's provenance directory and preserve all required copyright notices.
- Prefer upstream-compatible changes. Document the upstream commit and merge strategy.

## Private source migration

The existing GUI implementation and locally modified production bot are **review inputs**, not Git submodules, fork sources or wholesale import candidates. Nothing from their credentials, private configuration, runtime cache, tokens, cookies or logs belongs in public history.

## Desktop licensing

The existing PySide6 Fluent Widgets dependency has separate license conditions. Review these and any other third-party dependencies before shipping the combined desktop binary. Project-original code is GPL-3.0-only, but third-party notices and applicable licenses remain independent.

## Package naming

The intended PyPI distribution, Python import and CLI are all `daedalus`. No PyPI release has been claimed; verify name eligibility before publishing.
