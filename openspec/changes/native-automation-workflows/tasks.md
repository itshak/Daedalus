# Implementation plan — all operation-specific native workflows

## Foundation / navigation
- [x] Replace duplicated category/template strip with a consistent category tab selection without changing canonical task identity.
- [x] Fetch real account-scoped city options asynchronously and use them for construction city + paired city name.
- [x] Explicitly block broadcasting one city's construction plan to multiple accounts.
- [x] Add deterministic offline tests for city picker selection, isolation and group filtering.
- [ ] Reconcile the main workspace tabs, gallery, account scope and contextual actions into a single compact responsive Mac layout; remove redundant visible controls.
- [ ] Build a declarative, reviewed form/plan schema per task with versioned backend capability metadata and per-task adapters.
- [ ] Add synthetic screenshot/a11y fixtures for 900x650, 1200x800, larger text, light/dark and VoiceOver.

## Authoritative reads / previews
- [ ] Add read-only existing-session IPC for buildings, position/level/busy state, construction cost/time and queue; strict account+city membership.
- [ ] Expose typed read-only contextual endpoints for resources, city production, academy, island/wonder/shrine, transport ships/routes, market, army, research, piracy, movements and available space as appropriate.
- [ ] Enforce DTO schema, bounded result size, explicit observed_at/source, current account/world scope and stale invalidation on login/worker/backend changes.
- [ ] Introduce upstream-powered read-only plan preview with exact task, account, city, plan fingerprint and revision/expiry. Validate again immediately before dispatch; no planning API may perform a mutating game action.
- [ ] Extend tests for cross-account injection, stale views, unavailable IPC, no-auth sessions, unknown identifiers, planning side effects and secret-free errors.

## Domain workflows: city / research / production
- [ ] constructionList + constructBuilding: real city selector, sortable building upgrade table, current/target levels, queue order, costs, resources, ship supply, ETA and review.
- [ ] research: academies/cities, experiments, count/mode, crystal cost and cooldown preview.
- [ ] tavernManager, alertLowWine: city table, wine level/threshold, recurrence, transfer plan and alert destination.
- [ ] modifyProduction, modifyAcademyWorkers, modifyTempleWorkers, reorganizeCityBuildings: native, reversible controls and plan/confirmation appropriate to each operation.
- [ ] loginDaily, activateMiracle, activateShrine: city reward destinations, shrine/wonder identity, schedule and per-account readiness.

## Domain workflows: resources and trade
- [ ] sendResources, consolidateResources, distributeResources, resourceTransportManager: city/route matrix with resource quantity editors, ship type, recurrence, capacities and validation.
- [ ] buyResources, sellResources: authoritative market offer/price tables, resource picker, budget and amount controls; no invented quotes.
- [ ] donate, donationBot: island/project donation table, quantity and recurring schedule, explicit spend preview.

## Domain workflows: military / adventure
- [ ] trainArmy, UpgradeUnits: units/buildings/levels table, training queues, city and repetition controls.
- [ ] stationArmy, viewArmy, shipMovements: army selection, destination, current movements and nonsecret status views.
- [ ] attackBarbarians, autoBarbarians: islands, target level, troop composition, ship limits, schedule and risk review.
- [ ] autoPirate: mission picker, day/night windows and frequency preview.

## Domain workflows: monitoring / system
- [ ] alertAttacks, searchForIslandSpaces, getStatus, dumpWorld: unit-aware intervals, actual islands/map coordinates, saved filters, safe export.
- [ ] webServer, vacationMode, logs, killTasks: explicit lifecycle/status/stop safety and a distinct administrative workspace.
- [ ] proxyConf, decaptchaConf, importExportCookie, updateTelegramData, updateDiscordData, testTelegramBot, testDiscordBot, update, checkForUpdate, loadCustomModule, developer: expert-only guarded, purpose-built setup or read-only panels. No arbitrary executable code in standard workflow.
- [ ] Audit every menu entry and @task operation against upstream source; update inventory when public IkaBot adds or removes functions.

## Release gates
- [ ] Add contract, service, Qt form, source-inventory, migration and engine-no-side-effect unit tests for each operation.
- [ ] Run pytest, Ruff, strict OpenSpec validate and CI on the complete implementation; repair all failures.
- [ ] Update canonical specs, GUI quick start and task-control docs after verification and archive only when verified.
- [ ] Keep real-account, CAPTCHA, game outcome, live SSH/server migration and production approval assigned to the owner; no live credentials in tests.
