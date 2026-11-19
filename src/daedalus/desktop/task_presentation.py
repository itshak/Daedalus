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
