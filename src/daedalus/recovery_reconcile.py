"""Read-only, task-specific reconciliation before an automatic recovery dispatch.

A captured job is an *intent*, never a replayable queue of HTTP actions.
Only the maintained IkaBot IPC may inspect current world state and create a
fresh engine-generated construction plan. This module never sends game actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from daedalus.accounts import Account


@dataclass(frozen=True)
class ResumePlan:
    state: str  # ready, deferred, completed, review
    reason: str
    config: dict[str, Any] | None = None


def _ids(value: object) -> bool:
    return (isinstance(value, list) and bool(value)
            and all(type(v) is int and 0 < v < 10**12 for v in value)
            and len(set(value)) == len(value))


def _thresholds(value: object, *, allow_null: bool) -> bool:
    return (isinstance(value, list) and len(value) == 5
            and all((v is None and allow_null)
                    or (type(v) is int and v >= (-1 if not allow_null else 0)
                        and v <= 10**15) for v in value))


def canonical_fixed_transfer(config: dict[str, Any]) -> dict[str, Any] | None:
    """Only explicitly specified own-city routes are checkpointable."""
    if not isinstance(config, dict) or set(config) - {
        "routes", "useFreighters", "transfer_id",
    }:
        return None
    routes = config.get("routes")
    freighters = config.get("useFreighters", False)
    if type(freighters) is not bool or not isinstance(routes, list) or not 0 < len(routes) <= 40:
        return None
    clean = []
    for row in routes:
        if not isinstance(row, dict) or set(row) != {"from", "to", "resources"}:
            return None
        origin, dest, amounts = row["from"], row["to"], row["resources"]
        if (type(origin) is not int or type(dest) is not int
                or not 0 < origin < 10**12 or not 0 < dest < 10**12
                or origin == dest or not isinstance(amounts, list)
                or len(amounts) != 5 or any(
                    type(amount) is not int or not 0 <= amount <= 10**12
                    for amount in amounts
                ) or sum(amounts) == 0):
            return None
        clean.append({"from": origin, "to": dest, "resources": list(amounts)})
    return {"routes": clean, "useFreighters": freighters}


def _valid_transfer_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return UUID(value).version == 4 and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def restart_class_for(task: str, config: dict[str, Any]) -> str:
    """Explicit allowlist: one-shot amount-based transfers are never replayed.

    The two transport choices below continuously recalculate *excess above a
    minimum retained stock*. They do not replay a saved cargo quantity.
    """
    if task == "alertAttacks":
        return "continuous"
    if (task == "sendResources" and canonical_fixed_transfer(config) is not None
            and _valid_transfer_id(config.get("transfer_id"))):
        return "fixed_transfer"
    if task == "constructionList":  # noqa: SIM102 - explicit task allowlist
        if (config.get("expand_overall") is True
                and config.get("wait_resources") is False
                and config.get("shipments") == []
                and type(config.get("city_id")) is int
                and 0 < config["city_id"] < 10**12
                and isinstance(config.get("buildings"), list)
                and 0 < len(config["buildings"]) <= 12
                and all(isinstance(row, dict)
                        and type(row.get("position")) is int
                        and 0 <= row["position"] <= 80
                        and type(row.get("level")) is int
                        and 0 <= row["level"] <= 150
                        and type(row.get("upgradeTo")) is int
                        and row["level"] < row["upgradeTo"] <= 150
                        and isinstance(row.get("building"), str)
                        and bool(row["building"])
                        for row in config["buildings"])
                and len({row["position"] for row in config["buildings"]})
                == len(config["buildings"])):
            return "reconcile_construction"
    if task == "consolidateResources":  # noqa: SIM102 - explicit task allowlist
        if (_thresholds(config.get("limits"), allow_null=False)
                and _ids(config.get("sourceCityIds"))
                and type(config.get("destinationCityId")) is int
                and 0 < config["destinationCityId"] < 10**12
                and config["destinationCityId"] not in config["sourceCityIds"]
                and type(config.get("intervalInHours")) is int
                and config["intervalInHours"] >= 1
                and type(config.get("shipType")) is int
                and 1 <= config["shipType"] <= 3):
            return "convergent_transport"
    if task == "resourceTransportManager":  # noqa: SIM102 - explicit task allowlist
        if (config.get("mode") == "consolidate"
                and "island" not in config and "recipient" not in config  # Never auto-send to an external city.
                and config.get("send_mode") == "keep"
                and _thresholds(config.get("resource_config"), allow_null=True)
                and any(v is not None for v in config["resource_config"])
                and _ids(config.get("origin_cities"))
                and type(config.get("destination_city")) is int
                and 0 < config["destination_city"] < 10**12
                and config["destination_city"] not in config["origin_cities"]
                and type(config.get("interval_hours")) is int
                and config["interval_hours"] >= 1
                and type(config.get("useFreighters")) is bool):
            return "convergent_transport"
    return "manual"


def construction_plan(ipc: Any, account: Account, config: dict[str, Any]) -> ResumePlan:
    """Compute unfinished absolute building targets, without a write to the game.

    A busy building may represent a successfully queued upgrade, so defer until
    it completes. If the slot's building type changed, refuse to dispatch.
    """
    if restart_class_for("constructionList", config) != "reconcile_construction":
        return ResumePlan("review", "unverifiable_construction")
    city_id = config["city_id"]
    existing = ipc.buildings(account, city_id)
    slots = {row["position"]: row for row in existing}
    remaining: list[dict[str, int]] = []
    for target in config["buildings"]:
        current = slots.get(target["position"])
        if (current is None or current.get("building") != target["building"]
                or type(current.get("level")) is not int
                or current["level"] < target["level"]):
            return ResumePlan("review", "building_changed")
        # A queued final level is not necessarily finished yet: never mark
        # a still-busy slot complete, even if the game shows its next level.
        if current.get("busy") is True:
            return ResumePlan("deferred", "building_busy")
        if current["level"] >= target["upgradeTo"]:
            continue
        if current.get("can_upgrade") is not True:
            return ResumePlan("review", "building_unavailable")
        remaining.append({
            "position": target["position"],
            "target_level": target["upgradeTo"],
        })
    if not remaining:
        return ResumePlan("completed", "target_reached")
    # This is the exact existing read-only IkaBot planner. The engine validates
    # its returned configuration again immediately before dispatch.
    preview = ipc.construction_preview(account, city_id, remaining)
    if not preview.get("ready"):
        return ResumePlan("deferred", "resources_missing")
    fresh = preview.get("config")
    if (not isinstance(fresh, dict)
            or restart_class_for("constructionList", fresh) != "reconcile_construction"
            or len(fresh["buildings"]) != len(remaining)
            or {(r["position"], r["upgradeTo"]) for r in fresh["buildings"]}
            != {(r["position"], r["target_level"]) for r in remaining}
            or any(slots[r["position"]]["building"] != r["building"]
                   for r in fresh["buildings"])):
        return ResumePlan("review", "invalid_fresh_plan")
    return ResumePlan("ready", "remaining_upgrades", fresh)


def convergent_transport_plan(ipc: Any, account: Account,
                              task: str, config: dict[str, Any]) -> ResumePlan:
    """Verify source ownership freshly; only restart stock-threshold policies.

    Fixed-quantity/cumulative routes are intentionally excluded until shipment
    receipts and in-flight cargo reconciliation can prove their remainder.
    """
    if restart_class_for(task, config) != "convergent_transport":
        return ResumePlan("review", "non_idempotent_transport")
    own_ids = {city["id"] for city in ipc.cities(account)}
    origins = (config["sourceCityIds"] if task == "consolidateResources"
               else config["origin_cities"])
    if not set(origins) <= own_ids:
        return ResumePlan("review", "source_city_changed")
    destination_id = (config["destinationCityId"] if task == "consolidateResources"
                      else config["destination_city"])
    if destination_id not in own_ids:
        return ResumePlan("review", "destination_city_changed")
    # The source amount is re-read by the upstream engine at every run, never
    # taken from an old shipment plan. It can send only stock above the retained
    # threshold, so successfully dispatched cargo is no longer in that stock.
    return ResumePlan("ready", "stock_threshold_rechecked", config)

def fixed_transfer_plan(store: Any, ipc: Any, account: Account,
                        config: dict[str, Any]) -> ResumePlan:
    """Only verified outstanding dispatched amounts can be scheduled."""
    if restart_class_for("sendResources", config) != "fixed_transfer":
        return ResumePlan("review", "untracked_fixed_transfer")
    intent = canonical_fixed_transfer(config)
    if intent is None:
        return ResumePlan("review", "untracked_fixed_transfer")
    own_ids = {city["id"] for city in ipc.cities(account)}
    if any(route["from"] not in own_ids or route["to"] not in own_ids
           for route in intent["routes"]):
        return ResumePlan("review", "fixed_transfer_city_changed")
    progress = store.fixed_transfer_progress(account, config)
    if progress["uncertain"]:
        return ResumePlan("review", "fixed_transfer_uncertain")
    if progress["completed"]:
        return ResumePlan("completed", "fixed_transfer_dispatched")
    return ResumePlan("ready", "fixed_transfer_remaining", config)
