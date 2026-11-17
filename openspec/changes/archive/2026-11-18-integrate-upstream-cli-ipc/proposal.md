# Integrate unreleased upstream CLI and IPC support

## Why

Public IkaBot's stable version supports native game operations but offers a menu-driven interface unsuited to a complete Mac GUI. Upstream PR #499 proposes typed JSON configuration, CLI batch launching and authenticated local IPC, and includes merged follow-up PRs #502 and #511. Daedalus should integrate this tested engine capability **before building task-control views**.

## What Changes

- Combine the unchanged stable public 7.7.2 master baseline with the PR #499 head, retaining fixes on both branches.
- Vendor the combined upstream source and its tests under `engine/ikabot`, with a reproducible two-commit provenance record and original MIT license.
- Test CLI argument parsing, JSON task configuration, batch validation, IPC authentication and task configuration persistence entirely offline.
- Expose an **accurate read-only source capability flag** in `daedalus doctor` and `daedalus engine inventory`, without automatically dispatching game tasks.
- Preserve separation between the public engine package `ikabot` and the Daedalus controller/UI package.

## Capabilities

### Modified Capabilities
- `engine-integration`: adopt an unreleased but reviewed CLI/IPC transport and preserve source provenance.

## Non-goals

This change does NOT connect live accounts, share IPC access over the network, enable controller-to-engine task dispatch, automate login or CAPTCHA, or migrate production workers. It does not imply that every IkaBot task accepts a ready-made serializable configuration.

## Impact

The full project can build typed task controls against a real upstream engine mechanism. Session ownership, task schema coverage, secure backend IPC bridging, and production activation remain separate test-gated tasks. See ADR-001, ADR-002, ADR-003 and ADR-004.
