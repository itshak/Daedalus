# Successor implementation evidence

## Multi-island one-time shipments and generated launch contract

Native Qt and web shipment editors retain verified external city records with their original island coordinates across searches. Refreshing one island invalidates only its old recipients; a city found on a different island must be selected anew. Clear removes all external selections; account context resets the inventory. Up to ten islands are supported. The existing server ticket and worker recipient revalidation remain authoritative; no live game actions performed.

A generated TypeScript contract now derives supported draft task names, reviewed launch endpoints, ticket syntax, batch size and version from the Python manifest and reviewed endpoint map. Desktop start routing, web batch dispatch and BFF allowlists consume that map. A pytest drift check requires regeneration when the source changes. Full generated domain draft/preview/receipt schemas are still outstanding.

Baseline full local regression at 0a6d33d: 765 controller tests passed, 11 skipped; 412 engine tests passed, 9 skipped, 126 subtests. Archived 77a1638 passed 15 OpenSpec validation items. This follow-up: focused Qt shipment 3 passed; focused client/registry/batch/preview 37 passed; web unit suite 47 passed; typecheck and Ruff passed; lint 0 errors, 14 warnings. GitHub CI and live/Mac acceptance remain required. No production deployment.


## Full owned-city deployment selection

Station troops/fleet now covers all five upstream CLI deployment choices, including all other owned cities and combined ground/fleet. Both clients present named per-origin/category totals and shared transport capacity before approval. The engine builds a bounded aggregate fingerprint and revalidates every nonempty route before its individual non-retried POST. The conservative summed ground weight must fit the shared observed capacity. Empty routes are explicit and skipped; changed units or insufficient capacity stop remaining routes, with no rollback of prior submissions. Existing single-city contract remains compatible. The controller verifies complete owned-city coverage; the client independently validates the projection and ticket. This extends option parity but is not live acceptance.

Focused Python/Qt/API/batch/manifest regression: 49 passed. Web unit suite: 48 passed. TypeScript and Ruff passed; web lint 0 errors, 14 existing warnings. No real game requests.


## Multiple-city worker assignment and both production projects

Both clients now support additional selected owned cities for all three worker assignment operations and forest, luxury or both production projects. The engine reads the actual upstream slider in each city/project and constructs the exact reviewed target, validates the aggregate contract and rechecks each assignment immediately before a single non-retried mutation. Foreign/duplicate cities, missing buildings and invalid capacity block the plan; changed observations stop remaining writes. Existing single-city payloads remain compatible. Up to 32 cities can be selected. The game may still reject assignments when population is insufficient; no speculative economic impact or live acceptance is asserted.

Focused controller/engine-adapter/Qt/batch/manifest regressions: 58 passed. Web unit suite: 49 passed; TypeScript, Ruff and web lint passed (14 existing warnings).


## Reviewed recruitment

Both clients now support ordered recruitment rounds, repeated cycles and selected owned cities, with the existing game-derived barracks/shipyard inventory. Controller checks every selected city's unit costs and first-round affordability, issues an account-scoped ticket, and removes the generic HTTP start path for recruitment. The worker verifies all reviewed city/building/unit identities and costs, waits for training, checks stock and makes one non-retried submission for each round. Later rounds halt when the preceding training queue cannot be observed or data changes. Recruitment remains manual-recovery only; the first-round budget is checked now, later rounds may stop for insufficient resources. Limits include 32 cities, ten rounds, ten cycles, 200 submissions, and the existing 16 KiB configuration limit. Historical single-city engine API remains compatible. Actual game queue acceptance is not yet verified.

Verification: 43 focused Python tests, two recruitment Qt tests, 51 web unit tests and TypeScript passed. Fixed two OpenSpec archive/active status assertions and a Windows-specific path-separator assertion observed in hosted CI; 17 hygiene/recovery tests passed locally. No live game actions or deployment.


## Construction supply orchestration

Both clients support self-funded construction, send supplies then build, or send supplies only. Selected owned source cities are ordered; the engine calculates exact missing resources from the upstream construction calculator, optional upstream rounding, source inventory, destination space and real fleet capacity. A shortage not fully covered by the selected suppliers/storage blocks the ticket. The reviewed worker independently recomputes the plan, dispatches only the exact routes through the existing IkaBot shipment engine, rechecks ownership before each transport, and stops on uncertain dispatch. A combined job waits for actual sufficient destination stock (up to 24 hours after dispatch completes) and unchanged reviewed costs/targets before upgrading, with non-retried upgrade submission and observed building levels. Supply-only never upgrades. Supplied construction remains manual recovery; self-funded recovery remains unchanged. Full travel ETA is not verified, and the existing upstream shipping loop may wait for available transport/storage.

Focused construction tests: 12 passed, legacy engine construction suite: 26 passed, 27 subtests. Web suite: 52 passed; TypeScript and Ruff passed. Full preceding cce7085 controller regression: 776 passed, 11 skipped; engine: 412 passed, 9 skipped, 126 subtests. Linux and Windows hosted CI passed on that revision; Mac checks were queued. No live game actions or production deployment.


## Protected notification configuration

Desktop and web Settings now expose masked Telegram bot token/chat ID and Discord webhook inputs, with explicit worker-global consent and a separate clear action. Browser routes require the owner role. Upstream stores these provider defaults in global.json; legacy user-specific overrides take precedence, and a selected account with such an override fails closed for local reconciliation. Both clients encrypt to an ephemeral worker-held P-256 key with HKDF/AES-GCM and a one-use, identity/provider-bound 120-second ticket. Controller and BFF accept only the encrypted envelope. The worker makes a single bounded, direct TLS fixed-message provider test to an allowlisted host before replacement, with no redirects, raw provider responses or URL logging, then atomically writes the global default in a private file. The clear operation does not send a message. Upstream subsequent session writes also preserve private POSIX file mode. No provider credentials or production accounts were used in tests. Provider timeout or persistence failure requires a fresh status check; no automatic retry.

Nine focused Python tests passed, including browser WebCrypto/Python interoperability; web unit suite 53 passed and TypeScript passed. Existing proxy, challenge-provider and arbitrary extension/update boundaries are not approved or claimed implemented.


## Conditional first-load transport timing

Shipment and construction-supply previews now optionally query the read-only transport view using a verified owned port slot and exact origin/destination. The vendored getTransportLoadingAndTravelTime calculator supplies loading, travel and current port queue seconds using observed game parameters and selected fleet. Both clients show the bounded first-load estimate only when a single response view independently identifies the exact route and contains every required timing field. Missing, ambiguous or malformed observations remain unavailable. This is not a full multi-trip completion estimate, and no live-game response fixture or real account acceptance has been obtained.

Read-only view parameter reference: https://github.com/emelinhares/ikariam-builder/blob/master/ENDPOINTS.md (transport view); the timing arithmetic is the existing vendored IkaBot helper, not copied external implementation. Synthetic tests exercise the parser, freighter factor, malformed and mismatched scope rejection, and backend/web arithmetic guards.


## November 26: proxy deferral, modeled route delivery and exact cargo safety

The owner explicitly deferred proxy configuration. Nonsecret proxy status is retained; no new proxy writes are implemented. For a single owned-city route with the whole fleet free, sufficient verified storage and a complete first-load timing observation, the engine uses its existing transport calculator to estimate the final partial load and sequential full-fleet round trips. Both clients validate the model, show the conditional duration and distinguish it from an actual arrival guarantee. Shared fleet availability and dynamic port/storage conditions prevent a guaranteed multi-route completion time. A fresh source observation immediately before cargo reservation/POST prevents recording omitted or depleted stock. Focused transport, construction and fixed-transfer checks: 27 passed. No real game activity.


## Reviewed release discovery and diagnostics

Both Settings interfaces offer explicit read-only release lookup through a fixed public GitHub catalog endpoint. Only published preview tags with both expected uploaded project assets are returned; both clients validate exact link destinations. The worker/backend and packaged desktop build expose only a validated revision when available. No arbitrary URL, shell, cookie, environment dump, or automatic update is exposed. The existing authenticated controller is the remote service equivalent; legacy raw game-service start/stop and controlled production rollout/rollback are not claimed accepted. The Mac release remains unnotarized and the checksum is provided for user verification, not asserted verified locally.

Focused release/packaging/desktop/registry tests: 26 passed. Web suite: 55 passed. TypeScript, Ruff passed.


## Host-approved extension registration

Settings on both platforms can list a bounded host-installed approved catalog and register/unregister exactly one reviewed extension with explicit worker-global consent. The worker rechecks locally installed file hashes, rejects symlinks and unsafe POSIX permissions, compares the previously observed registration state, and preserves legacy registrations and unrelated global settings. Selected-account legacy overrides block changes. Source code and absolute paths are never transmitted. The browser owner role is required for mutation. Registration is not execution, installation or code deletion; host-local approval and review are required. Unreviewed legacy modules remain protected-local. A changed source file cannot be newly registered from the UI.

Verification: 13 focused extension and notification/admin tests, 11 desktop/registry tests, 56 web tests and TypeScript/Ruff passed. No actual host extensions were installed or registered.

## Human-controlled challenge policy

Managed piracy always stops upon a game challenge, regardless of legacy solver configuration. Both clients provide an account-scoped compare-and-set stop or notify-and-stop preference. Notify-and-stop requires a supported configured notification destination; the worker sends at most one fixed notice without challenge contents. No automated solver, solver credentials, answer submission or automated restart is exposed. Legacy local solver configuration is not migrated to the remote surface.

Verification: four dedicated policy, worker halt and authenticated controller tests passed; nine existing engine piracy tests passed; 57 web tests passed, TypeScript and Ruff passed.

## Research study submenu

Both native Research editors now distinguish existing experiments from named available advisor studies. The existing authenticated academy inventory optionally includes a bounded projection of the upstream advisor view; it exposes neither arbitrary AJAX requests nor HTML. The controller validates exact study configuration, the worker rechecks the current choice before start and before submission, and the existing upstream study action is submitted without transport-layer retry. No alternate study or experiment is inferred from a stale choice. Receipts record dispatch, not game-side research success. Real advisor responses remain subject to owner-operated acceptance. Existing experiment stock and cooldown behavior is retained.

Focused Python/Qt/engine study and experiment tests: 14 passed; web tests: 58 passed. Proxy deferral is independently tracked in issue #98.


## Fixed tavern servings, external-island monitoring and managed map reports

Both clients now expose the upstream tavern set-percentage action alongside equilibrium mode. Exact game-projected serving choices determine each selected city's current/target serving and wine consumption. The worker revalidates every reviewed row before dispatch, rechecks the current row before each non-retried submission, observes the resulting level and stops on ambiguity. One-time updates are not restored.

Island monitoring now selects verified external islands using the existing account-scoped lookup, including islands with no eligible external city. Both clients preserve explicit all-owned scope and invalidate failed or stale external selections. The controller accepts bounded coordinates rather than arbitrary island IDs; the existing engine resolves and verifies the actual coordinates again before launch.

Managed map scans now write only private account-bound aggregate reports, using server-owned report IDs and atomic owner-only files. They no longer write raw identifying world dumps or send filesystem paths to notification providers. Desktop Settings and web Activity list completed reports and export validated complete CSV pages, containing only coordinates, island ID, resource/wonder types, wood/luxury levels and occupied slots. Existing host-local legacy dumps and player/alliance searches remain outside this remote projection; the original local CLI behavior is preserved. A zero-radius regional scan selects only the stated center instead of the entire world. Storage is bounded at twenty completed reports per identity; a full store requires host-local reconciliation rather than deleting evidence automatically.

Focused tavern/island checks: 34 passed. Dedicated map export, engine dump and desktop registry tests: 17 passed, plus zero-radius regression passed. Web tests: 61 passed. TypeScript and Ruff passed. No live game actions or actual user report exports performed.


## Account-approved proxy profiles (deferral superseded)

The owner restored proxy configuration to scope. Both Settings interfaces now expose account-specific host-approved aliases, masked legacy status, explicit test and test-and-save controls. The authenticated controller and owner-only browser mutation route validate exact drafts. The worker loads a bounded owner-only manifest scoped by world/player identity, verifies idle managed and recorded processes, uses an opaque process-keyed revision, and makes a single fixed public HTTPS request with TLS verification, no redirects or game credentials before rechecking and saving the existing upstream account preference. Direct connection is available only when the host manifest explicitly permits it. Neither endpoint URLs nor proxy credentials are returned; profiles containing inline credentials are rejected, with authenticated upstream forwarding provisioned host-locally. No forced reconnect, automatic rotation, arbitrary endpoint probe or real game test is provided. Issue #98's original deferral is superseded; live validation and approval of the protected host-local provisioning boundary remain unperformed.

Verification: five focused worker/controller/Qt tests passed, including redaction, scope, stale revision, busy account, failed test and fixed TLS options. Web unit suite: 62 passed; TypeScript and Ruff passed. All network responses were mocked. No production network settings were changed.

## Reviewed daily rewards, distribution and market trades

Both native clients now obtain account-scoped worker observations before queueing or starting daily rewards, exact resource distribution, purchases or sales. The daily advisor supplies current favour, limit, reset and collectable count, not a guarantee of future rewards. Distribution validates exact routes, aggregate origin stock and destination storage and stops on changed allocation. Trade review calculates quantities and quoted gold and checks available purchase gold, current quotes and final purchase form prices. New reviewed listings require an empty market to avoid overwriting existing listings. The four operations use scoped expiring single-use tickets and independent multi-account queues; generic task launch cannot bypass them. No real game mutations were performed. Focused Python/Qt/engine suite: 55 passed before added integration tests; the eight dedicated reward/distribution/market tests pass, including controller account isolation and idempotent launch. Web: 64 passed, TypeScript and Ruff passed.

Manual macOS installation and real-account acceptance are owner-deferred in issue #60; automated build and deployment gates remain.

## Account-specific policy review expansion

Research, tavern, miracle, shrine and workshop workflows now issue independent account-bound review tickets from existing attested read-only inventories. Both clients validate observed selected cities, available studies, current crystal/cooldowns, exact fixed serving choices, current wine consumption, wonder availability, shrine favour or workshop current/target levels. The review is a current observation rather than a promise of future eligibility, costs or successful execution; existing worker preparation remains authoritative. Generic controller task launch cannot bypass the reviewed route. Focused Python/Qt tests: 60 passed; web tests: 65 passed; TypeScript and Ruff passed.

## Remaining recurring-operation review queues

The six additional native forms now require independently scoped expiring review tickets. Consolidation and transport show current stock, free storage and the selected fleet's capacity and free/total counts, and reverify external destination identity using the existing upstream helper. Donation policies show scoped current stock and named policy values. Monitoring resolves actual selected/owned islands; map reports check protected report capacity and expose only the existing aggregate export scope. Fortress review uses existing mission eligibility; the managed human-challenge stop remains mandatory. Both clients validate the bounded projections, reject generic launch and queue distinct accounts. Current inventory is not a promised future transfer, donation, route ETA or mission outcome. No game actions or provider requests were performed. The focused regression including API scope and idempotency tests passed 67 tests; web 66 passed; TypeScript and Ruff passed. The previous full controller run had one synthetic CLI lock collision (823 passed, 11 skipped); the test now uses a temporary lock directory and passes in isolation. Hosted Linux, Windows, web, engine, security and strict OpenSpec checks passed on abce0b2; the Mac runner was queued/in progress, with no new artifact yet. Final-revision CI and full regression, rollout and owner testing remain separate gates.
