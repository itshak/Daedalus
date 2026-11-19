# Daedalus Automation UX — Complete IkaBot feature audit

**Status: active implementation; not production-complete.**

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
| Cities | `constructionList` | Real city picker; actual building table, target levels, cost/shipments/queue review | **Partial: picker, actual building table, draft targets; engine planner pending** |
| Cities | `constructBuilding` | One-shot building/level selector with cost preview | Designed; interactive-only adapter pending |
| Cities | `research` | Academy city list, experiments, crystal cost and cooldown | **Partial: actual city multi-select; experiment planner pending** |
| Cities | `tavernManager` | City list, check recurrence, wine balance/notifications | **Partial: city multi-select and interval; wine preview pending** |
| Cities | `loginDaily` | Actual city reward destinations and collection switches | Designed; reward eligibility pending |
| Cities | `activateMiracle` | Wonder/island selector, repetitions, cooldown | Designed; wonders data pending |
| Cities | `activateShrine` | Gods/shrines table with mode, count and timing | Designed; faith data pending |
| Cities | `modifyProduction` | Workers slider + hourly production forecast per city | Designed; interactive-only adapter pending |
| Cities | `modifyAcademyWorkers` | Scientists controls per academy | Designed; interactive-only adapter pending |
| Cities | `modifyTempleWorkers` | Temple priests controls | Designed; interactive-only adapter pending |
| Cities | `reorganizeCityBuildings` | Before/after drag-and-drop city slots | Designed; interactive-only adapter pending |
| Resources | `sendResources` | Route table with 5 resource amounts, ship capacity and live stocks | Designed; route preview data pending |
| Resources | `distributeResources` | Resource + even/producers policy + actual selected cities | **Partial: native controls and upstream preparation; shipment preview pending** |
| Resources | `resourceTransportManager` | Policy, source/destination cities, resource thresholds, check interval | Designed; dynamic policy schema pending |
| Resources | `consolidateResources` | Source/target city matrix, retained stock thresholds, ship choices | Designed; stock data pending |
| Resources | `buyResources` | Actual buy offers, quantity, price, gold and shipping | Designed; market quotes pending |
| Resources | `sellResources` | Sell-to-offer / list sale, price/amount/stock | Designed; market quotes pending |
| Resources | `donationBot` | Island project table, donation quantities and recurrence | Designed; island project data pending |
| Resources | `donate` | One-time project and resource contribution | Designed; interactive-only adapter pending |
| Military | `trainArmy` | Troop table, city, quantity and training queue | Designed; military data pending |
| Military | `UpgradeUnits` | Workshop unit upgrade table and targets | Designed; unit upgrade costs pending |
| Military | `attackBarbarians` | Island/target, army composition, ship count and risk review | Designed; combat planner pending |
| Military | `autoBarbarians` | Target cycle, troop template, capacity and notifications | Designed; combat planner pending |
| Military | `autoPirate` | Mission picker, pirate count and day/night schedule | Designed; pirate data pending |
| Military | `stationArmy` | Garrison origin/destination and troop send preview | Designed; interactive-only adapter pending |
| Military | `viewArmy` | Read-only garrison/unit table | Designed; interactive-only adapter pending |
| Military | `shipMovements` | Read-only movement route/ETA table | Designed; interactive-only adapter pending |
| Alerts | `alertAttacks` | Minutes polling interval + notification readiness | Existing basic native primitive control |
| Alerts | `alertLowWine` | Warning threshold in hours, opt-in transfer and amount | Existing basic native primitive controls |
| Alerts | `searchForIslandSpaces` | Island list/map, polling frequency and fight policy | Designed; island data pending |
| Alerts | `dumpWorld` | World coordinates, radius, scan filters and safe export | Designed; world data pending |
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

**Today, steps 1–2 and target-level draft controls of step 3 are implemented in the feature branch.** Steps 3–6 still require engine-side adapters. This is preferable to an apparently polished editor that silently launches malformed IkaBot tasks.

## Local verification once merged

Use a synthetic/demo backend to verify grouping, empty states, account switching, city picker, disabled construction start, native resource policy and read-only building failure. Use an explicitly authorized real session only for operator-owned testing of actual city/building values; normal automated tests must not log in, create child game tasks or guess game resources. Run the repository's source lint, offscreen Qt tests, IPC contract tests, OpenSpec strict validation and GitHub Actions before merge. Real-world behavior remains subject to the user’s later acceptance tests.
