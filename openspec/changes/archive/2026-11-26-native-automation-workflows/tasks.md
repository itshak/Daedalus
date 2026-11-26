# Implementation plan — all operation-specific native workflows

## Verified implementation slice (desktop + backend + existing-session engine)

- [x] Native group tabs and catalog with account/selected/all status viewing and account-specific execution guards.
- [x] Native construction building table, upstream cost/queue calculation and engine-side stale/shortage rejection (self-funded upgrades).
- [x] Own-city route editor, reserve/resource policy matrix, donation-by-city policy and optional map area/island controls.
- [x] Verified read-only workshop upgrade, troop/ship recruitment, academy, tavern, miracle, shrine, piracy fortress and market inventories with dedicated Qt editors.
- [x] Strict source-scoped API/client/IPC checks, no fabricated game IDs, and synthetic UI/engine tests for these native background workflows.
- [x] Run-time validation of current game unit resources, training costs, construction targets and exact current market quotes before relevant task dispatch.
- [x] Read-only viewArmy and shipMovements via account-bound existing-session IPC, validated HTTP DTOs and compact Troops/Fleet/Movements tables with All accounts scope; no game order path.
- [x] Keep automation review/launch controls in a visible native footer and remove nested guided-form vertical scrolling.
- [x] Hide unsupported free-form JSON parameters in guided mode; require explicitly reviewed expert configuration for unsafe/unimplemented tasks.
- [ ] Provide safe graphical configuration and independently reviewed dispatch plans for all remaining background operations and original interactive-only CLI functions.
- [ ] Live operator acceptance, accessibility snapshots and end-to-end combat/administrative workflows.

**Scope note:** Individual groups below are intentionally still unchecked when they
include items beyond the completed slice. See \`docs/AUTOMATION-UX-AUDIT.md\`
for exact supported and unsupported actions. Do not archive this proposal
while any checked product scope remains unresolved.

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
- [x] loginDaily: choose real wine/wood/luxury city reward destinations, reviewed favour-task checklist and collection switch; existing engine prepare validates owned IDs.
- [ ] loginDaily: reward eligibility and current state preview from upstream game data.
- [ ] activateMiracle, activateShrine: shrine/wonder identity, schedule and per-account readiness.

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

## Upstream waiting compatibility audit
- [x] Compare vendored gameplay waits with the original upstream import and inspect the current experimental CLI PR for principal queue helpers.
- [x] Consolidate duplicate fleet waits and reviewed supply arrival timing into upstream helpers.
- [x] Preserve audited read-only queue AJAX request forms on verified cookie sessions; test original training, workshop and miracle waiting implementations.
- [ ] Verify real successive fleet loads, recruitment rounds, workshop and construction queue progression on the deployed revision.

## Engine parity review
- [x] Compare the vendored engine definitions with the merged upstream CLI/IPC baseline and record the complete changed-module inventory.
- [x] Restore the upstream fleet timing helper and consolidate duplicated original request construction for building, layout, deployment and market resource selection.
- [x] Isolate bounded read-only form validation from gameplay logic and test original request shapes and preserved helper source guards.
- [ ] Finish individual verified-cookie integration and live acceptance for other state-changing operation POSTs; do not imply live coverage from read-only/parity tests.


## Military read regression verification (PR #109)
- [x] Add exact upstream `cityMilitary` form to the protected read adapter; reject extra fields and mismatched city IDs, retaining the upstream parser.
- [x] Add offline regression coverage through the original helper and real cookie-session transport; add military-specific client and backend diagnostics.
- [x] Verify deployed read-only inventory and movements endpoints against an existing authenticated account, including subsequent worker availability; owner confirmed the military feature works in the macOS GUI. No account identifiers, counts or runtime logs retained here.
- [ ] Separately verify updated diagnostic presentation in released desktop and web builds; this is not established by the successful inventory refresh.
- [x] Implement dedicated web troop/fleet row projection and tests instead of generic nested-object placeholders.
- [ ] Verify the new web rendering in the authenticated deployed interface.
