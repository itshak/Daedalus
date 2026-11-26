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


## Existing-session validation IPC overlay

The separate Daedalus-maintained existing-session-recovery-monitor change adds validate_session_existing. It selects an exact existing in-memory world/player only, performs a fixed world-host read-only GET and returns only the world/player and boolean validity. No Gameforge login, Session.from_saved, raw HTML, hidden action token or cookie is transferred. This is not part of upstream stable IkaBot. See [controller monitor limitations](../docs/EXISTING-SESSION-MONITOR.md).

## Optional private world-cookie handoff overlay

The Daedalus-maintained private-world-cookie-handoff change extends the explicit safe Session.from_saved cookies-only mode with world_cookie_override, an in-memory-only cookie obtained from the user's OS keyring after a confirmed local browser-cookie import. The default upstream CLI and login path remain unchanged, and this override is refused without cookies-only mode or exact world/player selectors. It never calls the lobby loginLink path or writes the imported cookie into upstream saved-session JSON. This is not a stable upstream feature; see [local cookie handoff](../docs/PRIVATE-WORLD-COOKIE-HANDOFF.md).

## Source-only production authentication reconciliation overlay (2026-11-18)

An owner-authorized *tracked-source-only* comparison against the locally
modified production IkaBot 7.7.0 checkout was completed. The six-file
source patch, decisions and digest are documented without private code or
credentials in [engine authentication reconciliation](../docs/ENGINE-AUTH-RECONCILIATION.md). Official upstream `master` and
PR #499 still match the pinned revisions above; the original MIT notice
is retained.

Daedalus independently adds bounded, sanitized blackbox API transport retry,
bounded operator-controlled timeouts and fail-fast behavior for unattended
password/manual-token prompts. No automatic environment credential bootstrap,
unconfirmed web server, extra Gameforge login or task replay has been ported.
This is a separately maintained Daedalus overlay, **not** upstream-author
code or evidence of live compatibility. The existing public CLI contract
and browser-assisted authentication boundary are retained.


## Daedalus independent world-page identity attestation (2026-11-18)

The maintained `helpers/serverIdentity.py` extension and the cookies-only
`Session.from_saved`/`validate_session_existing` overlay now require a
recognizable current-player marker on a TLS-verified, **nonredirecting**
game-world response. A saved IkaBot username, a selected lobby entry, an HTTP
200 response or an actionRequest token on its own cannot prove the cookie
belongs to the configured player. The engine rejects missing, ambiguous or
other-player identities and the Daedalus controller rejects IPC validation
replies that lack a typed `player_attested` boolean. The only IPC outputs are
nonsecret world/player names and booleans; raw HTML, cookies and page tokens
never cross the IPC boundary.

The optional remote Mac controller can now approve **host-only** staging and
rebind of one existing Daedalus-owned dedicated worker, but never uploads
cookies or launches a remote browser. The original public IkaBot CLI and
default non-cookies-only saved-session path are unchanged. The new parser
was subsequently checked against one owner-authorized isolated live
world page on 2026-11-19. The real own-player marker was a scoped
`#GF_toolbar li.avatarName` element, not a legacy `#avatarName` ID. The
parser now accepts this exact server-rendered self marker but still rejects
missing, conflicting or unscoped names. This is partial field evidence,
not proof of every world, full account recovery or task execution. A changed
website layout must fail closed until carefully reviewed.

The same limited live smoke exposed two upstream-compatible IPC mismatches:
`getIdsOfCities` provides numeric string map keys, so the existing-session
bridge now converts only strict positive decimal IDs to typed IPC integers
while preserving upstream legacy CLI behavior. The current warehouse page
requires a warehouse building slot from the authenticated city view, and
reports plunderable/capacity values in a server-rendered JSON updater map,
not always direct spans. Only bounded numeric resource values leave the
engine; arbitrary HTML, page tokens and raw cookies remain private. One
owner-approved test returned seven city and seven warehouse records; the
remaining live recovery, explicit task dispatch and production gates in
`openspec/changes/validate-live-authentication` remain open.

## Warehouse consolidation overlay

The warehouse task is a Daedalus planner/policy, not an independent game transport engine. It translates the reviewed allocation into the upstream PR #499 sendResources route contract, reuses prepare_sendResources and shared route resolution, and applies its storage/incoming guards inside executeRoutes. The common sendGoods builds the upstream form (including explicit zero-valued available resource inputs). Cookie-only transport is a bounded adapter behind Session.post, not a second sender; ordinary CLI sessions retain existing behavior. The upstream baseline and PR head were source-compared; upstream stable and both reviewed PR #499 revisions use the same sendGoods form. Live compatibility is not inferred from synthetic tests.

## Operation-specific waiting compatibility

See [upstream wait audit](../docs/UPSTREAM-WAIT-AUDIT.md) for the source comparison, operation inventory, preserved queue algorithms and offline evidence. The Daedalus cookie-only adapter now admits the exact existing read-only queue forms for the fleet advisor, barracks, shipyard, workshop, temple and construction-speedup popup. These are local transport compatibility changes; the upstream wait helper and queue algorithms remain the source of truth. Live multi-iteration acceptance remains open.

## Engine parity audit

The correct merged stable + CLI/IPC comparison point is Daedalus commit ba6aaba (not the stable-only import ab070fb). [Full definition inventory and rationale](../docs/UPSTREAM-ENGINE-PARITY.md) records every changed module relative to this baseline, remaining integration risks and the shared original request builders. Twenty-five preserved upstream helpers are source-guarded in offline CI. New local read-form validation is isolated in nativeReadForms; no blanket mutation proxy or live-game acceptance is implied.

The governing architecture decision is [ADR-006: upstream-first engine reuse](../openspec/adr/006-upstream-first-engine-reuse.md). Consult it before changing any game operation or shared helper.
