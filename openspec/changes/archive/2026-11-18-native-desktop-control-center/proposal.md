# Start the native Fluent Daedalus control center

## Why
The owner prefers the existing PySide6 Fluent Mac GUI over a web app rewrite. The new backend already exposes safe account, task and warehouse endpoints, so a native client can be rebuilt around the original visual vocabulary without transporting legacy saved credentials or Selenium sessions.

## What Changes
- Port reviewed GUI navigation, Mac native titlebar handling, theme, scrollable tables and queued Qt logging patterns from the private GUI.
- Add a secure read-only desktop API client supporting local HTTP loopback and HTTPS remote servers; reject plaintext non-loopback credentials.
- Add Accounts, Warehouses, Operations, Log and Connection pages with async backend calls.
- Preserve the warehouse 220K unsecured-resource filter and CSV/JSON exports, including unknown/null values.
- Add a desktop entry point, optional PySide6/Fluent dependency group and a dedicated macOS headless UI smoke workflow.

## Capabilities
### Modified Capabilities
- `desktop-client`: native Fluent shell and read-only API presentation.
- `controller-api`: read-only client contract and transport confidentiality.

## Non-goals
No task launch, game login, Selenium code, CAPTCHA solver, remote browser, local session secrets, private settings import, native app signing or complete GUI feature parity.

## Impact
Provides an executable first native Mac UI foundation while preserving existing design. See `docs/GUI-MIGRATION.md`, ADR-001 and ADR-005.
