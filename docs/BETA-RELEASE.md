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

## Stage the immutable beta draft

After the final preparation PR is merged and all seven workflows for that **exact main revision** succeed, run from its clean checkout:

```bash
python scripts/prepare_beta_release.py --revision "$(git rev-parse HEAD)"
python scripts/prepare_beta_release.py --revision "$(git rev-parse HEAD)" --create-draft
```

The first command verifies the main SHA, current CI, matching preview tag and downloaded DMG checksum. The second creates an unpublished GitHub prerelease draft using those exact bytes. To refresh an existing unpublished beta draft after a newer reviewed main revision passes all checks, use `--refresh-draft` instead of `--create-draft`. It refuses to replace a published release or move an existing tag and re-downloads the refreshed assets to verify their checksum. Publication and production rollout remain separate approval actions.

For owner testing before final publication, use the matching verified [merged Mac preview 26663b8](https://github.com/itshak/Daedalus/releases/tag/desktop-preview-26663b8e7b01), and check the [beta operation scope](BETA-OPERATION-SCOPE.md). This is a beta test candidate, not evidence that all game operations or the live deployment are accepted.

## Version-gated Vercel deployment policy

Ordinary main pushes and pull requests run GitHub CI but skip Vercel builds. The project-level Ignored Build Step and `apps/web/vercel.json` use `apps/web/scripts/vercel-ignore-build.mjs`. An automatic production build is permitted only on `main` when the current web package version strictly increases from the first parent and agrees with both lockfile version fields. Use a single reviewed version-bump merge (not a multi-commit push with the bump buried in history). Align Python/web versions and validate the version-consistency test before merging. Missing history or invalid metadata skips rather than builds. Preview pushes skip too; synthetic web CI still runs on every PR.

This gate is a version-bump trigger, not a publication or CI approval mechanism: do not bump the version until the release candidate has been reviewed. The GitHub versioned release remains a separate explicit approval. For a failed build, a necessary hotfix without a version increase, or an older revision, use Vercel Deployments → Redeploy and uncheck **Use project's Ignore Build Step**, or manually create a deployment from an exact reviewed Git SHA in the dashboard. Select production only after approval. Do not remove the persistent policy to redeploy. No additional deploy credentials or public hooks are required.

The clean server-only installation must pass `daedalus doctor --smoke` in a fresh virtual environment with a synthetic home. The server extra includes the HTTP client required by that diagnostic; package CI exercises the actual wheel with `[server]` rather than assuming developer-only dependencies are installed. Do not restart an authenticated production worker merely to test installation.
