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


def present_fields(task_name: str, fields: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return an enriched, side-effect-free copy of validated backend fields."""
    rendered: list[dict[str, object]] = []
    for original in fields:
        field = dict(original)
        metadata = REVIEWED_FIELD_CONTROLS.get((task_name, str(field.get("name"))), {})
        if metadata:
            field.update(metadata)
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
