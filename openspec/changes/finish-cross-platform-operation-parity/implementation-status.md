# Successor implementation evidence

## Multi-island one-time shipments and generated launch contract

Native Qt and web shipment editors retain verified external city records with their original island coordinates across searches. Refreshing one island invalidates only its old recipients; a city found on a different island must be selected anew. Clear removes all external selections; account context resets the inventory. Up to ten islands are supported. The existing server ticket and worker recipient revalidation remain authoritative; no live game actions performed.

A generated TypeScript contract now derives supported draft task names, reviewed launch endpoints, ticket syntax, batch size and version from the Python manifest and reviewed endpoint map. Desktop start routing, web batch dispatch and BFF allowlists consume that map. A pytest drift check requires regeneration when the source changes. Full generated domain draft/preview/receipt schemas are still outstanding.

Baseline full local regression at 0a6d33d: 765 controller tests passed, 11 skipped; 412 engine tests passed, 9 skipped, 126 subtests. Archived 77a1638 passed 15 OpenSpec validation items. This follow-up: focused Qt shipment 3 passed; focused client/registry/batch/preview 37 passed; web unit suite 47 passed; typecheck and Ruff passed; lint 0 errors, 14 warnings. GitHub CI and live/Mac acceptance remain required. No production deployment.
