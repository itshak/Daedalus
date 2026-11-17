# Public IkaBot engine provenance — unreleased CLI/IPC integration

## Source identity

- Upstream: https://github.com/Ikabot-Collective/ikabot
- Stable master baseline: `3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579` (IkaBot 7.7.2, Nov 16, 2026)
- Proposed CLI/IPC source: [upstream PR #499](https://github.com/Ikabot-Collective/ikabot/pull/499), head `062feec0f5f6ea5810bfe91126e337a2b86aa3e3` (Nov 16, 2026)
- Included work: #502 (CLI task improvements) and #511 (task configuration, batch/city-ID refinements). These are integrated through the PR #499 branch; **do not cherry-pick them a second time**.
- Import strategy: merge PR #499 into the stable master baseline without conflicts, retain the resulting working tree's engine source and upstream tests.
- Status: **experimental unreleased upstream patchset**. It is NOT represented as an official stable IkaBot release.
- Source license: MIT, original notice at `engine/ikabot/LICENSE`. Project-original Daedalus code is separately GPL-3.0-only.
- No production account configurations, sessions, secrets, or browser profiles were used as source inputs.

## Reproducing the merged engine tree

From a clean temporary checkout of public upstream, without touching a production installation:

```bash
git clone https://github.com/Ikabot-Collective/ikabot.git /tmp/ikabot-upstream
cd /tmp/ikabot-upstream
git fetch origin master
git fetch origin refs/pull/499/head:refs/remotes/origin/daedalus-pr499
git checkout --detach 3ea1e0eebfb2e52b5f53ea8b5051df2a9a887579
git merge --no-commit --no-ff refs/remotes/origin/daedalus-pr499

# Compare the resulting LICENSE, README.md, MANIFEST.in, setup.py,
# ikabot/, tests/, and assets/ with Daedalus's engine/ikabot/ directory.
# The merge was conflict-free when this patchset was reviewed.
```

The commit pair precisely defines the source. The engine in Daedalus retains the upstream `ikabot` package namespace and its own tests. The desktop GUI will use a renamed package to prevent imports from shadowing the engine.

## Available, not yet exposed to live account workers

The proposed engine adds:
- `ikabot --world=... --player=... --task=... --config=<JSON>`
- `ikabot --batch=@tasks.json` for multiple prepared tasks
- `ikabot --cities` for city metadata lookup
- Local IPC server with loopback socket, authentication key and 0600-protected discovery file
- Task configuration viewing/saving/relaunch and preparation hooks in multiple native modules

Daedalus does **not** expose this privileged IPC server directly over its HTTP API. Task validation, account ownership, idempotent execution, status reporting and stop/pause capability are separate integrations. The existing CLI may create authenticated sessions; run it only after explicit account provisioning, never from public CI.

## Verification

An isolated master+PR #499 merged checkout passed:
- 275 upstream Python tests, 9 skips and 107 subtests
- 32 focused CLI/IPC/config/city tests and 29 focused subtests

All tests used a sandbox HOME and synthetic data, with no production account authentication.

The CLI/IPC patchset is upstream code under review and may change before merging into upstream master. Future upgrades must reconcile this branch with master and re-run the offline suite.
