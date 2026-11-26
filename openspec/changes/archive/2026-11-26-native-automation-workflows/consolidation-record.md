# Consolidation disposition — 2026-11-26

Archived as superseded by the single engineering successor `finish-v010-engineering`, not as proof that unchecked tasks passed. Original task checkboxes remain unchanged. Codes are defined in [the reconciliation index](../../../../docs/V010-RECONCILIATION.md). V codes identify implementation or evidence already present for part/all of a historical task; where E or O also appears, the remaining portion is explicitly transferred. S identifies an obsolete sequencing requirement. No live acceptance is inferred.

| Original unchecked task (in order) | Disposition |
| --- | --- |
| 1. Provide safe graphical configuration and independently reviewed dispatch plans for all remaining background operations and original interactive-only CLI functions. | E1 |
| 2. Live operator acceptance, accessibility snapshots and end-to-end combat/administrative workflows. | E3; E5; O2; O5 |
| 3. Reconcile the main workspace tabs, gallery, account scope and contextual actions into a single compact responsive Mac layout; remove redundant visible controls. | V4; E5 |
| 4. Build a declarative, reviewed form/plan schema per task with versioned backend capability metadata and per-task adapters. | V5; E1 |
| 5. Add synthetic screenshot/a11y fixtures for 900x650, 1200x800, larger text, light/dark and VoiceOver. | E5; O5 |
| 6. Add read-only existing-session IPC for buildings, position/level/busy state, construction cost/time and queue; strict account+city membership. | V5; E1 |
| 7. Expose typed read-only contextual endpoints for resources, city production, academy, island/wonder/shrine, transport ships/routes, market, army, research, piracy, movements and available space as appropriate. | V5; E1 |
| 8. Enforce DTO schema, bounded result size, explicit observed_at/source, current account/world scope and stale invalidation on login/worker/backend changes. | E1; E3 |
| 9. Introduce upstream-powered read-only plan preview with exact task, account, city, plan fingerprint and revision/expiry. Validate again immediately before dispatch; no planning API may perform a mutating game action. | V5; E1 |
| 10. Extend tests for cross-account injection, stale views, unavailable IPC, no-auth sessions, unknown identifiers, planning side effects and secret-free errors. | V6; E3 |
| 11. constructionList + constructBuilding: real city selector, sortable building upgrade table, current/target levels, queue order, costs, resources, ship supply, ETA and review. | V5; E1 |
| 12. research: academies/cities, experiments, count/mode, crystal cost and cooldown preview. | V5; E1 |
| 13. tavernManager, alertLowWine: city table, wine level/threshold, recurrence, transfer plan and alert destination. | V5; E1 |
| 14. modifyProduction, modifyAcademyWorkers, modifyTempleWorkers, reorganizeCityBuildings: native, reversible controls and plan/confirmation appropriate to each operation. | V5; E1 |
| 15. loginDaily: reward eligibility and current state preview from upstream game data. | V5; E1 |
| 16. activateMiracle, activateShrine: shrine/wonder identity, schedule and per-account readiness. | V5; E1 |
| 17. sendResources, consolidateResources, distributeResources, resourceTransportManager: city/route matrix with resource quantity editors, ship type, recurrence, capacities and validation. | V5; E1 |
| 18. buyResources, sellResources: authoritative market offer/price tables, resource picker, budget and amount controls; no invented quotes. | V5; E1 |
| 19. donate, donationBot: island/project donation table, quantity and recurring schedule, explicit spend preview. | V5; E1 |
| 20. trainArmy, UpgradeUnits: units/buildings/levels table, training queues, city and repetition controls. | V5; E1 |
| 21. stationArmy, viewArmy, shipMovements: army selection, destination, current movements and nonsecret status views. | V5; E1; O5 |
| 22. attackBarbarians, autoBarbarians: islands, target level, troop composition, ship limits, schedule and risk review. | V5; E1 |
| 23. autoPirate: mission picker, day/night windows and frequency preview. | V5; E1 |
| 24. alertAttacks, searchForIslandSpaces, getStatus, dumpWorld: unit-aware intervals, actual islands/map coordinates, saved filters, safe export. | V5; E1 |
| 25. webServer, vacationMode, logs, killTasks: explicit lifecycle/status/stop safety and a distinct administrative workspace. | V5; E1 |
| 26. proxyConf, decaptchaConf, importExportCookie, updateTelegramData, updateDiscordData, testTelegramBot, testDiscordBot, update, checkForUpdate, loadCustomModule, developer: expert-only guarded, purpose-built setup or read-only panels. No arbitrary executable code in standard workflow. | V5; E1; O6 |
| 27. Audit every menu entry and @task operation against upstream source; update inventory when public IkaBot adds or removes functions. | V1 |
| 28. Add contract, service, Qt form, source-inventory, migration and engine-no-side-effect unit tests for each operation. | V6; E3 |
| 29. Run pytest, Ruff, strict OpenSpec validate and CI on the complete implementation; repair all failures. | V3; E6 |
| 30. Update canonical specs, GUI quick start and task-control docs after verification and archive only when verified. | V7; E6 |
| 31. Keep real-account, CAPTCHA, game outcome, live SSH/server migration and production approval assigned to the owner; no live credentials in tests. | O1; O6 |
| 32. Verify real successive fleet loads, recruitment rounds, workshop and construction queue progression on the deployed revision. | O2 |
| 33. Finish individual verified-cookie integration and live acceptance for other state-changing operation POSTs; do not imply live coverage from read-only/parity tests. | E1; E3; O2 |
| 34. Separately verify updated diagnostic presentation in released desktop and web builds; this is not established by the successful inventory refresh. | O5 |
| 35. Verify the new web rendering in the authenticated deployed interface. | O5 |
