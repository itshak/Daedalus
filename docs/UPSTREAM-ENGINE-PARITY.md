# Upstream engine parity audit — 2026-11-26

## Baselines and method

Compare tracked source against `ba6aaba`, the merged public IkaBot 7.7.2 stable baseline plus experimental CLI/IPC PR #499. Stable-only import `ab070fb` is NOT the merged baseline. Public PR #499 is still open at `55d88778182159ee22918dd50585e1643f4df015` (checked via GitHub). Do not silently upgrade to that unreleased revision.

Compared all tracked engine source modules and function/class-method AST definitions, including duplicate top-level function names. The following inventory records the pre-audit delta (main `5d34af5`) and the consolidation decisions. Raw diff size includes necessary integration modules, not just gameplay changes.

## Operation-module decisions

| Module | Disposition |
| --- | --- |
| `activateMiracle.py` | Account/world-scoped caches; preserve upstream cooldown and activation. |
| `attackBarbarians.py` | Native reviewed mission plan and validation; keep upstream mission engine. Reviewed execution remains a live acceptance gate. |
| `autoBarbarians.py` | Native policy adapter and checks; mission logic remains upstream. Live outcomes unverified. |
| `autoPirate.py` | Native eligibility and human challenge handling; retain upstream scheduler. |
| `buyResources.py` | Keep upstream buy routine, reviewed quote guard; unify resource selection. |
| `constructBuilding.py` | Keep upstream price/block parser; extract one original read and mutation form, used by both callers. |
| `constructionList.py` | Native supply/review policy and exact target checks; retain original queue and cost helpers; use fleet arrival estimate. |
| `distributeResources.py` | Reviewed routes and ownership checks around upstream route planner/executor. |
| `donate.py` | Shared original donation mutation; reviewed island and amount checks. |
| `dumpWorld.py` | Managed reports/status and cancellation; preserve upstream scanning. |
| `fillCityWarehouse.py` | Local feature: planner and verification policy only; shared upstream sendResources executor. |
| `loginDaily.py` | Read-only reward inventory; unchanged original scheduler. |
| `modifyAcademyWorkers.py` | New native wrapper around modifyProduction worker-assignment helper. |
| `modifyProduction.py` | Shared original assignment requests; local read-only slider/plan validation. |
| `modifyTempleWorkers.py` | New native wrapper around modifyProduction worker-assignment helper. |
| `nativeMarket.py` | Read-only quote projection and prepare adapter; calls upstream offers/market helpers. |
| `reorganizeCityBuildings.py` | Keep upstream move algorithm; share original dialog and write form. |
| `research.py` | Reviewed research choice guard; retain upstream research experiment/cooldown functions. |
| `resourceTransportManager.py` | Replace duplicated fleet polls with shared wait; retain original recurring schedules and locks. |
| `searchForIslandSpaces.py` | Verify returned island coordinates match request; retain upstream search. |
| `sellResources.py` | Review quote/stock before existing upstream sell/list logic. |
| `sendResources.py` | Reviewed route/recipient validation, fixed-transfer journal and shared execution entry; retain original cargo form. |
| `stationArmy.py` | Shared original deployment view and sendArmy; preserve strict native inventory parsing. |
| `tavernManager.py` | Reviewed fixed serving policy delegates original TavernManager setter; retain recurrence. |
| `testDiscordBot.py` | Thin native wrapper for original notification test. |
| `testTelegramBot.py` | Thin native wrapper for original notification test. |
| `trainArmy.py` | Reviewed per-round policy delegates original waitForTraining and train; retain original CLI planTrainings. |
| `vacationMode.py` | Native review delegates original activateVacationMode; explicit no-replay. |

## Remaining integration changes and risks

- Retain account ownership, IPC registration, typed reviews, fixed-transfer recovery journal, managed report lifecycle, safe session recovery and human challenge policy. These features are not supplied by the pinned upstream CLI.
- The verified-cookie session adapter still differs from upstream session authentication. Original upstream queue and audited inventory read forms now go through one bounded same-world adapter; form validation lives in a dedicated local helper. The already working protected cargo submission is unchanged.
- Other state-changing POSTs still follow the existing session path unless explicitly covered by the protected transport adapter. Source/payload parity alone does not establish their live cookie-session compatibility. Do not claim that all workflows are operational or broaden a generic mutation proxy. Remaining actions need individual protected-session integration and synthetic plus owner-operated acceptance.
- The custom reviewed policy guards and journal in planRoutes cannot simply be removed without losing allocation caps, idempotence and uncertain-result handling. Further extraction is possible, but preserve the existing upstream cargo form and the currently verified shipment.
- Native preview projections are stricter than interactive menus by design. Reject stale/missing/ambiguous state rather than guess, and retain original game semantics.
- Previous waiting audit compared the stable-only import for its AST inventory; this audit uses the actual merged CLI/IPC baseline.

## Exact source definition inventory

Definitions changed/added/removed relative to the merged upstream baseline. This is an exhaustive machine-generated source inventory, not a claim of runtime acceptance.

### `config.py`
- Imports, constants, formatting or top-level registration only.

### `function/activateMiracle.py`
- Changed: `obtainMiraclesAvailable`.

### `function/attackBarbarians.py`
- Changed: `do_it`, `load_troops`, `loot`.
- Added: `_native_attack_city`, `_native_attack_inventory`, `_native_attack_plan`, `native_attack`, `native_attack_inventory`, `prepare_native_attack`, `preview_native_attack`.

### `function/autoBarbarians.py`
- Changed: `do_attack`, `loot`.
- Added: `_native_grind_plan`, `native_grind`, `prepare_native_grind`, `preview_native_grind`.

### `function/autoPirate.py`
- Changed: `do_pirate_missions`, `prepare_autoPirate`.

### `function/buyResources.py`
- Changed: `buy`, `chooseResource`, `do_it`.
- Added: `select_market_resource`.

### `function/constructBuilding.py`
- Changed: `constructBuilding`.
- Added: `_building_ground`, `_native_build_options`, `_native_build_plan`, `_submit_building`, `native_build`, `native_build_options`, `prepare_native_build`, `preview_native_build`.

### `function/constructionList.py`
- Changed: `do_it`, `expandBuilding`, `getResourcesNeeded`.
- Added: `_construction_supply`, `_run_supplied_construction`, `prepare_constructionList`, `preview_native_construction`.

### `function/distributeResources.py`
- Changed: `do_it`, `prepare_distributeResources`.
- Added: `preview_distribution`, `reviewed_distribution_routes`.

### `function/donate.py`
- Changed: `donate`.
- Added: `_submit_donation`, `execute_native_donation`, `prepare_donate`, `preview_native_donation`.

### `function/dumpWorld.py`
- Changed: `do_dumpWorld`, `do_it`.

### `function/fillCityWarehouse.py`
New local module.
- Added: `FillPreviewError.__init__`, `_WarehousePolicy.__init__`, `_WarehousePolicy._has_space`, `_WarehousePolicy._observe`, `_WarehousePolicy.after_send`, `_WarehousePolicy.before_send`, `_WarehousePolicy.before_wait`, `_WarehousePolicy.limit`, `_amount`, `_city`, `_free_space`, `_owned`, `_target`, `fill`, `incoming_amount`, `prepare_fill`, `preview_fill`.

### `function/loginDaily.py`
- Added: `preview_daily_rewards`.

### `function/modifyAcademyWorkers.py`
New local module.
- Added: `execute`, `prepare`.

### `function/modifyProduction.py`
- Changed: `modifyAcademyWorkers`, `modifyProduction`, `modifyTempleWorkers`.
- Added: `_read_worker_slider`, `_submit_worker_assignment`, `execute_native_workers`, `native_modify_production`, `prepare_modify_production`, `prepare_native_workers`, `preview_native_workers`.

### `function/modifyTempleWorkers.py`
New local module.
- Added: `execute`, `prepare`.

### `function/nativeMarket.py`
New local module.
- Added: `_amount`, `_market_city`, `_name`, `market_snapshot`, `prepare_buyResources`, `prepare_sellResources`, `preview_native_market`.

### `function/reorganizeCityBuildings.py`
- Changed: `reorganizeCityBuildings`.
- Added: `_open_layout_dialog`, `_review_layout`, `_submit_layout`, `native_layout`, `prepare_native_layout`, `preview_native_layout`.

### `function/research.py`
- Changed: `do_it`, `prepare_research`, `study`.
- Added: `native_study_choices`, `reviewed_study`.

### `function/resourceTransportManager.py`
- Changed: `do_it`, `do_it_distribute`, `do_it_unified`, `prepare_resourceTransportManager`.

### `function/searchForIslandSpaces.py`
- Changed: `islandIdFromCoords`.

### `function/sellResources.py`
- Changed: `do_it`, `do_it1`, `do_it2`.

### `function/sendResources.py`
- Changed: `do_it`, `prepare_sendResources`.
- Added: `_TransportIdentity.__init__`, `_TransportIdentity.handle_starttag`, `_destination_id`, `_eligible_destinations`, `_transport_timing`, `_verify_recipient`, `execute_prepared_shipments`, `native_island_destinations`, `preview_native_shipments`.

### `function/stationArmy.py`
- Changed: `getArmyAvailable`, `sendArmy`.
- Added: `_deployment_view`, `_station_batch`, `_station_plan`, `native_station`, `prepare_native_station`, `preview_native_station`.

### `function/tavernManager.py`
- Changed: `TavernManager._apply_level`, `TavernManager._get_tavern_data`, `do_tavernManager`, `prepare_tavernManager`.
- Added: `_fixed_row`, `_review_fixed_servings`, `_run_fixed_servings`, `native_serving_options`.

### `function/testDiscordBot.py`
- Added: `native_test`, `prepare_native_test`.

### `function/testTelegramBot.py`
- Added: `native_test`, `prepare_native_test`.

### `function/trainArmy.py`
- Changed: `do_trainArmy`, `train`.
- Added: `_reviewed_training_round`, `_run_reviewed_training`, `_validate_reviewed_training`, `available_trainable_units`, `prepare_trainArmy`.

### `function/vacationMode.py`
- Changed: `activateVacationMode`.
- Added: `native_vacation`, `prepare_native_vacation`, `preview_native_vacation`.

### `helpers/apiComm.py`
- Changed: `getNewBlackBoxToken`.

### `helpers/botComm.py`
- Added: `_native_notification_destination`, `native_notification_ready`, `native_notification_test`.

### `helpers/decorators.py`
- Changed: `task`.

### `helpers/fillProgress.py`
New local module.
- Added: `mark`, `snapshot`.

### `helpers/fixedTransferJournal.py`
New local module.
- Added: `FixedTransferJournal.__init__`, `FixedTransferJournal._db`, `FixedTransferJournal._pending`, `FixedTransferJournal._transition`, `FixedTransferJournal._verify`, `FixedTransferJournal.confirmed`, `FixedTransferJournal.rejected`, `FixedTransferJournal.remaining`, `FixedTransferJournal.reserve`, `_verified_uuid`, `canonical_transfer`.

### `helpers/fleetAdvisor.py`
New local module.
- Added: `advisor_data`.

### `helpers/ipc.py`
- Changed: `IPCServer.__init__`, `IPCServer._list_cities`, `IPCServer._start_task`, `IPCServer.handle_request`, `_run_ipc_task`, `get_ipc_file_path`, `get_ipc_lock_path`.
- Added: `IPCServer._attack_units_existing`, `IPCServer._build_options_existing`, `IPCServer._existing_session`, `IPCServer._list_academies_existing`, `IPCServer._list_buildings_existing`, `IPCServer._list_existing_sessions`, `IPCServer._list_existing_tasks`, `IPCServer._list_miracles_existing`, `IPCServer._list_pirate_fortresses_existing`, `IPCServer._list_taverns_existing`, `IPCServer._list_trainables_existing`, `IPCServer._list_workshop_upgrades_existing`, `IPCServer._market_quotes_existing`, `IPCServer._military_overview_existing`, `IPCServer._preview_attack_existing`, `IPCServer._preview_build_existing`, `IPCServer._preview_construction_existing`, `IPCServer._preview_donation_existing`, `IPCServer._preview_grind_existing`, `IPCServer._preview_layout_existing`, `IPCServer._preview_station_existing`, `IPCServer._preview_vacation_existing`, `IPCServer._preview_workers_existing`, `IPCServer._ship_movements_existing`, `IPCServer._shrine_status_existing`, `IPCServer._stop_existing_task`, `IPCServer._task_entry`, `IPCServer._task_preflight_existing`, `IPCServer._validate_session_existing`, `IPCServer._warehouse_snapshots_existing`, `_existing_city_id`, `start_dedicated_ipc_server`.

### `helpers/nativeAdminStatus.py`
New local module.
- Added: `administrative_status`.

### `helpers/nativeChallengePolicy.py`
New local module.
- Added: `configure`, `status`, `stop_at_challenge`.

### `helpers/nativeExtensions.py`
New local module.
- Added: `_approved_directory`, `_bounded_read`, `_inventory`, `_private`, `_registration`, `set_registration`, `status`.

### `helpers/nativeNotificationSettings.py`
New local module.
- Added: `_aad`, `_apply`, `_decode`, `_encode`, `_identity`, `_provider_accepts`, `_prune`, `_save_global`, `begin`, `complete`.

### `helpers/nativePolicyReview.py`
New local module.
- Added: `preview_recurring`.

### `helpers/nativeProxyProfiles.py`
New local module.
- Added: `_approved_path`, `_busy`, `_check_connectivity`, `_inventory`, `_private`, `_scope`, `_snapshot`, `configure`, `status`.

### `helpers/nativeReadForms.py`
New local module.
- Added: `_id`, `_position`, `validate_params`, `validate_url`.

### `helpers/nativeWorldReports.py`
New local module.
- Added: `_directory`, `_files`, `_integer`, `_metadata`, `_private_directory`, `_read`, `ensure_capacity`, `list_reports`, `project_world`, `read_report`, `save_report`.

### `helpers/pedirInfo.py`
- Changed: `read`.

### `helpers/planRoutes.py`
- Changed: `executeRoutes`, `sendGoods`, `waitForArrival`.
- Added: `transport_feedback`.

### `helpers/serverIdentity.py`
New local module.
- Added: `_OwnerHeader.__init__`, `_OwnerHeader.handle_data`, `_OwnerHeader.handle_endtag`, `_OwnerHeader.handle_starttag`, `_name`, `attest_player_from_world_html`.

### `helpers/sessionStorage.py`
- Changed: `write_json_file`.

### `web/session.py`
- Changed: `Session.__ask_password_if_needed`, `Session.__load_new_blackbox_token`, `Session.__login`, `Session.from_saved`, `Session.get`, `Session.logout`, `Session.post`.
- Added: `Session._daedalus_cookie_advisor_post`, `Session._daedalus_cookie_only_get`, `Session._daedalus_cookie_queue_post`, `Session._daedalus_cookie_read_ajax`, `Session._daedalus_reviewed_transport_post`, `_can_request_manual_auth`.

## Regression protection

The test fixture records exact source hashes of preserved upstream queue, parser and calculation helpers extracted from the merged baseline, independent of Git access in CI. New parity tests compare the original CLI and reviewed adapter request forms. Any future intentional upstream update requires reviewing and refreshing the guard.

Live acceptance remains separate: the first 81,500-wood shipment was previously observed; later fleet cycles and unrelated game operations remain unverified.
