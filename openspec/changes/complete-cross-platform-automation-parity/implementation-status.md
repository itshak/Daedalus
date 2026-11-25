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

The versioned capability manifest records 26 native workflows, existing read-only or managed-task views, protected local boundaries and pending adapters. Its committed JSON companion is checked against the upstream registry and the runtime manifest. Clients show unsupported workflows explicitly, rather than enabling them based on registration alone. All rows remain partial/pending, not live accepted.

Donation integration baseline: 705 Python tests passed, 11 skipped; 408 engine tests passed, 9 skipped, 123 subtests passed; 25 web tests, TypeScript, lint (warnings only), production build, Ruff and proposal validation passed. Worker/manifest focused regression: 33 Python tests passed; 27 web unit tests passed before the final manifest UI wiring. Full combined validation is required.

## Copy city building layout

The layout editor selects two different authenticated cities on the same account. It uses the original IkaBot move planner, checks both slot maps, rejects busy/missing/incompatible known slots, fingerprints the reviewed layouts, and presents the applicable swaps. The engine rereads both cities before dispatch and before one non-retried save request. No-op previews issue no ticket. This is a single target city per review and game acceptance must be verified; full multi-target parity is not claimed.

Focused layout/Qt/manifest regression: 31 Python tests passed. Web: TypeScript and 28 unit tests passed.

## New building construction

The new-building editor discovers actual empty-slot building choices through the upstream building-ground view. Both clients select a city and named building/slot, show the five-resource cost and eligibility, and use an account-bound, single-use review ticket. The worker checks the same slot and cost fingerprint at launch and again before one non-retried construction request. Unparsed prices, unavailable slots, busy cities and unaffordable construction are not launched. The building-ground parser still requires live acceptance on actual game responses.

Combined regression at worker/manifest commit 04aa845: 715 Python passed, 11 skipped; 408 engine passed, 9 skipped, 123 subtests passed; 27 web tests, TypeScript, production build, Ruff and proposal validation passed. Layout and new-building focused regression: 40 Python tests passed.

## Still open

Attack/automatic barbarian planning and the engine web-service workflow need audited adapters. Interactive menu-only operations, external-city transport, fleet capacity/ETA, authoritative effect previews beyond the construction slice, independently authored city-bound batch plans, full upstream option parity and shared versioned contracts are incomplete. Native browser/E2E, macOS installer and real-account acceptance remain unverified. Keep this change active; do not archive or mark the aggregate tasks complete.
