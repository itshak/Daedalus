# Upstream gameplay waiting audit — 2026-11-26

## Evidence and scope

Compared the AST of every Python function in the vendored game operation
directory against stable import commit `ab070fb` (public IkaBot stable
`3ea1e0e`). The later merged CLI/IPC baseline is `ba6aaba`; see
[the broader parity audit](UPSTREAM-ENGINE-PARITY.md). Audited 61 top-level
functions containing explicit wait/sleep calls; also inspected the warehouse
policy's class methods, shared transport helpers, session adapter and
controller waits. Spot-checked the public PR #499 revision `55d8877` for
transport, recruitment, workshop, construction, miracle, shrine, research,
tavern and recurring consolidation/transport waiting. This is a source and
offline test audit, not a live-game acceptance report.

## Registered operations (34 unique task names)

| Operation(s) | Waiting mechanism / disposition |
| --- | --- |
| sendResources, distributeResources, consolidateResources, fillCityWarehouse | Shared executeRoutes / waitForArrival / getMinimumWaitingTime |
| resourceTransportManager | Both consolidation and distribution now call shared waitForArrival; preserve upstream recurrence and lock timeout |
| constructionList | Original waitForConstruction, resource-arrival estimate from getMinimumWaitingTime; reviewed supply keeps independent stock recheck and 24h deadline |
| trainArmy | Original waitForTraining and planTrainings; reviewed recruitment calls the same wait before each round |
| UpgradeUnits | Original wait_for_upgrade_completion and wait_for_upgrade_start; all selected workshop tabs checked |
| buyResources, sellResources | Existing waitForArrival for available vessels; retain upstream market schedules |
| activateMiracle | Original wait_for_miracle and temple countdown |
| activateShrine | Upstream favour and grace-period schedules |
| research | Upstream experiment and multi-academy cooldown logic |
| loginDaily | Existing daily task timers and recurrence |
| tavernManager, donationBot, alertAttacks, alertLowWine, searchForIslandSpaces | Existing operation-specific check intervals; reviewed low-wine interval remains configurable |
| attackBarbarians, autoBarbarians, autoPirate | Existing mission-specific timing; no changes to their action logic |
| dumpWorld | Existing scan pacing; Event.wait is intentionally cancellable report-status infrastructure |
| modifyProduction, reorganizeCityBuildings | Existing upstream pacing between operations |
| constructBuilding, donate, modifyAcademyWorkers, modifyTempleWorkers, stationArmy, testDiscordBot, testTelegramBot, vacationMode | No replacement gameplay waiting loop introduced by the native adapters |
| webServer | Existing server lifecycle wait, not a gameplay queue |

The original `helpers/varios.py::wait` implementation is unchanged. Upstream
itself uses both that helper and direct time.sleep for different operations;
do not mechanically replace its already-working sleeps or use the fleet
advisor for unrelated queues. Preserve account recovery, UI/network timeout,
process registration, report cancellation, recurrence and lock timing as
separate infrastructure.

## Corrections

- Use the original upstream read-only military advisor AJAX request in
  fleet waiting, not the different full-page advisor response. Retain the
  full-page GET for the proven warehouse incoming-cargo observation.
- Restore the original upstream barracks, shipyard, workshop, temple,
  building-speedup popup and military-advisor read request shapes through
  a strictly bounded verified-cookie session adapter. Only exact read
  forms are admitted; no arbitrary write or relogin path is added.
- Remove the duplicate recurring transport manager availability polling loops.
- Use the existing upstream fleet arrival estimate plus wait in the new
  reviewed construction supply loop, keeping a bounded stock check if no
  event is known. Never equate elapsed time with verified delivery.
- Use upstream wait for the warehouse policy's short bounded independent
  incoming-cargo verification delay.

## Evidence and remaining acceptance gates

Offline tests execute the real shared fleet wait across three synthetic
loads, the actual upstream troop and ship recruitment waits, workshop
completion, miracle cooldown, and construction-supply arrival observation.
They also verify that malformed queue forms and extra action fields are
rejected, and protected reads do not invoke legacy login.

Production dc8e52b independently confirmed 81,500 incoming wood after
the first load, then exited during fleet waiting. The precise live failing
advisor field was not captured. Fleet return and subsequent loads need
real-world acceptance; recruitment, workshop, construction, research,
faith and other operation outcomes have not been established by this audit.
The audited read adapter does not certify all unrelated game writes.
