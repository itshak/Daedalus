# Beta operation scope — 0.1.0

This is a source-backed option inventory, not a live support certification. Registry fields below are upstream task contracts, including hidden derived fields; they are not all editable or directly accepted as a raw launch payload. All 49 operations retain partial coverage or a protected-local boundary. Experimental legacy submission paths are not certified for cookie-only sessions. Do not assume a launch receipt establishes success or retry an uncertain outcome.

The reviewed desktop and web forms expose bounded selections; the upstream engine remains authoritative. Exact protected request parity is documented in [engine audit](UPSTREAM-ENGINE-PARITY.md), and generated contract drift is tested in `tests/test_cross_platform_parity.py`. Owner acceptance is [issue #60](https://github.com/itshak/Daedalus/issues/60).

| Operation | Registry fields / native controls | Beta scope and limits |
| --- | --- | --- |
| `activateMiracle` | `wonder`, `iterations` (derived), `island` (derived) | Reviewed wonder and iteration selection; bounded protected temple activation. Real cooldown and effect pending. |
| `activateShrine` | `godids`, `mode` (derived), `times` (derived), `selected_gods` (derived), `wait_time` (derived) | Reviewed god selection, mode and repetition; protected favor donation; other shrine paths retain upstream behavior and are experimental. |
| `alertAttacks` | `minutes` | Polling interval; requires configured notifications; delivery not live-accepted. |
| `alertLowWine` | `hours`, `auto_transfer`, `transfer_amount` | Threshold and optional transfer; transfer effect and long-running notification acceptance pending. |
| `attackBarbarians` | `city_id`, `target_city_id`, `waves`, `expected` (derived) | Reviewed city and target, bounded ordered waves; mission submission retains upstream path without a complete cookie adapter; experimental. |
| `autoBarbarians` | `city_id`, `target_city_id`, `send_notifications`, `expected` (derived) | Reviewed target and upstream preset; mission submission retains upstream path; experimental. |
| `autoPirate` | `pirateCount`, `pirateSchedule` (derived), `pirateMissionChoice` (derived), `pirateMissionDayChoice` (derived), `pirateMissionNightChoice` (derived), `dayStart` (derived), `dayEnd` (derived), `nightStart` (derived), `nightEnd` (derived), `autoConvert` (derived), `convertPerMission` (derived), `maxRandomWaitingTime` (derived), `piracyCities` (derived), `manual_challenge` (derived) | Mission/day-night schedule and human-stop challenge policy; no automatic challenge solver; mission/conversion paths remain experimental. |
| `buyResources` | `city`, `offers` (derived), `amount_to_buy` (derived), `reviewed_market` (derived) | Reviewed offer/quantity and live quote check; purchase submission retains upstream path; experimental. |
| `checkForUpdate` | Existing view / no settings | Read-only fixed project release catalog; no updater. |
| `consolidateResources` | `limits`, `sourceCityIds`, `destinationCityId`, `intervalInHours`, `shipType` | Owned sources and target, retain limits, interval and fleet selection; no automatic restoration of ambiguous effects. |
| `constructBuilding` | `city_id`, `position`, `building_id` (derived), `expected` (derived) | Owned eligible slot and building choice; protected original build submission; actual cost and building effect pending. |
| `constructionList` | `city_id`, `city_name`, `buildings`, `shipments`, `expand_overall`, `wait_resources`, `construction_queue`, `total_time`, `supply_review` | Owned city, targets and optional supply; build-only/supply-only/both; exact upgrade adapter; full multi-route ETA and optional speedup paths not certified. |
| `decaptchaConf` | Existing view / no settings | Human challenge policy only; automated solver configuration excluded. |
| `developer` | Existing view / no settings | Redacted diagnostics; no raw session/cookie dump. |
| `distributeResources` | `resource`, `mode`, `cities_ids`, `useFreighters`, `routes`, `reviewed_routes` (derived) | Reviewed distribution modes and allocations; no authoritative delivery guarantee or automatic replay. |
| `donate` | `city_id`, `project`, `amount`, `expected_island` (derived), `expected_level` (derived), `expected_donated` (derived), `expected_required` (derived) | Owned island resource/luxury project and amount; protected original donation submission; effect pending. |
| `donationBot` | `cities_dict`, `waiting_time`, `donate_method`, `cities_ids` (derived) | Reviewed policy by city, method and interval; recurring donation effect pending. |
| `dumpWorld` | `waiting_time`, `coords`, `radius` (derived), `shallow`, `non_empty_islands`, `show_progress` (derived), `managed_report_id` (derived) | Bounded area and aggregate report only; raw player data excluded; live scan completion pending. |
| `fillCityWarehouse` | `destination_city`, `resource`, `useFreighters`, `reviewed_sources` (derived) | One owned destination and resource; shared upstream cargo and fleet wait; checkpointed remaining cargo may restore after a verified reconnect (up to 40 reviewed sources); uncertain or legacy loads require review. |
| `getStatus` | Existing view / no settings | Managed account and task status, not raw process inspection. |
| `importExportCookie` | Existing view / no settings | Protected local handoff only; no web raw cookie import/export. |
| `killTasks` | Existing view / no settings | Managed task stop only; no arbitrary PID or kill-all. |
| `loadCustomModule` | Existing view / no settings | Host-approved hash-bound extension registration only; no remote code upload or execution. |
| `loginDaily` | `wine_city`, `wood_city`, `luxury_city`, `favour_tasks`, `collect_ambrosia` | Reviewed reward destinations, favor tasks and optional ambrosia collection; upstream collection/claim paths are experimental on cookie-only workers. |
| `logs` | Existing view / no settings | Bounded sanitized activity and receipts only; raw engine logs host-local. |
| `modifyAcademyWorkers` | `city_id`, `percentage`, `expected` (derived), `additional_city_ids` | Verified academies and percentage across selected owned cities; protected assignment; effect pending. |
| `modifyProduction` | `city_id`, `percentage`, `project`, `overcharge`, `expected` (derived), `additional_city_ids` | Verified forest, luxury or both projects, percentage and overcharge; protected assignment; effect pending. |
| `modifyTempleWorkers` | `city_id`, `percentage`, `expected` (derived), `additional_city_ids` | Verified temples and percentage across selected owned cities; protected assignment; effect pending. |
| `proxyConf` | Existing view / no settings | Host-approved network profiles only; arbitrary endpoint or credentials excluded. |
| `reorganizeCityBuildings` | `city_id`, `template_city_id`, `expected` (derived) | Owned template and target city only; protected layout submission; effect pending. |
| `research` | `cities_ids`, `qty` (derived), `mode` (derived), `experiments` (derived), `automatic` (derived), `cities` (derived), `info` (derived), `study_choice` (derived) | Study selection has protected request parity; repeated academy experiment paths retain legacy submission and remain experimental. |
| `resourceTransportManager` | `mode`, `origin_cities`, `destination_city`, `island` (derived), `interval_hours`, `resource_config`, `useFreighters`, `send_mode`, `notify`, `origin_city`, `destination_cities`, `info` (derived), `telegram_enabled` (derived), `notify_on_start` (derived), `recipient` (derived) | Reviewed recurring owned/external allocations; no generic replay or automatic restoration of unobservable transfers. |
| `searchForIslandSpaces` | `time`, `islandList`, `fights` | Reviewed coordinates or owned islands, notification checks; live monitor acceptance pending. |
| `sellResources` | `mode`, `amount_to_sell` (derived), `offers` (derived), `resource_type` (derived), `city_to_buy_from` (derived), `price` (derived), `sell_market_capacity` (derived), `city` (derived), `reviewed_market` (derived) | Reviewed existing buyers or offer creation, stock/price constraints; submission retains upstream path and is experimental. |
| `sendResources` | `routes`, `useFreighters`, `transfer_id` | Reviewed routes and fleet choice, bounded external lookup; only confirmed owned fixed cargo is eligible for automatic missing-work recovery. |
| `shipMovements` | Existing view / no settings | Account-scoped read-only movement inventory; actual values pending owner comparison. |
| `show_proxy` | Existing view / no settings | Read-only approved profile status; no credentials. |
| `stationArmy` | `city_id`, `destination_city_id`, `ground`, `expected` (derived), `all_origins`, `both` | Reviewed owned origin/destination, all ground/fleet or both; deployment write retains upstream path and is experimental. |
| `tavernManager` | `run_hours` (derived), `cities_ids`, `cities` (derived), `notification_mode` (derived), `check_now` (derived), `fixed_servings` (derived) | Equilibrium or fixed serving mode; bounded run duration and verified cities; fixed wine setter protected; recurring result pending. |
| `testDiscordBot` | Existing view / no settings | One fixed message, protected configured provider; delivery pending. |
| `testTelegramBot` | Existing view / no settings | One fixed message, protected configured provider; delivery pending. |
| `trainArmy` | `city`, `tranings` (derived), `trainTroops` (derived), `replicate` (derived), `countRepeat` (derived), `cityTrainings` (derived), `units` (derived), `reviewed_jobs` (derived) | Reviewed owned city, unit/fleet inventory, ordered rounds and repeats; protected recruitment; actual queue and resource effects pending. |
| `update` | Existing view / no settings | Reviewed release instructions only; no automatic engine update. |
| `updateDiscordData` | Existing view / no settings | Write-only encrypted worker-global default; legacy overrides require local reconciliation. |
| `updateTelegramData` | Existing view / no settings | Write-only encrypted worker-global default; legacy overrides require local reconciliation. |
| `UpgradeUnits` | `jobs` | One owned workshop, bounded offensive/defensive upgrades; protected write and stop on unobserved queue; actual completion pending. |
| `vacationMode` | `city_id`, `expected` (derived) | Explicit review and existing stop/recovery safeguards; activation retains upstream path and remains experimental. |
| `viewArmy` | Existing view / no settings | Read-only troop/fleet inventory; physical owner comparison pending. |
| `webServer` | `port`, `local_network_ip` | Daedalus gateway instead of raw IkaBot service; arbitrary port/network listener excluded. |

## Release boundary

The beta candidate retains existing reviewed editors, including experimental operations, without claiming complete protected-worker compatibility. Market writes, reward collection, mission/deployment writes, vacation activation, some shrine/research subpaths and optional construction speedups still require engineering review of the original request paths. No new generic game proxy or mutation adapter is introduced for these. Treat those paths as unsupported for the first beta until separately validated. The current engineering change remains open for those code gaps; the owner checklist does not silently convert unfinished engineering to passed tests.
