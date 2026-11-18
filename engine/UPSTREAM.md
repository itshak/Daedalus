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

## Daedalus-maintained IPC compatibility overlay

Starting with the `connect-existing-ipc` milestone, Daedalus adds a **small tracked patch** to `engine/ikabot/ikabot/helpers/ipc.py` and a synthetic regression test `test_daedalus_existing_ipc.py`. The new operations are `list_sessions`, `list_cities_existing`, and `warehouse_snapshots_existing`. They require an already-authenticated in-memory session and cannot invoke `Session.from_saved`. The warehouse action returns numeric resource fields only, never full game HTML or action tokens. Upstream `start_task` and `list_cities` remain intact for compatibility.

The two public upstream revisions still define the **base** engine import; the Daedalus-specific patch must be applied on top (and will appear explicitly in the `[connect-existing-ipc]` repository commit). This overlay is not attributed to upstream IkaBot, nor presented as a stable upstream release. See the [archived read-only bridge design](../openspec/changes/archive/2026-11-18-connect-existing-ipc/design.md).

## Daedalus task control overlay

The subsequent `enable-existing-session-tasks` milestone extends only the Daedalus-maintained IPC patch, adding `start_task_existing`, `list_managed_tasks`, and `stop_managed_task`. They require an existing authenticated session, packaged built-in `@task` implementations, bounded JSON config, and UUID4 idempotency. A private in-memory registry stores exact Process objects to prevent termination of arbitrary PID targets. These operations are not upstream PR #499 features, and must be kept in the local patch series during any future upstream upgrade.

## Available, not yet exposed to live account workers

The proposed engine adds:
- `ikabot --world=... --player=... --task=... --config=<JSON>`
- `ikabot --batch=@tasks.json` for multiple prepared tasks
- `ikabot --cities` for city metadata lookup
- Local IPC server with loopback socket, authentication key and 0600-protected discovery file
- Task configuration viewing/saving/relaunch and preparation hooks in multiple native modules

Daedalus does **not** expose this privileged IPC server directly over its HTTP API. Daedalus now offers **optional** existing-session task validation, idempotent start, managed-task status and stop; durable account worker ownership, pause/resume and login recovery remain separate integrations. The existing CLI may create authenticated sessions; run it only after explicit account provisioning, never from public CI.

## Verification

An isolated master+PR #499 merged checkout passed:
- 275 upstream Python tests, 9 skips and 107 subtests
- 32 focused CLI/IPC/config/city tests and 29 focused subtests

All tests used a sandbox HOME and synthetic data, with no production account authentication.

The CLI/IPC patchset is upstream code under review and may change before merging into upstream master. Future upgrades must reconcile this branch with master and re-run the offline suite.

## Daedalus safe cookie-only recovery overlay

The `safe-saved-session-recovery` change adds a **Daedalus-specific** optional `Session.from_saved(..., cookies_only=True)` pathway. It bypasses lobby token/loginLink/blackbox flows, checks only existing world cookies against the exact world, requires a successful world-host HTTP 200 and rejects invalid cookies without a new Gameforge login. The old upstream CLI and `from_saved` default semantics are kept; this option is not represented as an upstream IkaBot stable feature. Daedalus's local `sessions probe-saved-cookies` command uses the explicit mode under an account lease, with the saved-user email association held in the OS keyring rather than source. No game tests execute in CI. See [recovery setup](../docs/SAFE-COOKIE-RECOVERY.md).
