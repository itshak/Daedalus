# Daedalus Automation UX — Complete IkaBot feature audit

**Status: native background-task implementation available on the feature branch; release blocked pending CI, merge and owner-operated live testing. Interactive CLI-only operations remain explicitly out of scope of automatic dispatch.**

This is the accessible index to the full [operation-specific design](../openspec/changes/native-automation-workflows/design.md), [OpenSpec proposal](../openspec/changes/native-automation-workflows/proposal.md) and [task-by-task implementation checklist](../openspec/changes/native-automation-workflows/tasks.md). It was built against Daedalus's vendored `engine/ikabot/ikabot/command_line.py`, the `@task` decorators and `prepare_*` functions, and the actual Daedalus account-scoped API. The IkaBot task registry is authoritative for which operations are executable; the menu catalog can include interactive-only actions that cannot be launched as background tasks.

## Immediate UX decisions

- **Primary menu:** All | City & research | Resources & trade | Military & missions | Alerts & exploration | System & advanced.
- **Account scope:** Current / Selected / All. Task-specific city IDs are never reused across accounts. Read-only statuses can include all configured accounts; execution uses explicitly approved account-specific plans.
- **Card layout:** Left searchable action list, right contextual configuration. No duplicated Wine/Construction task buttons, no default JSON field wall.
- **Task-specific affordances:** City picker, building upgrade table, route/resource matrix, academy experiment planner, tavern consumption controls, unit/recruitment table, active market offers, island target selector and time schedule fields. A small Advanced drawer can import previously prepared engine plans, with prominent provenance and validation.
- **Safety:** Display source and freshness of every game value. Distinguish unknown from zero, not connected from disabled, and known ready from game-server approved. No task starts merely by opening or editing a form. Preserve durable request IDs and unknown-outcome reconciliation.

## Feature-by-feature coverage

A row with **Designed, pending engine data** represents a *specified* UI but not a working native editor. This distinction is intentional.

| Area | IkaBot operation | Intended interface | Implementation status |
| --- | --- | --- | --- |
| Cities | `constructionList` | Real city picker; actual building table, target levels, cost/shipments/queue review | **Native: owned-city picker, live building rows and targets, read-only upstream costs/queue preview; only self-funded plans start after independent engine recheck** |
| Cities | `constructBuilding` | One-shot building/level selector with cost preview | Designed; interactive-only adapter pending |
| Cities | `research` | Academy city list, experiments, crystal cost and cooldown | **Native: account academy inventory, crystal/cooldown readiness and experiment controls; engine prepares experiment execution** |
| Cities | `tavernManager` | City list, check recurrence, wine balance/notifications | **Native: read-only tavern/wine/population table, explicit city coverage and recurrence** |
| Cities | `loginDaily` | Actual city reward destinations and collection switches | **Native: three owned-city reward pickers and favour checklist; eligibility preview remains pending** |
| Cities | `activateMiracle` | Wonder/island selector, repetitions, cooldown | **Native: current account-owned wonder/temple inventory, levels and cooldowns** |
| Cities | `activateShrine` | Gods/shrines table with mode, count and timing | **Native: shrine location/favour read and timed god selection** |
| Cities | `modifyProduction` | Workers slider + hourly production forecast per city | Designed; interactive-only adapter pending |
| Cities | `modifyAcademyWorkers` | Scientists controls per academy | Designed; interactive-only adapter pending |
| Cities | `modifyTempleWorkers` | Temple priests controls | Designed; interactive-only adapter pending |
| Cities | `reorganizeCityBuildings` | Before/after drag-and-drop city slots | Designed; interactive-only adapter pending |
| Resources | `sendResources` | Route table with 5 resource amounts, ship capacity and live stocks | **Native: own-city route and five-resource matrix; ship capacity/arrival preview pending** |
| Resources | `distributeResources` | Resource + even/producers policy + actual selected cities | **Partial: native controls and upstream preparation; shipment preview pending** |
| Resources | `resourceTransportManager` | Policy, source/destination cities, resource thresholds, check interval | **Native: source/destination city policies and resource amount controls; live capacity preview pending** |
| Resources | `consolidateResources` | Source/target city matrix, retained stock thresholds, ship choices | **Native: account source/destination and reserve matrix; live shipment capacity preview pending** |
| Resources | `buyResources` | Actual buy offers, quantity, price, gold and shipping | **Native: current owned-city trading-post offers and price bounds; engine rechecks quotes before trades** |
| Resources | `sellResources` | Sell-to-offer / list sale, price/amount/stock | **Native: current owned-city trading-post offers and price bounds; engine rechecks quotes before trades** |
| Resources | `donationBot` | Island project table, donation quantities and recurrence | **Native: city donation policies with method/recurrence; current island project preview pending** |
| Resources | `donate` | One-time project and resource contribution | Designed; interactive-only adapter pending |
| Military | `trainArmy` | Troop table, city, quantity and training queue | **Native: real account barracks/shipyard unit types, costs, quantity and citizen-budget checks; engine rechecks before dispatch** |
| Military | `UpgradeUnits` | Workshop unit upgrade table and targets | **Native: actual workshop upgrade types/current/target levels; independent engine preparation before dispatch** |
| Military | `attackBarbarians` | Island/target, army composition, ship count and risk review | Designed; combat planner pending |
| Military | `autoBarbarians` | Target cycle, troop template, capacity and notifications | Designed; combat planner pending |
| Military | `autoPirate` | Mission picker, pirate count and day/night schedule | **Native: account fortress mission eligibility, mission and day/night frequency controls; game outcomes require owner testing** |
| Military | `stationArmy` | Garrison origin/destination and troop send preview | Designed; interactive-only adapter pending |
| Military | `viewArmy` | Read-only garrison/unit table | Designed; interactive-only adapter pending |
| Military | `shipMovements` | Read-only movement route/ETA table | Designed; interactive-only adapter pending |
| Alerts | `alertAttacks` | Minutes polling interval + notification readiness | Existing basic native primitive control |
| Alerts | `alertLowWine` | Warning threshold in hours, opt-in transfer and amount | Existing basic native primitive controls |
| Alerts | `searchForIslandSpaces` | Island list/map, polling frequency and fight policy | **Native: actual owned-island coordinates and monitoring options; live free-space inventory pending** |
| Alerts | `dumpWorld` | World coordinates, radius, scan filters and safe export | **Native: bounded map-area coordinate/radius widgets and native scan filters** |
| Status | `getStatus` | Read-only account/city/task health | Designed; interactive-only view pending |
| Status | `logs` | Sanitized task log viewer | Designed; interactive-only panel pending |
| Admin | `webServer` | Advanced restricted service status/bind/port | Designed; hardening pending |
| Admin | `vacationMode` | Explicit one-time account confirmation with consequences | Designed; interactive-only adapter pending |
| Admin | `killTasks` | Managed task owner/stop table | Daedalus already has managed task Stop; menu action separate |
| Admin | `proxyConf`, `show_proxy` | Masked proxy settings and test | Designed; interactive-only adapter pending |
| Admin | `decaptchaConf` | CAPTCHA assistance provider configuration | Designed; human challenge still required |
| Admin | `importExportCookie` | Private session import/export with secure handoff | Designed; no plaintext JSON exposure |
| Admin | `updateTelegramData`, `testTelegramBot` | Masked Telegram settings and test | Designed; interactive-only adapter pending |
| Admin | `updateDiscordData`, `testDiscordBot` | Masked Discord settings and test | Designed; interactive-only adapter pending |
| Admin | `update`, `checkForUpdate` | Version and upgrade screen | Designed; interactive-only adapter pending |
| Admin | `loadCustomModule`, `developer` | Developer-only tools behind explicit trust boundary | Designed; never generic public task execution |

Some features appear only in the old IkaBot CLI menu; others appear as `@task` engine operations. This audit includes both, without falsely claiming all are currently dispatchable.

## Construction: accepted end-state

1. Select account and one of its actual cities.
2. See live building names, slot numbers, levels, construction state and eligible upgrades.
3. Set target level and order upgrades in a specialized table; request a read-only IkaBot preview.
4. Preview costs per wood/wine/marble/crystal/sulfur, missing materials, supply routes/ships, queue times, total ETA and account/world.
5. Resolve shortages or choose a safe policy and confirm exact game effects.
6. Launch with a durable per-account request ID only after authoritative plan preparation and fresh preflight; observe Running/History and reconcile uncertainty.

**Implemented now:** Steps 1–3 and the engine-calculated building costs, shortages and total queue duration in step 4 are supported. The UI refuses launch if the current city lacks required resources, and the engine independently re-prepares the plan before step 6. **Not implemented:** automatically sourcing material shortages, shipping supplies or providing a complete transport-ship ETA and revisioned expiry/fingerprint. The game's final construction outcomes have not been acceptance-tested by the owner.

## Local verification once merged

Use a synthetic/demo backend to verify grouping, empty states, account switching, city picker, disabled construction start, native resource policy and read-only building failure. Use an explicitly authorized real session only for operator-owned testing of actual city/building values; normal automated tests must not log in, create child game tasks or guess game resources. Run the repository's source lint, offscreen Qt tests, IPC contract tests, OpenSpec strict validation and GitHub Actions before merge. Real-world behavior remains subject to the user’s later acceptance tests.

## Remaining functional gaps / safe boundaries

- Combat planners (`attackBarbarians`, `autoBarbarians`) still require an independently prepared, correctly scoped game plan. The ordinary form does **not** request JSON or suggest that an unverified army can attack; these operations remain expert-only until read-only troop/risk/ship previews and revalidation are implemented.
- The `webServer` automation is administrative and retains an explicit expert setup/approval boundary; a secure native listener setup is not yet available.
- IkaBot's original interactive-only operations (single-building actions, production/scientist/priest controls, garrison/movement inspection, notifications, proxies, cookies, updater and developer tools) are **not** background tasks and cannot be safely launched through the task dispatcher. They require individually scoped read-only/interactive controller adapters and dedicated screens.
- Shipment capacity and external-island destination validation, donation project balances, academy eligibility refinements, daily reward eligibility, task preview TTL/fingerprint and multi-screen accessibility evidence are pending. They must not be presented as already supported.
- All game-changing tasks require explicit per-account review, the backend/engine's existing task preflight, and reconciliation of uncertain outcomes. Demo/synthetic tests do not constitute user acceptance or live Ikariam validation.
