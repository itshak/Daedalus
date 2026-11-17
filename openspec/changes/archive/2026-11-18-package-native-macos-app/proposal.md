# Produce a native macOS application preview from CI

## Why
The existing Mac GUI is a core Daedalus capability. A user-testable .app needs to be produced reproducibly from the current public source, rather than from the legacy private scraper or a prepublished IkaBot wheel.

## What Changes
- Adapt the author's existing PyInstaller Mac packaging helper to the new Daedalus entry point.
- Produce `Daedalus.app` without copying sessions or installing into /Applications.
- Add optional `macos-build` dependencies, local dry-run and safety tests.
- Add a restricted GitHub Actions macOS build that ad-hoc signs the preview and uploads a CI artifact.

## Capabilities
### Modified Capabilities
- `desktop-client`: portable native macOS preview packaging.

## Non-goals
No notarization, Developer ID signing, auto-updater, public release, bundled server worker, Selenium engine, accounts or private login state.

## Impact
Reviewable macOS app artifacts from every proposed source change, while preserving the GPL/provenance and security boundaries.
