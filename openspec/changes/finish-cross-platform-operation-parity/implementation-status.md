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
