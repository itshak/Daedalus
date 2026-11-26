# First beta release preparation

Target: Git tag `v0.1.0-beta.1`, Python `0.1.0b1`, web `0.1.0-beta.1`. This document prepares a prerelease, not stable certification or evidence of publication.

## Build and verification

1. Use a clean, reviewed commit; record its full SHA. Run the Python and upstream regression suites, Ruff, strict OpenSpec validation, web tests/typecheck/lint/build and synthetic browser E2E. Require all applicable GitHub workflows to pass, including dependency and secret scanning.
2. Build macOS using the existing macOS workflow. Verify the bundle version and source SHA against the reviewed commit. Download the DMG and SHA-256 checksum and verify the checksum locally. Preview signing is ad hoc; do not present it as notarization.
3. Build the web application from the same reviewed revision, with Vercel-provided commit provenance. Use private server-side environment configuration; do not ship credentials or game snapshots. Confirm the controller API compatibility before promoting a deployment.
4. After release approval, publish the tag as a GitHub prerelease with the changelog, matching artifact and checksum, supported setup instructions and known limitations. Do not mark it as stable.

## Deployment and rollback

Keep the prior verified backend revision, DMG and Vercel deployment available. Back up protected account configuration and durable receipt state using the existing secure operational procedure. Stage compatible backend/web revisions before promotion. Do not migrate or overwrite protected production state as part of release packaging. If the rollout fails, restore the previous compatible backend and Vercel deployment; preserve receipt history and require operator review of uncertain operations rather than replaying them.

The remaining engineering work is tracked in `finish-v010-engineering`; real game effects and physical Mac acceptance remain separately in [owner acceptance](V010-OWNER-ACCEPTANCE.md). No versioned beta release has been published by this preparation alone.

CI workflow updates for browser E2E and bundle provenance assertions are committed on the engineering branch through the authorized GitHub integration. The server CLI retains its limited OAuth scope; GitHub branch protection remains in force. Require actual successful CI on the final revision.

Native visual QA: `QT_QPA_PLATFORM=offscreen python scripts/capture_native_ui.py --output-dir ./qa-screenshots` renders the actual Qt client with synthetic fixtures. The matrix includes 19 primary/secondary views at 900×650 and 1200×800 in light/dark, and all 33 native operation editors at 900×650 in both themes (142 images). The Linux CI screenshot artifact must be generated successfully; physical macOS visual acceptance is separate.
