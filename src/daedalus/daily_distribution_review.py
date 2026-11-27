"""Bounded typed drafts and scope validation for scheduled daily and distribution reviews."""
from daedalus.reviewed_operations import validate_shipment_plan, validated_shipment_draft


def _city(value):
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 12:
        value = int(value)
    if type(value) is not int or not 0 < value < 10**12:
        raise ValueError("Choose an actual city")
    return value


def daily_draft(value):
    if (not isinstance(value, dict) or not {"wine_city"} <= set(value)
            or set(value) - {"wine_city", "wood_city", "luxury_city", "favour_tasks", "collect_ambrosia"}):
        raise ValueError("Invalid daily reward draft")
    tasks = value.get("favour_tasks", [])
    ambrosia = value.get("collect_ambrosia", False)
    if (not isinstance(tasks, list) or len(tasks) > 4
            or any(not isinstance(t, str) or t not in ("resource", "look", "online", "complete") for t in tasks)
            or len(set(tasks)) != len(tasks) or type(ambrosia) is not bool):
        raise ValueError("Invalid daily reward choices")
    return {"wine_city": _city(value["wine_city"]),
            "wood_city": _city(value["wood_city"]) if value.get("wood_city") is not None else None,
            "luxury_city": _city(value["luxury_city"]) if value.get("luxury_city") is not None else None,
            "favour_tasks": tasks, "collect_ambrosia": ambrosia}


def distribution_draft(value):
    if (not isinstance(value, dict) or not {"resource", "cities_ids"} <= set(value)
            or set(value) - {"resource", "cities_ids", "mode", "useFreighters"}):
        raise ValueError("Invalid distribution draft")
    resource, mode, fleet = value["resource"], value.get("mode", "even"), value.get("useFreighters", False)
    ids = value["cities_ids"]
    if (resource not in ("wood", "wine", "marble", "crystal", "sulfur")
            or mode not in ("even", "producers") or (mode == "producers" and resource == "wood")
            or type(fleet) is not bool or not isinstance(ids, list) or not 2 <= len(ids) <= 200):
        raise ValueError("Invalid distribution options")
    ids = [_city(i) for i in ids]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate distribution city")
    return {"resource": resource, "mode": mode, "cities_ids": ids, "useFreighters": fleet}


def validate_distribution(draft, plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("routes"), list):
        raise ValueError("Invalid distribution preview")  # noqa: TRY004 - invalid remote observation
    routes = [{k: r[k] for k in ("from", "to", "resources")} for r in plan["routes"] if isinstance(r, dict)
              and all(k in r for k in ("from", "to", "resources"))]
    if len(routes) != len(plan["routes"]):
        raise ValueError("Invalid distribution route")
    ship = validated_shipment_draft({"routes": routes, "useFreighters": draft["useFreighters"]})
    index = ("wood", "wine", "marble", "crystal", "sulfur").index(draft["resource"])
    if any(r["from"] not in draft["cities_ids"] or r["to"] not in draft["cities_ids"]
           or any(v for j, v in enumerate(r["resources"]) if j != index) for r in routes):
        raise ValueError("Foreign distribution route")
    validate_shipment_plan(ship, plan)
    destinations = {}
    for row in plan["routes"]:
        dest = row["to"]
        space, amounts = destinations.get(dest, (row["destination_space"], [0] * 5))
        if space != row["destination_space"]:
            raise ValueError("Destination storage changed")
        amounts = [a + b for a, b in zip(amounts, row["resources"])]
        if any(a > b for a, b in zip(amounts, space)):
            raise ValueError("Distribution exceeds observed destination space")
        destinations[dest] = (space, amounts)
    return ship["routes"]


def validate_daily(draft, value):
    if (not isinstance(value, dict) or set(value) != {"cities", "favour", "limit", "reset_seconds", "collectable"}
            or not isinstance(value["cities"], dict)
            or set(value["cities"]) != {k for k in ("wine_city", "wood_city", "luxury_city") if draft[k] is not None}
            or any(not isinstance(v, str) or not 0 < len(v) <= 120 or any(ord(c) < 32 or c in "<>" for c in v)
                   for v in value["cities"].values())
            or any(type(value[k]) is not int or not 0 <= value[k] <= 10**9
                   for k in ("favour", "limit", "reset_seconds", "collectable"))
            or value["limit"] == 0 or value["favour"] > value["limit"] or value["collectable"] > 100):
        raise ValueError("Invalid daily reward observation")
    return value


def validate_ticket(value, account, task, draft):
    import re
    fields = {"account_id", "task", "draft", "observation", "preview_id", "expires_in"}
    if task == "fillCityWarehouse" and isinstance(value, dict) and "recovery_reason" in value:
        from daedalus.fill_warehouse_review import WAREHOUSE_RECOVERY_MESSAGES

        fields.add("recovery_reason")
        if not isinstance(value["recovery_reason"], str) or value["recovery_reason"] not in WAREHOUSE_RECOVERY_MESSAGES:
            raise ValueError("Invalid warehouse recovery status")
    if (not isinstance(value, dict) or set(value) != fields
            or value.get("account_id") != account or value.get("task") != task
            or value.get("draft") != draft or not isinstance(value.get("preview_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value["preview_id"])
            or type(value.get("expires_in")) is not int or not 1 <= value["expires_in"] <= 120):
        raise ValueError("Invalid native review")
    if task == "loginDaily":
        validate_daily(draft, value["observation"])
    elif task == "distributeResources":
        validate_distribution(draft, value["observation"])
        if value["observation"]["ready"] is not True:
            raise ValueError("No usable fleet")
    elif task in {"buyResources", "sellResources"}:
        from daedalus.market_review import validate_market_observation

        validate_market_observation(task, draft, value["observation"])
    else:
        from daedalus.native_policy_review import validate_policy_observation

        validate_policy_observation(task, draft, value["observation"])
    return value
