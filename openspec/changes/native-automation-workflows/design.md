# Domain UI design and engine integration contract — native automation workflows

## Source of truth and coverage

This design is based on the bundled engine's `ikabot/command_line.py` menu table, `ikabot/function/*.py` task-decorator signatures, the existing `src/daedalus/engine_registry.py` AST inventory, and the existing Daedalus API/IPC and PySide6 task page. Its task names are **canonical engine names**, not invented public actions. The inventory is dynamically reconciled with the backend's supported catalog; a static design row alone **never** authorizes dispatch.

The existing backend can enumerate an account's actual `id/name/coords/tradegood` cities using `GET /api/v1/accounts/{id}/cities`; it cannot yet enumerate real building positions/levels, resource production policies, units, market offers, academy state, wonders or task-specific cost previews. Those require additional audited existing-session reads. We must not pretend that a JSON argument called `city` is a usable city ID; some upstream tasks expect a full city dictionary or prepared plan.

## Information architecture

### Primary Automations workspace

1. A *single* persistent account scope selector (One account / Selected accounts / All accounts) with world and session readiness; changing scope invalidates draft and preview for any mismatched identity. For stateful operations, Selected/All switches to per-account queueing of individual drafts, never shares raw city IDs or prepared arrays.
2. One horizontally navigable category tab row, not a pivot plus redundant category ComboBox plus featured-template buttons: **City & research**, **Resources & trade**, **Military & missions**, **Alerts & exploration**, **System & advanced**. Include **All** and accessible keyboard tab navigation. Tabs filter a searchable catalog with canonical names and availability indicators. Search can scan across categories.
3. Selecting an action opens a focused *Configure* workspace. First show a friendly one-paragraph explanation and needed prerequisites, then grouped semantic controls. No wall of generic parameters; every field has a natural unit, data origin and validation. The last row is a compact *Review changes* + *Start* flow, not a Start command hidden below a huge QScrollArea.
4. **Running** and **History** remain independent navigation states but retain the same account scope. Running shows stop only for Daedalus-owned child task IDs. History exposes reconciliations separately and preserves ambiguous request receipts without relaunch.
5. **Advanced import** is a deliberate optional tab/drawer with a typed preview of the original engine parameters for experts; it never overrides a reviewed native draft without a clearly visible mode change.

### Shared widgets

- **AccountScopeBar**: world/flag, account nickname, grouped account chip with distinct per-account readiness. Selection is account ID scoped and backed by authenticated `accounts` plus session status.
- **CityPicker**: searchable actual `cities` list, displays name, coordinates, luxury resource; stores integer ID but never exposes it as a user-editable field. One selected city defaults to *Choose a city*, not the first city. Multi-selection only when that task's engine adapter explicitly accepts IDs or per-account plan.
- **BuildingUpgradeTable**: one row per authoritative `city.position` record: building name, slot, current level, busy state and end time if observed, target level spinbox, priority order, material and ETA preview; drag reorder, remove/duplicate safeguards, “all eligible” only when backed by actual snapshot. A backend-prepared upstream plan contains `buildings`, `shipments`, `expand_overall`, `wait_resources`, `construction_queue`, `total_time`. No local game formula or guessed `constructionTimes`.
- **RouteGrid**: source city/target city selectors, resources as five quantity columns, ship mode, available capacity and duration from server; add/remove/clone rows, inline validation of source != target and account scope.
- **ResourceQuantity**: five canonical resources wood, wine, marble, crystal/glass, sulfur from upstream constants with account-specific availability and known/unknown semantics; limit/all buttons only with verified stocks. Never conflates unknown and zero.
- **ScheduleEditor**: single run or interval, hourly ranges or day/night windows as appropriate, time zone explicitly indicated when sourced from server. Contextual presets only if upstream task semantics are verified.
- **ArmyCompositionTable**: authoritative unit types and current army, desired quantities or training increments, recruitment building, duration/resource estimate, grouping land/naval.
- **MarketOfferTable**: live quotes with price/quantity, source island/city, max legal transaction and trade cost. Quotes expire; no stale market transaction.
- **RiskReview**: concise account/world, affected city or destination, values and state-changing effects, warnings, snapshot age and confirmation. Don't print credential/raw game HTML or echo arbitrary parameter strings.

## Operation-by-operation UX specification

The names below correspond to built-in background `@task` operations; display labels are local-only. `Data needed` always means a new bounded account-scoped read or upstream-prepared result unless explicitly marked existing-city API.

### City management, construction, research, faith and production

| Engine operation | Native editor (user's mental model) | Required authoritative reads and conversion |
| --- | --- | --- |
| `constructionList` | Pick a real city; building table with current and target levels, per-building priority and cost/time; shortages, supply-city selector and dispatch summary; start exactly the reviewed ordered queue | Existing cities API for ID/name; NEW building slots/levels/busy/cost/reducers/resources/time snapshot and upstream construction planner preview; lower to exact 8-arg prepared task structure; preview must fail closed |
| `research` | Choose academies/cities; research mode; crystal experiments table with quantity or automatic mode, cooldown and cost; run schedule | Existing city IDs for scope; NEW academy positions, crystal stock/cooldown, research advisor and upstream `prepare_research`; submit optional `cities_ids/qty/mode/experiments/automatic` only from validated preview |
| `tavernManager` | Choose all/selected tavern cities, check interval (0 = once), initial check switch, notification choice; optional wine budget/forecast view | Existing cities + NEW tavern occupancy/wine consumption/serving levels, reviewed notification enum; source-validated `run_hours` and supported city filtering; never invent `cities` objects |
| `loginDaily` | Pick wine/wood/luxury reward destinations with three actual city pickers, collection toggles, one-time run summary | Existing city IDs, NEW reward eligibility/current state; map `wine_city/wood_city/luxury_city/favour_tasks/collect_ambrosia` via upstream `prepare_loginDaily`; no invented reward |
| `activateMiracle` | Wonder selector with discovered wonder type, island and level, desired iterations and trigger | NEW island wonders and miracle cooldown; upstream documented `wonder` codes and eligible island, never pretend any island qualifies |
| `activateShrine` | Shrine/wonder selection table, activation mode, repeat count, wait schedule, cooldown preview | NEW god/wonder IDs, valid shrine state and mode enumeration; serialize `godids/mode/times/selected_gods/wait_time` only from compatible upstream data |

Interactive-only menu functions in this group:
- `constructBuilding`: one-shot building picker + target level, availability and cost; needs reviewed controlled operation adapter, not merely a task called `constructionList`.
- `modifyProduction`: city resource production sliders with min/max and currently employed workers; submit changes per-city, preview resulting delta.
- `modifyAcademyWorkers`: academy staffing spinbox/slider, current/max scientists and cost warning.
- `modifyTempleWorkers`: temple priest allocation, faith effect and cooldown; task-specific confirmation.
- `reorganizeCityBuildings`: draggable city building slots, before/after plan and hard stop on unsupported moves.
- `getStatus`: read-only city task status cards, current upgrades and economy; no start control.

### Resources, transport, trade and donations

| Engine operation | Native editor | Required reads / exact preparation |
| --- | --- | --- |
| `sendResources` | Route table with actual source+destination cities (or verified external island), five resource amounts, ship types, capacity, add/remove/edit lines and final shipment review | Existing city API + NEW available ships, active movements, stocks and external destination lookup; reviewed `routes` objects with `from/to/resources` and optional `island`; `prepare_sendResources` |
| `resourceTransportManager` | Choose transfer strategy (auto/manual), source/destination scope; resource policy matrix; check interval, ship type, notification toggle | Existing cities + NEW upstream mode enums, `resource_config` schema, route capacity and `prepare_resourceTransportManager`; don't guess `mode` or task fields |
| `consolidateResources` | Select many source cities and one target; per-resource retain thresholds; frequency and ship mode | Existing cities + NEW inventory, `limits` semantics, ship availability; construct `sourceCityIds/destinationCityId` and limits from reviewed source |
| `distributeResources` | Choose resource, even/custom policy, multi-city distribution table, per-route preview and freighter toggle | Existing cities + NEW stock levels, valid policy modes and ship resources, upstream `prepare_distributeResources` |
| `buyResources` | Market search with resource, actual available offers, quantity, max price, available gold and transport costs; explicit buy summary | NEW market offers and verified `city` structure, `offers`, `amount_to_buy`; prevent stale quote and compare revision before mutation |
| `sellResources` | Sell to a verified buy offer or list a sale; quote table, price/amount, stock and capacity limits | NEW local markets/offers, `mode`, `resource_type`, `city` and sell limits; reviewed engine mode semantics |
| `donationBot` | Owned island and donation project table, target amount/strategy/recurrence; summary of exact donated resources | NEW island resource project, project level/current donations, city membership, `cities_dict`/method semantics; no defaults fabricated |

Interactive-only menu:
- `donate`: one-off island contribution with wood amount, available stock, resulting project progress and confirmation.
- `shipMovements`: read-only table of current ships, arrival ETA and origin/destination; optional upstream-supported actions only when separately authorized.

### Alerts, exploration, account and world reporting

| Engine operation | Native editor | Required reads / preparation |
| --- | --- | --- |
| `alertAttacks` | Poll interval (minutes), notifications availability state, selected scope and preview of how notification delivery works | Already supported `minutes=20`; existing authenticated task preflight checks Telegram/Discord; no need for opaque JSON |
| `alertLowWine` | Number-of-hours low-wine threshold, wine transfer enable, amount if on, optional monitored-city table | Existing reviewed primitive controls + NEW wine consumption/stock/city health for preview; notifications readiness from preflight |
| `searchForIslandSpaces` | Island search target chips (owned islands or verified coordinates), interval, barbarian fight filter, output notification preview | NEW island identities/spaces with validated `islandList`, source-reviewed `time/fights` semantics |
| `dumpWorld` | Map selector/center/radius, shallow scan and nonempty filters, safe polling rate and export location | NEW valid world coordinate bounds, source-reviewed `coords/radius/waiting_time`; no cross-account world leakage |

Interactive-only:
- `viewArmy`: read-only grouped units/location table.
- `getStatus`: grouped status summary.
- `logs`: safe bounded local task history (avoid raw secret-bearing logs).
- `checkForUpdate` / `update`: explicit version check and administrative update flow; never mix with world operations.

### Military, barbarians and piracy

| Engine operation | Native editor | Required reads / preparation |
| --- | --- | --- |
| `trainArmy` | City, troop/unit table, training quantities, queue and repeat count; available barracks/shipyard and estimated resources | NEW unit type inventory and city military buildings, `tranings/trainTroops/replicate/countRepeat/cityTrainings/units` semantics; typo `tranings` preserved only on engine wire |
| `UpgradeUnits` | Smithy/research upgrade table by unit, target upgrade level, city of execution, cost and queue | NEW unit-level facts, eligible workshop/city, `jobs` with `city_id/upgrades[{unitId,upgradeType,target}]` per upstream `prepare_UpgradeUnits` |
| `attackBarbarians` | Island target and level, selected origin city, army composition table, estimated ships and risk confirmation | NEW verified barbarian island/camp info, ship capacity, combat plan; use `island/city/babarians_info/plan/ship_capacity` from upstream planner |
| `autoBarbarians` | Barbarian schedule, target island/level, replenishment/army template, automation limits and notifications | NEW same military data, ship capacity and upstream `schematic/float_city/units_data`; never autofill hypothetical armies |
| `autoPirate` | Pirate fortress selector, missions picker, schedule with day/night time windows and count, limits and risk note | NEW pirate missions/fortress availability, upstream choices and timezone; `pirateCount/pirateSchedule/...` reviewed by `prepare_autoPirate` |

Interactive-only:
- `stationArmy`: actual origin/destination selector, troop amounts, garrison transport costs and explicit send confirmation.
- `viewArmy`, `shipMovements`: read-only dashboards, not fake background tasks.

### System, advanced and administration

| Engine operation | Native editor | Boundary |
| --- | --- | --- |
| `webServer` | Advanced service status, desired bind address and port with loopback-only default, control and warnings | Highly sensitive network exposure: explicit auditing and service permission required; no public IP by default |

Interactive-only:
- `vacationMode`: high-friction account scope, consequences and explicit user consent; no background automation.
- `killTasks`: show only verified managed engine task IDs; support safe stop, never arbitrary PID kill.
- `proxyConf`: private, masked proxy config and local validation, never send credentials to general task endpoint.
- `decaptchaConf`: CAPTCHA-assistance settings with human-required challenge; never promise bypass.
- `importExportCookie`: separate secure session recovery/import/export interface, no raw cookie in task planner.
- `updateTelegramData` / `updateDiscordData`: separate encrypted notification-settings cards; show configured/verified only, not tokens.
- `testTelegramBot` / `testDiscordBot`: explicit “Send test notification” with exact account/recipient review.
- `loadCustomModule` / `developer`: expert-only code execution boundary, never make runnable through generic untyped `@task` dispatch.
- `update`, `checkForUpdate`: installation/update screen with version, provenance and rollback guidance.
- `logs`: sanitized task logs with redaction; no shell access.
- `getStatus`: read-only summary, ideally reused in Overview rather than an extra automation card.
- `show_proxy`: read-only masked status within proxy settings.

## State, security and execution semantics

Each native editor has four independent phases: **Choose scope**, **Load live choices**, **Prepare/preview**, **Confirm/dispatch**. On switching backend URL/account/world/session owner/task, invalidate all pending previews, form approval, live selection and queued responses. No auto-triggered game action when opening tabs, choosing cities or refreshing snapshots. State-changing tasks remain locked until an exact native plan can be built and server+engine independently accept it.

Previews and DTOs SHALL have a bounded observation/revision identifier, account ID, world identity and timestamp. The backend SHALL enforce snapshot ownership and freshness itself; do not trust GUI-provided city IDs. Account bulk execution should independently construct, preflight, confirm and dispatch each approved account-specific plan (halt on ambiguous outcome). A failure on one account must never be displayed as a zero stock or success.

Until each adapter exists, keep it clearly labeled *Requires native planner / data*, with Expert prepared configuration as a separate, explicit advanced escape hatch only when supported by the current backend and policy.

## Design acceptance criteria

- A nontechnical player can set up a supported automation without typing JSON, internal IDs, Python structures or IkaBot function signatures.
- Every listed engine operation has a clearly documented native workflow or explicit read-only/unavailable state; no “generic JSON for the entire catalog” as the default long-term experience.
- The construction screen shows verifiable real cities, real building rows, target levels and a reviewable upstream cost/queue preview *before* permitting a plan launch.
- 900x650 desktop layout can use keyboard/VoiceOver to reach category filter, city chooser and review without nested clipping; 1200x800 remains compact.
- Dark/light screenshots and offline fixtures show no raw email, cookie, session or game account credentials.
- Offline tests verify backend read-only guarantees, no cross-account choices, stale revision rejection, import safety, no duplicate dispatch and no automatic retry after unknown outcomes.

## Current implementation state

This change is still **active**, not archived. The feature branch implements
native editors for the source-verified subset of background tasks listed in
docs/AUTOMATION-UX-AUDIT.md, including building levels and construction cost
previews, unit recruitment and workshop improvements, trade quotes, tavern,
academy, shrine, miracles, piracy and city/resource policies. The layout
retains a compact, visible review/start footer and one form scroller.

The original interactive-only viewArmy and shipMovements now have safe,
read-only existing-session adapters and a separate, responsive native Military
workspace with account and All accounts selectors. These endpoints never run
an IkaBot background task and return only bounded unit counts and current
movement descriptions. They fail closed on identity or malformed replies.

The remaining combat planning, worker assignments, production management,
transport ETA and other interactive administration tools are still unimplemented.
Readiness, full accessibility evidence, fresh plan fingerprints and
live-user-accepted game outcomes remain release gates; this change must not
be archived until those gates are met.

## Reuse upstream gameplay waits

Use the operation-specific upstream queue/cooldown implementation for all supported native workflows. Preserve original upstream scheduling rather than imposing one global wait algorithm. The verified cookie adapter SHALL preserve the original read-only queue AJAX forms for fleet advisor, barracks, shipyard, workshop, temple and building-speedup popup; it SHALL reject extra mutation fields and avoid implicit reauthentication. Reviewed supply uses the shared fleet-arrival estimate but independently verifies actual destination stock before upgrades. Infrastructure timeouts and cancellation remain independent. See docs/UPSTREAM-WAIT-AUDIT.md for the full task inventory and evidence.

## Engine parity and compatibility boundary

Use the merged upstream CLI/IPC import ba6aaba as the comparison baseline. Preserve upstream operation helpers verbatim where possible; when an interactive configurator contains an inline request, extract that exact request once for CLI and reviewed callers. Keep native planning, scope validation, and no-replay behavior separate from gameplay request construction. Dedicated nativeReadForms validates the existing bounded read-only AJAX forms at the cookie-session boundary; the operation should not substitute a different game endpoint. Retain the original upstream wait, recruitment, workshop, building, market and calculation functions, with source guards for preserved helpers. See docs/UPSTREAM-ENGINE-PARITY.md for the full source inventory and outstanding cookie-session integration risks.
