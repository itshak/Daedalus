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
