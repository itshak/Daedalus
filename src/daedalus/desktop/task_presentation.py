"""Reviewed UI presentation metadata for public IkaBot background tasks.

This is a display-only adapter. Actual task names, availability, allowed
parameter keys, and execution remain defined by the backend/engine. In
particular, adapters never generate game city identifiers or send requests.
Only explicitly source-documented primitive fields may refine an AST "json"
type into a native control; everything unknown keeps its advanced fallback.
The reference engine source retains upstream MIT attribution in engine/.
"""

from __future__ import annotations

from typing import Any

TASK_DESCRIPTIONS: dict[str, str] = {
    "activateMiracle": "Activate a configured miracle; requires a reviewed island and wonder.",
    "activateShrine": "Run the configured shrine schedule with explicit approval.",
    "alertAttacks": "Get notified about incoming attacks at a chosen polling interval.",
    "alertLowWine": "Alert before city wine supplies run out, with optional transfers.",
    "attackBarbarians": "Execute an independently prepared barbarian attack plan.",
    "autoBarbarians": "Repeat a reviewed barbarian mission configuration.",
    "autoPirate": "Run a configured piracy schedule or mission.",
    "buyResources": "Make market purchases using a reviewed offer and amount.",
    "consolidateResources": "Consolidate known resources to a target city.",
    "constructionList": "Run a prepared city construction plan; building queues require engine data.",
    "distributeResources": "Distribute resources using a selected supported policy.",
    "donationBot": "Coordinate supported island donations across configured cities.",
    "dumpWorld": "Export an allowed portion of the world map.",
    "loginDaily": "Perform the supported daily collection routine.",
    "research": "Run automatic academy experiments with a validated research configuration.",
    "resourceTransportManager": "Manage validated resource transport routes and intervals.",
    "searchForIslandSpaces": "Monitor island availability using a reviewed search configuration.",
    "sellResources": "Offer resources for sale using validated market criteria.",
    "sendResources": "Send resources along prepared, approved routes.",
    "tavernManager": "Balance tavern wine consumption in all cities, or a selected subset.",
    "trainArmy": "Execute a reviewed army-training plan for one city.",
    "UpgradeUnits": "Upgrade military units using a prepared plan.",
    "webServer": "Run the engine web service only with an explicitly reviewed configuration.",
}

# Explicitly documented by public IkaBot's @task function signatures:
# do_tavernManager(session, run_hours, ...) doc: integer hours, 0 runs once.
# alertLowWine.do_it(session, hours, ...) doc: integer positive wine threshold.
# The engine AST cannot infer these because upstream parameters lack type
# annotations/defaults. Nothing else is presumed to be a primitive value.
REVIEWED_FIELD_CONTROLS: dict[tuple[str, str], dict[str, Any]] = {
    # Source-verified compound editors. These field maps follow the actual
    # upstream prepare_* contract; options and amounts remain subject to
    # independent engine-side validation.
    ("sendResources", "routes"): {
        "type": "shipment_routes", "label": "Shipments",
        "help": "Add origin, destination and resource quantities for each route. Own cities only.",
    },
    ("consolidateResources", "limits"): {
        "type": "resource_limits", "label": "Retain in source cities",
        "help": "Choose how many resources to keep in each source city; keep all means do not ship.",
    },
    ("consolidateResources", "sourceCityIds"): {
        "type": "city_list", "label": "Source cities",
        "help": "Choose the owned cities whose excess resources should be consolidated.",
    },
    ("consolidateResources", "destinationCityId"): {
        "type": "city_picker", "label": "Destination city",
        "help": "Receive excess resources in this account's city.",
    },
    ("consolidateResources", "intervalInHours"): {
        "type": "integer", "label": "Repeat every",
        "minimum": 1, "maximum": 336, "suffix": " h",
        "explicit_input": True, "help": "Full hours between consolidation checks.",
    },
    ("consolidateResources", "shipType"): {
        "type": "integer", "choices": [1, 2, 3],
        "choice_labels": ["Trade ships", "Freighters", "Both fleets"],
        "label": "Fleet type",
    },
    ("donationBot", "cities_dict"): {
        "type": "donation_policies", "label": "Donation by city",
        "help": "Choose each city's island project and share or amount.",
    },
    ("donationBot", "donate_method"): {
        "type": "integer", "choices": [1, 2, 3],
        "choice_labels": ["Keep storage below a percentage",
                          "Donate a percentage of production",
                          "Donate a fixed resource amount"],
        "label": "Donation policy",
    },
    ("donationBot", "waiting_time"): {
        "type": "integer", "label": "Repeat donations every",
        "minimum": 1, "maximum": 10080, "suffix": " min",
        "help": "Actual IkaBot donation polling interval.",
    },
    ("donationBot", "cities_ids"): {
        "type": "hidden_derived",
        "help": "City IDs are derived from the reviewed donation table.",
    },
    ("resourceTransportManager", "mode"): {
        "type": "text", "choices": ["consolidate", "distribute"],
        "choice_labels": ["Many source cities → One destination",
                          "One source city → Many destinations"],
        "label": "Transport strategy",
    },
    ("resourceTransportManager", "origin_cities"): {
        "type": "city_list", "label": "Sending cities",
        "help": "Select one or more of your own source cities.",
    },
    ("resourceTransportManager", "destination_city"): {
        "type": "city_picker", "label": "Receiving city",
    },
    ("resourceTransportManager", "origin_city"): {
        "type": "city_picker", "label": "Sending city",
    },
    ("resourceTransportManager", "destination_cities"): {
        "type": "city_list", "label": "Receiving cities",
        "help": "Choose the receiving cities in this account.",
    },
    ("resourceTransportManager", "resource_config"): {
        "type": "resource_config", "label": "Five resource policies",
        "help": "Use Ignore to exclude a resource, 0 for send-all in Keep mode, or a positive amount.",
    },
    ("resourceTransportManager", "send_mode"): {
        "type": "text", "choices": ["keep", "send"],
        "choice_labels": ["Keep a reserve; send any surplus", "Send these amounts"],
        "label": "Resource amount interpretation",
    },
    ("resourceTransportManager", "island"): {
        "type": "hidden_derived",
        "help": "External destination islands need a separately verified lookup and are expert-only.",
    },
    ("resourceTransportManager", "interval_hours"): {
        "type": "integer", "minimum": 0, "maximum": 720,
        "label": "Repeat every", "suffix": " hours",
        "help": "0 sends only once; a positive value runs periodically.",
    },
    ("resourceTransportManager", "notify"): {
        "type": "text", "choices": ["none", "start", "all"],
        "choice_labels": ["No extra notifications", "At the start of each cycle",
                          "For every shipment"],
        "label": "Notifications",
    },
    ("resourceTransportManager", "info"): {"type": "hidden_derived"},
    ("resourceTransportManager", "telegram_enabled"): {"type": "hidden_derived"},
    ("resourceTransportManager", "notify_on_start"): {"type": "hidden_derived"},
    ("research", "qty"): {
        "type": "integer", "label": "Experiments (one city)",
        "minimum": 0, "maximum": 9999, "omit_zero": True,
        "help": "0 means automatic experiments. Positive count requires exactly one academy city.",
    },
    ("research", "mode"): {"type": "hidden_derived"},
    ("research", "experiments"): {"type": "hidden_derived"},
    ("research", "automatic"): {"type": "hidden_derived"},
    ("research", "cities"): {"type": "hidden_derived"},
    ("research", "info"): {"type": "hidden_derived"},
    ("tavernManager", "cities"): {"type": "hidden_derived"},
    ("activateMiracle", "wonder"): {
        "type": "text", "choices": ["hephaistos", "hades", "demeter", "athene",
                                   "hermes", "ares", "poseidon", "colossus"],
        "choice_labels": ["Hephaistos", "Hades", "Demeter", "Athena",
                          "Hermes", "Ares", "Poseidon", "Colossus"],
        "label": "Miracle",
        "help": "Engine verifies that this account owns an eligible temple of the chosen wonder.",
    },
    ("activateMiracle", "iterations"): {
        "type": "integer", "minimum": 1, "maximum": 100,
        "label": "Number of activations",
    },
    ("activateMiracle", "island"): {
        "type": "hidden_derived",
        "help": "IkaBot finds an eligible owned temple for the chosen wonder.",
    },
    ("activateShrine", "godids"): {
        "type": "choices_list", "choices": [1, 2, 3, 4, 5, 6],
        "choice_labels": ["Pan", "Dionysus", "Tyche", "Plutus", "Theia", "Hephaestus"],
        "label": "Gods to activate", "help": "Requires an actual Shrine of Olympus in this account.",
    },
    ("activateShrine", "mode"): {
        "type": "integer", "choices": [1, 2, 3],
        "choice_labels": ["Activate a number of times", "Repeat every 70 hours", "Both"],
        "label": "Activation schedule",
    },
    ("activateShrine", "times"): {
        "type": "integer", "minimum": 1, "maximum": 10,
        "label": "Number of activations", "help": "Used in First and Both schedules.",
    },
    ("activateShrine", "selected_gods"): {"type": "hidden_derived"},
    ("activateShrine", "wait_time"): {"type": "hidden_derived"},
    ("searchForIslandSpaces", "islandList"): {
        "type": "island_list", "label": "Islands to monitor",
        "help": "Optionally select islands already hosting your cities; otherwise IkaBot searches all owned islands.",
    },
    ("searchForIslandSpaces", "time"): {
        "type": "integer", "minimum": 3, "maximum": 1440,
        "label": "Check every", "suffix": " min", "explicit_input": True,
    },
    ("searchForIslandSpaces", "fights"): {
        "type": "boolean", "label": "Also monitor fighting on these islands",
    },
    ("dumpWorld", "coords"): {
        "type": "map_center", "label": "Map area",
        "help": "Optionally select an area; leave disabled to scan the whole world.",
    },
    ("dumpWorld", "radius"): {
        "type": "hidden_derived", "help": "Radius is entered beside the optional map center.",
    },
    ("dumpWorld", "waiting_time"): {
        "type": "number", "label": "Delay between island requests",
        "minimum": 0.1, "maximum": 60.0, "suffix": " s",
        "help": "Avoid aggressive world requests. Default is 1.5 seconds.",
    },
    ("dumpWorld", "show_progress"): {"type": "hidden_derived"},
    ("autoPirate", "pirateCount"): {
        "type": "integer", "minimum": 1, "maximum": 100000, "explicit_input": True,
        "label": "Number of missions",
    },
    ("autoPirate", "pirateMissionChoice"): {
        "type": "integer", "choices": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "label": "Mission", "help": "Required without the day/night schedule.",
    },
    ("autoPirate", "pirateMissionDayChoice"): {
        "type": "integer", "choices": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "label": "Day mission", "help": "Required when scheduled.",
    },
    ("autoPirate", "pirateMissionNightChoice"): {
        "type": "integer", "choices": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "label": "Night mission", "help": "Required when scheduled.",
    },
    ("autoPirate", "dayStart"): {"type": "integer", "minimum": 0, "maximum": 23, "suffix": ":00"},
    ("autoPirate", "dayEnd"): {"type": "integer", "minimum": 0, "maximum": 23, "suffix": ":00"},
    ("autoPirate", "nightStart"): {"type": "integer", "minimum": 0, "maximum": 23, "suffix": ":00"},
    ("autoPirate", "nightEnd"): {"type": "integer", "minimum": 0, "maximum": 23, "suffix": ":00"},
    ("autoPirate", "autoConvert"): {"type": "boolean", "label": "Convert capture points automatically"},
    ("autoPirate", "convertPerMission"): {
        "type": "integer", "minimum": 0, "maximum": 1000000, "label": "Convert after each mission",
    },
    ("autoPirate", "maxRandomWaitingTime"): {
        "type": "integer", "minimum": 0, "maximum": 3600,
        "label": "Random additional waiting", "suffix": " s",
    },
    ("autoPirate", "piracyCities"): {
        "type": "hidden_derived",
        "help": "Engine selects the first eligible real pirate fortress for the chosen mission.",
    },
    # Daily collection city destinations and favour keys are taken verbatim
    # from loginDaily.prepare_loginDaily and TASK_FUNCTIONS.
    ("loginDaily", "wine_city"): {
        "type": "city_picker", "label": "Daily wine reward city",
        "help": "Choose which of your actual cities receives the daily wine reward.",
    },
    ("loginDaily", "wood_city"): {
        "type": "city_picker", "label": "Cinetheatre wood reward city",
        "help": "Optional: leave skipped if you do not want the wood cinetheatre reward.",
    },
    ("loginDaily", "luxury_city"): {
        "type": "city_picker", "label": "Cinetheatre luxury reward city",
        "help": "Optional: leave skipped if you do not want the luxury cinetheatre reward.",
    },
    ("loginDaily", "favour_tasks"): {
        "type": "choices_list", "choices": ["resource", "look", "online", "complete"],
        "label": "Daily favour tasks",
        "help": "Optional tasks: collect resource favour, visit information pages, stay online or collect completed tasks.",
    },
    # These are literal upstream enums in distributeResources.py, not guesses.
    ("distributeResources", "resource"): {
        "type": "text",
        "choices": ["wood", "wine", "marble", "crystal", "sulfur"],
        "label": "Resource to distribute",
        "help": "The IkaBot engine calculates actual shipment amounts at the time of dispatch.",
    },
    ("distributeResources", "mode"): {
        "type": "text",
        "choices": ["even", "producers"],
        "label": "Distribution policy",
        "help": "Even: balance amounts; Producers: ship from producers to non-producers.",
    },
    ("distributeResources", "cities_ids"): {
        "type": "city_list",
        "label": "Participating cities",
        "help": "Leave all unchecked to use every city. Choose at least two for a custom subset.",
    },
    ("tavernManager", "cities_ids"): {
        "type": "city_list",
        "label": "Tavern cities",
        "help": "Leave all unchecked to have IkaBot select its default tavern cities.",
    },
    ("research", "cities_ids"): {
        "type": "city_list",
        "label": "Academy cities",
        "help": "Leave all unchecked to include the engine's default eligible academies.",
    },
    ("tavernManager", "run_hours"): {
        "type": "integer",
        "label": "Check tavern balance every",
        "minimum": 0,
        "maximum": 168,
        "suffix": " hours",
        "explicit_input": True,
        "help": "Whole hours between checks. Choose 0 to run just once.",
    },
    ("alertLowWine", "hours"): {
        "type": "integer",
        "label": "Warn when wine has less than",
        "minimum": 1,
        "maximum": 720,
        "suffix": " hours",
        "explicit_input": True,
        "help": "Alert threshold in hours. Notifications must already be configured in IkaBot.",
    },
    ("alertLowWine", "auto_transfer"): {
        "label": "Transfer wine automatically if needed",
        "help": "Turn on only if this account is allowed to send wine automatically.",
    },
    ("alertLowWine", "transfer_amount"): {
        "label": "Wine to transfer",
        "minimum": 0,
        "maximum": 1_000_000,
        "help": "The amount of wine to send if automatic transfer is enabled; 0 disables transfers.",
    },
    ("tavernManager", "check_now"): {
        "label": "Check once immediately",
        "help": "Run the initial check before the recurring schedule.",
    },
}


# Labels and guidance are presentation-only. They never substitute values,
# allowed IDs, resource quantities, route definitions or building queues.
FIELD_GUIDANCE: dict[tuple[str, str], tuple[str, str]] = {
    ("constructionList", "city_id"): (
        "City identifier", "Choose an existing city from your reviewed construction plan; do not guess an ID."
    ),
    ("constructionList", "city_name"): (
        "City name", "Use the name paired with the city in the reviewed plan."
    ),
    ("constructionList", "buildings"): (
        "Building upgrades", "Prepared ordered building upgrades from IkaBot; supply structured plan data."
    ),
    ("constructionList", "construction_queue"): (
        "Construction queue", "Use the queue from an existing validated plan; the Mac app cannot invent steps."
    ),
    ("research", "cities_ids"): (
        "Research cities", "Optional array of existing city identifiers, from your engine configuration."
    ),
    ("research", "experiments"): (
        "Academy experiments", "Review experiment quantities and academy prerequisites in the engine plan."
    ),
    ("resourceTransportManager", "origin_cities"): (
        "Source cities", "Use only authorized source city identifiers from your existing route plan."
    ),
    ("resourceTransportManager", "destination_city"): (
        "Destination city", "Use the exact destination city in your reviewed route plan."
    ),
    ("resourceTransportManager", "interval_hours"): (
        "Transport interval", "Hours between transport checks; 0 is the engine default."
    ),
    ("sendResources", "routes"): (
        "Transport routes", "Required structured routes: source, destination, resource and quantity."
    ),
    ("alertAttacks", "minutes"): (
        "Check for attacks every", "Polling interval in minutes. Notifications must be configured in IkaBot."
    ),
    ("tavernManager", "cities_ids"): (
        "Tavern cities", "Optional array of known city identifiers; omit for engine defaults."
    ),
    ("autoPirate", "dayStart"): (
        "Day schedule begins", "Hour on the game's configured schedule; check the upstream time convention."
    ),
    ("autoPirate", "dayEnd"): (
        "Day schedule ends", "Hour on the game's configured schedule; check the upstream time convention."
    ),
    ("autoPirate", "nightStart"): (
        "Night schedule begins", "Hour on the game's configured schedule; check the upstream time convention."
    ),
    ("autoPirate", "nightEnd"): (
        "Night schedule ends", "Hour on the game's configured schedule; check the upstream time convention."
    ),
    ("consolidateResources", "intervalInHours"): (
        "Consolidation interval", "Hours between resource consolidation checks."
    ),
    ("distributeResources", "useFreighters"): (
        "Use freighters", "Use freighters only if this route and account support them."
    ),
    ("dumpWorld", "waiting_time"): (
        "Wait between queries", "Engine-provided interval; avoid aggressive map requests."
    ),
}


def present_fields(task_name: str, fields: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return an enriched, side-effect-free copy of validated backend fields."""
    rendered: list[dict[str, object]] = []
    for original in fields:
        field = dict(original)
        metadata = REVIEWED_FIELD_CONTROLS.get((task_name, str(field.get("name"))), {})
        if metadata:
            field.update(metadata)
        guidance = FIELD_GUIDANCE.get((task_name, str(field.get("name"))))
        if guidance:
            field.setdefault("label", guidance[0])
            field.setdefault("help", guidance[1])
        rendered.append(field)
    return rendered


def task_explanation(task_name: str) -> str:
    return TASK_DESCRIPTIONS.get(
        task_name,
        "Review the registered engine parameters. Complex tasks may require an "
        "existing prepared configuration.",
    )


def expert_configuration_needed(fields: list[dict[str, object]]) -> bool:
    """Flag required nested fields that cannot safely be guessed as Mac widgets."""
    return any(
        field.get("required") is True and field.get("type") == "json"
        for field in fields
    )


# Intentionally allow-listed primitive display values. Advanced free-form values
# may contain private game data; do not echo them into dialogs or logs.
_SUMMARY_SAFE_SCALARS = frozenset({
    "minutes", "hours", "run_hours", "auto_transfer", "transfer_amount",
    "check_now", "notification_mode", "intervalInHours", "interval_hours",
    "useFreighters", "shallow", "non_empty_islands", "show_progress",
})


def configuration_summary(config: dict[str, object]) -> str:
    """Human-readable, secret-free summary; never print arbitrary game data."""
    if not config:
        return "Use registered defaults"
    items = []
    for key, value in list(config.items())[:32]:
        if not isinstance(key, str):
            continue
        title = key.replace("_", " ")
        if key in _SUMMARY_SAFE_SCALARS and type(value) in (bool, int, float):
            items.append(f"{title}: {value}")
        else:
            items.append(f"{title}: configured")
    return ", ".join(items)[:600]
