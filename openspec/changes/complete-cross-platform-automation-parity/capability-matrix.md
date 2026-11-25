# Operation-by-operation baseline and target

Baseline: main commit 49eb67e2e86934d86ddacf69053f421d1009c3c4; open PR #95 head 76fab112d08b618d774baa89fcf9ca30e2f2f8c2. This is a source review, not live acceptance. Sources: vendored command_line.py menu_actions (45 actions), resourceTransportManager @task (separate registered task), desktop task_page.py/task_presentation.py/native_controls.py and docs/AUTOMATION-UX-AUDIT.md, web control-center.tsx TASK_GROUPS/INVENTORIES and request-policy.ts/BFF route. checkForUpdate and show_proxy are auxiliary entries from existing audit, not counted as menu entries. The 46 core rows are the observed menu plus transport manager, not a claimed exhaustive AST scan; implementation must regenerate and compare inspect_engine() union and enumerate interactive submenus against this matrix.

Legend: D = desktop dedicated editor exists but full acceptance/gaps remain; E = expert/raw-plan or administrative gap on main (PR #95 removes raw override, not the missing adapter); R = read-only inventory/view; P = single-building read-only preview; P0 = catalog/preflight only; S = related existing screen or partial workflow, not full upstream action parity; M = missing dedicated workflow. No status means fully accepted. Web Automation explicitly disables dispatch for every action, even if proxy POST tasks is allowlisted. No raw JSON editor currently in web; do not add one. Every row must be closed by implementation, or by a reviewed, explicitly documented security-equivalent desktop/admin workflow for privileged operations.

| Operation | Desktop baseline | Web baseline | Required native controls and remaining work (both clients) |
|---|---|---|---|
| constructionList | D | P | City, ordered multiple building targets; cost, shortages, supply routes and queue ETA; verified launch |
| constructBuilding | M | M | City, vacant/eligible slot and building type, target level, cost/time, one-shot confirmation |
| research | D | R | Actual academies, experiment mode/count, crystal cost, cooldown, eligibility |
| modifyProduction | M | M | City/island, resource production workers, feasible range, production and cost before/after |
| modifyAcademyWorkers | M | M | Actual academy, worker count, available population and research/gold impact |
| modifyTempleWorkers | M | M | Actual temple, priest count, faith and population impact |
| reorganizeCityBuildings | M | M | Actual city layout and valid slots; keyboard reorder plus before/after confirmation |
| tavernManager | D | R | City/tavern table, consumption, population, wine reserve, cadence, balance and notifications |
| loginDaily | D | P0 | Real reward city selectors, favour checklist, collection switches and eligibility |
| activateMiracle | D | R | Owned temple/wonder, island, cooldown, activation count and schedule |
| activateShrine | D | R | Actual shrine/gods/favour, mode, times, interval and eligibility |
| sendResources | D | P0 | Repeatable source/destination city dropdowns, five resource amounts, ships/freighters, verified external destination search, capacity/ETA |
| resourceTransportManager | D | P0 | Consolidate/distribute mode, actual city selections, reserve/send amounts, fleets, interval and notification policy |
| consolidateResources | D | P0 | Source city checklist, target city dropdown, per-resource retained stock and fleet/interval |
| distributeResources | D | P0 | Resource, even/producers policy, owned cities, ships, calculated quantities and capacity |
| buyResources | D | R | Real trading post, resource, seller offer, quantity, budget, shipping, current quote |
| sellResources | D | R | Real trading post, buyers or offer creation, resource, stock, price, quantity, quote |
| donate | M | M | Owned city/island, eligible island project, current balance, amount and spend confirmation |
| donationBot | D | P0 | City/island project table, amount/percentage policy, retained stock, recurrence |
| trainArmy | D | R | Real barracks/shipyard, troop/ship types, quantities, costs, citizens, queue and repetitions |
| UpgradeUnits | D | R | Workshop city, actual unit upgrade options, current/target levels, resource/cost preview |
| stationArmy | M | M | Origin and verified destination city, actual troop/fleet selection, ship capacity, mission and ETA |
| viewArmy | R | R | Read-only troop/fleet tables, city filters, freshness and current/selected/all accounts |
| shipMovements | R | R | Read-only movement source, target, mission, hostile/returning state, counts, ETA and freshness |
| attackBarbarians | E | M | Owned origin, verified island and barbarian level, actual troops, available ships, upstream plan, explicit risk review |
| autoBarbarians | E | M | Verified islands, origin/float city, supported schematic, troops, fleet, schedule and notifications |
| autoPirate | D | R | Owned fortress, eligible missions, duration, day/night schedules, conversion policy, limits |
| alertAttacks | D | P0 | Polling interval, configured notification destination and readiness |
| alertLowWine | D | P0 | Threshold, actual city wine data, transfer switch, amount, reviewed route and notifications |
| searchForIslandSpaces | D | P0 | Owned islands and verified external lookup/map, interval, fight policy and observed results |
| dumpWorld | D | P0 | Coordinate bounds/radius, delay, filters, progress, cancel and safe export |
| getStatus | S | S | Account/world/session, city/task health, freshness and per-account errors |
| vacationMode | M | M | Account, authoritative eligibility, duration/consequences, explicit one-time confirmation |
| logs | S | M | Account/task scoped sanitized log viewer, filters, bounded paging/export; no secret fields |
| killTasks | S | S | Owned managed task selector, state and exact targeted stop; separate audited support for eligible unmanaged tasks |
| webServer | E | M | Restricted service state, approved bind/port choices, authentication/access checks, explicit start/stop; no public unauthenticated exposure |
| proxyConf | M | M | Masked proxy host/port/auth settings, supported protocol, connectivity test, explicit save/delete |
| decaptchaConf | M | M | Supported provider configuration, masked write-only secret, test/status; preserve human challenge where required |
| importExportCookie | S | S | Secure session import/export workflow via approved desktop/local handoff; web status and instructions, no raw cookie or token exposure |
| updateTelegramData | M | M | Masked write-only bot token/chat destination, validate/test/save/delete, configured status |
| testTelegramBot | M | M | Choose configured destination, send explicit bounded test, show result |
| updateDiscordData | M | M | Masked write-only webhook/destination, validate/test/save/delete, configured status |
| testDiscordBot | M | M | Choose configured destination, send explicit bounded test, show result |
| update | M | M | Current/available release, verified artifact, controlled deployment/rollback; no browser-triggered arbitrary shell |
| loadCustomModule | M | M | Reviewed installed extension list, provenance/signature, explicit admin enable/disable; no untrusted upload/execution in web |
| developer | M | M | Guarded diagnostics and reviewed developer actions; no arbitrary browser code/command execution |
| checkForUpdate | M | M | Auxiliary release check, version comparison and approved update workflow |
| show_proxy | M | M | Auxiliary masked proxy status and connectivity, never expose credentials |

## Implementation progress — expanded background slice (not accepted)

See [implementation-status.md](implementation-status.md) for current editors and local verification. The web now has 21 native operation editors (including one-time donation), including authoritative self-funded construction preview/launch, dynamic operation search and account-independent alert batches. The desktop player-first/native-only controls are integrated and tested offscreen. The baseline table above is intentionally retained as historical evidence rather than an acceptance claim. External cities, fleet capacity/ETA, full options, city-bound independent batches, interactive adapters, combat and web-service workflows remain open.

## Evidence and gaps

- Desktop has route matrix with source/destination ComboBoxes for own cities, actual resource quantities; external destinations and transport capacity/ETA remain incomplete. Construction already calculates self-funded preview; shortage sourcing and multi-account independent plans remain. Existing primitive/compound editors are reusable, not a reason to rewrite functioning code.
- Web has 22 static action entries, construction one-building preview, 11 read-only inventory mappings, and separate military/activity screens. No native task launch from the Automation panel. Generic object tables are not full editors. Catalog is not sourced dynamically from the registry.
- Web account display currently prefers email/name before player. Desktop main task selectors prefer imported label. PR #95 addresses desktop player names and removes raw editors; web requires equivalent player-first naming for automation only.
- Existing engine registry infers opaque structures as json; that metadata is not a UI schema. Current BFF launch schema accepts arbitrary config keys structurally; new routes must validate operation-specific drafts server-side, not rely on browser widgets.
- Existing pending OpenSpecs native-automation-workflows, redesign-macos-desktop-experience, apple-style-nextjs-web-control-center and delayed-session-reconnect-and-task-restoration must be reconciled. Do not archive work that remains unverified.


### Reviewed implementation coverage

See [capability-matrix.json](capability-matrix.json) for the versioned, machine-checked current coverage policy and [implementation-status.md](implementation-status.md) for evidence and limitations. The 29 native workflows include the newly reviewed one-shot donation, three worker-assignment operations, city-layout copy and new building construction. Native does not imply complete upstream option parity or live acceptance.
