# Implementation status — expanded native background workflows

Implemented on the integration branch (not yet accepted or deployed):

- Desktop PR #95: player-first account names and native-only reviewed settings, with opaque game fields no longer exposed as editable JSON. City-bound multi-account broadcasts are blocked by the desktop form and API worker. Only the two account-independent alert operations allow shared settings.
- Web: 20 background operation editors, including constructionList, sendResources, distributeResources, consolidateResources, resourceTransportManager, alertAttacks, alertLowWine, loginDaily, research, tavernManager, activateMiracle, activateShrine, donationBot, autoPirate, searchForIslandSpaces, dumpWorld, trainArmy, UpgradeUnits, buyResources and sellResources. Exact operation-specific BFF contracts replace generic raw payload entry; current city/academy/tavern/temple/fortress/unit/market options come from authenticated controller inventory where applicable.
- Construction: multiple ordered building targets, current/target levels, engine-calculated self-funded costs/shortages and ETA, explicit confirmation with a bounded, expiring, account-scoped opaque review ticket. Tickets are tied to one request ID; existing controller and engine revalidation/receipts remain authoritative.
- Web catalog: search and actual registered operation names, player-first account selection and Russian labels. Unimplemented actions remain informational, not falsely runnable.
- Alert batches: current, selected or all account scope; every account is checked before the first dispatch, separate request IDs and receipts, stop on uncertainty, no automatic retry. Disabled or missing accounts block a batch.
- Source registry/matrix coverage regression, native contract negatives, construction review scope/expiry/replay tests, and desktop account-scope regression.

## Local verification on aiserver

- Python main suite, Qt offscreen included: 701 passed, 11 skipped, 0 failed.
- Ruff: passed.
- Strict validation of this change: passed. Repository-wide strict validation previously reported seven existing spec/change failures due to long-requirement warnings.
- Web: 24 tests passed; TypeScript passed; ESLint passed with 14 warnings (0 errors); production Next.js build passed.
- No live game operations or production deployments were performed.

## One-time island donation slice

The `donate` menu action now also has an engine-owned structured task and dedicated Qt and web controls. Choose an owned city, forest or luxury-resource project and exact wood amount. The read-only preview reports live stock, project level and remaining contribution. The controller creates an account/operation-bound ticket; the worker rechecks the project fingerprint before dispatch and again before the single donation request. The generic task route cannot launch this operation without a ticket. A transport error does not retry the donation, and automatic recovery classifies it as manual. A started/finished task is not confirmation of the in-game contribution; verify the island balance. The legacy CLI donation path retains its original behavior.

Focused tests: four native donation/Qt tests, 17 session expiry/retry tests (12 subtests), 25 web tests and TypeScript passed. Full suites and new commit CI are additional gates. Native UI acceptance is still open.

## Reviewed worker assignments and coverage manifest

The three upstream worker operations (production, academy, temple) now have structured, city-scoped engine adapters and native desktop/web editors. The current project/building slider and normal/extra capacity are read from the game; the selected percentage is converted into an exact target. A one-shot ticket binds the operation and city to the reviewed slider state, and the child revalidates it before mutation. No raw game fields or automatic retry/replay. Population, production and faith impact estimates beyond the source slider are not inferred.

The versioned capability manifest records 30 native workflows, existing read-only or managed-task views, protected local boundaries and pending adapters. Its committed JSON companion is checked against the upstream registry and the runtime manifest. Clients show unsupported workflows explicitly, rather than enabling them based on registration alone. All rows remain partial/pending, not live accepted.

Donation integration baseline: 705 Python tests passed, 11 skipped; 408 engine tests passed, 9 skipped, 123 subtests passed; 25 web tests, TypeScript, lint (warnings only), production build, Ruff and proposal validation passed. Worker/manifest focused regression: 33 Python tests passed; 27 web unit tests passed before the final manifest UI wiring. Full combined validation is required.

## Copy city building layout

The layout editor selects two different authenticated cities on the same account. It uses the original IkaBot move planner, checks both slot maps, rejects busy/missing/incompatible known slots, fingerprints the reviewed layouts, and presents the applicable swaps. The engine rereads both cities before dispatch and before one non-retried save request. No-op previews issue no ticket. This is a single target city per review and game acceptance must be verified; full multi-target parity is not claimed.

Focused layout/Qt/manifest regression: 31 Python tests passed. Web: TypeScript and 28 unit tests passed.

## New building construction

The new-building editor discovers actual empty-slot building choices through the upstream building-ground view. Both clients select a city and named building/slot, show the five-resource cost and eligibility, and use an account-bound, single-use review ticket. The worker checks the same slot and cost fingerprint at launch and again before one non-retried construction request. Unparsed prices, unavailable slots, busy cities and unaffordable construction are not launched. The building-ground parser still requires live acceptance on actual game responses.

Combined regression at worker/manifest commit 04aa845: 715 Python passed, 11 skipped; 408 engine passed, 9 skipped, 123 subtests passed; 27 web tests, TypeScript, production build, Ruff and proposal validation passed. Layout and new-building focused regression: 40 Python tests passed.

## Station troops and fleet

The desktop and web clients now support reviewed deployment of all available ground troops or fleet units from one owned city to another. The engine reads current deployment inventory, validates both city identities, checks ground transport capacity, binds the cargo to an expiring account-specific ticket, and revalidates before a single submission. Synthetic tests cover stale inventory, insufficient capacity, account scope, ticket replay, and desktop confirmation. Individual unit allocation, ETA, external destinations, multi-origin orchestration and live-game acceptance remain outside this slice.

## Automatic barbarian preset

Both clients select an owned origin city and a city on the target island, display the current village level, named troop requirements and available/required ships, and offer optional configured notifications. The engine derives the upstream default non-Hephaestus schematic, verifies prerequisites, issues a scoped review ticket and rechecks the plan in the child. The legacy CLI contract is retained; automatic attack and looting submissions no longer replay uncertain transport failures. The current slice covers the existing level 1–39 preset with a non-destroyed starting village; manual wave editing, unsupported schematics, and live acceptance remain open. The recovery policy is manual rather than automatic replay.

At integrated revision 8a0a76f the full regression passed: 722 Python, 408 engine tests and 123 engine subtests, 29 web tests, typecheck/build/Ruff/OpenSpec (lint warnings only). Automatic attack focused tests: 7 engine/API/manifest/previous station tests, 1 Qt test and 31 web tests passed.

## Manual barbarian waves

Both clients load named available troops for an owned origin city, select the island of an owned target city, and edit up to eight ordered waves with troop quantities, requested loot ships and optional final looting. The engine reads village/ship/unit data, rejects invalid and overallocated waves, and produces a bound review ticket. It rechecks the draft before invoking the upstream attack routine. Reviewed waves refuse missing troops rather than silently reducing their quantities; game mutations do not replay uncertain transport failures. Both legacy and native task contracts are retained. Ship capacity is a conservative initial reservation; looting resources can change after combat and are calculated by the original engine. Live acceptance and larger wave counts remain unverified/unsupported.

Focused manual/automatic tests: 6 Python engine/API/manifest, 2 Qt, 32 web tests and TypeScript passed. Full latest-revision CI remains required.

## Vacation mode

Both clients implement account-wide vacation activation through an owned city identity, a preview and explicit confirmation. Active engine/managed jobs and enabled automatic recovery block ticket issuance; the controller and engine independently recheck before dispatch, the engine rejects concurrent managed starts, and the child rechecks active processes. The upstream activation request is submitted once without uncertain transport replay. The task is never captured as a desired job. Recovery must be manually disabled beforehand and kept disabled until the operator ends vacation; this slice does not automatically change recovery policy or claim verified game activation.

Focused vacation tests (engine/API/Qt) passed. Live vacation behavior and policy-change races across independent operators require acceptance review.

## Still open

The engine web-service and other protected administrative workflows need audited adapters. Interactive menu-only operations, external-city transport, fleet capacity/ETA, authoritative effect previews beyond the construction slice, independently authored city-bound batch plans, full upstream option parity and shared versioned contracts are incomplete. Native browser/E2E, macOS installer and real-account acceptance remain unverified. Keep this change active; do not archive or mark the aggregate tasks complete.

### Shipment outcome hardening

The shared cargo POST now disables automatic HTTP retries for both checkpointed and ordinary shipments. Only the existing explicit game rejection outcome permits a new attempt; malformed or unknown replies halt for manual reconciliation, and ambiguous checkpoint entries remain unresolved. Focused transport suite: 21 tests and 6 subtests passed. This does not implement the outstanding external-city UI or certify live shipment behavior.


### External one-time shipments and worker integration

Both clients' Send resources workflow now discovers eligible external cities by bounded island coordinates and displays actual city and player names in destination dropdowns. Origins remain owned. The engine binds external recipients to the observed island, city and owner identifiers, validates the recipient during prepare and immediately before each cargo POST, and rejects changed ownership or vacation state. Coordinate/account changes invalidate lookup choices. External shipments are not checkpointed or automatically restored. The existing own-city checkpoint contract remains unchanged. The account-worker router now explicitly forwards every reviewed operation's read methods to the correct worker; a regression covers this previously missing integration boundary.

Focused Python/engine/Qt tests: 58 passed, 6 subtests passed. Recurring external consolidation, multiple external island inventories in one form, fleet and ETA previews and live acceptance remain incomplete.


### Reviewed shipment capacity

Both native clients now request an account-specific read-only quote before approval. Current free/total fleet count, vessel capacity, source stock and destination storage (owned cities only) determine per-route first-load upper bounds and theoretical minimum full-fleet loads. All routes share the fleet; no completion time is promised. The server issues an expiring shipment ticket, binds the exact route draft and rejects the external-route generic launch bypass. Legacy owned-city launches remain compatible, including durable fixed-transfer journals. Engine preparation independently validates ownership, stock and external recipient identity. ETA remains unavailable because the upstream formula has no source-verified transport-view request supplying the required route-specific inputs. Synthetic capacity, API ticket and desktop review regressions passed.

### Native notification tests

Telegram and Discord each have a native fixed-message test workflow. Preflight checks the exact provider's configured credential shape without returning any secret. The worker accepts only official HTTPS endpoints, disables redirects, bounds the request timeout, suppresses automatic error notifications and never retries the provider request. Managed activity reports accepted or failed/uncertain based on process exit status. A 30-second per-account/provider cooldown limits repeated dispatch. Credentials remain shared by login; editing and pairing are not yet implemented. Synthetic focused tests: 49 passed; no real provider contacted.
