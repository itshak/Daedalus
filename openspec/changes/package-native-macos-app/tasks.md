# Tasks

## Packaging
- [x] Port the safe PyInstaller build path to `daedalus.desktop`.
- [x] Eliminate automatic installation, config seeding, and legacy Selenium bundling.
- [x] Provide a dry-run that works on non-macOS systems.
- [x] Document unsigned/ad-hoc and Gatekeeper limitations.

## CI and verification
- [x] Add a macOS build workflow with a short-retention artifact.
- [x] Add synthetic packaging tests that never call PyInstaller by default.
- [ ] Verify macOS GitHub Actions produces the app and verifies its signature.
- [ ] Review and merge with all required checks under itshak.
