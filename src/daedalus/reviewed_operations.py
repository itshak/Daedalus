"""Typed one-shot drafts shared by the controller and native client."""
from __future__ import annotations

WORKER_TASKS = frozenset({"modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers"})
CITY_REVIEW_TASKS = WORKER_TASKS | {"donate", "reorganizeCityBuildings", "constructBuilding", "stationArmy", "autoBarbarians"}


def validated_worker_draft(task: object, draft: object) -> dict[str, object]:
    if not isinstance(task, str) or task not in WORKER_TASKS or not isinstance(draft, dict):
        raise ValueError("Unknown worker operation")
    production = task == "modifyProduction"
    keys = {"percentage", "project", "overcharge"} if production else {"percentage"}
    if (set(draft) != keys or type(draft.get("percentage")) is not int
            or not 0 <= draft["percentage"] <= 100):
        raise ValueError("Invalid worker draft")
    if production and (draft["project"] not in ("resource", "tradegood")
                       or type(draft["overcharge"]) is not bool
                       or (draft["overcharge"] and draft["percentage"] != 100)):
        raise ValueError("Invalid worker project or overcharge")
    return dict(draft)


def validate_worker_plan(task: str, city_id: int, draft: dict[str, object],
                         plan: object) -> dict[str, object]:
    """Check a bounded engine observation; never synthesize missing values."""
    if (not isinstance(plan, dict) or plan.get("task") != task
            or type(plan.get("city_id")) is not int or plan["city_id"] != city_id
            or plan.get("percentage") != draft["percentage"]
            or plan.get("project") != draft.get("project")
            or plan.get("overcharge") is not draft.get("overcharge", False)
            or plan.get("ready") is not True
            or not isinstance(plan.get("city_name"), str)
            or not 0 < len(plan["city_name"]) <= 100):
        raise ValueError("Invalid worker preview scope")
    for key in ("maximum", "extra", "target"):
        if type(plan.get(key)) is not int or not 0 <= plan[key] <= 2*10**6:
            raise ValueError("Invalid worker count")
    current = plan.get("current")
    if current is not None and (type(current) is not int or not 0 <= current <= 2*10**6):
        raise ValueError("Invalid current worker count")
    if (plan["target"] != plan["maximum"] * draft["percentage"] // 100
            + (plan["extra"] if draft.get("overcharge") else 0)
            or (task != "modifyProduction" and plan["extra"] != 0)):
        raise ValueError("Invalid worker allocation")
    config = plan.get("config")
    if not isinstance(config, dict):
        raise ValueError("Missing worker config")  # noqa: TRY004 - malformed remote data
    expected = config.get("expected")
    if (not isinstance(expected, dict)
            or set(expected) != {"island_id", "position", "maximum", "extra", "current", "target"}
            or type(expected.get("island_id")) is not int
            or not 0 < expected["island_id"] < 10**12
            or (task == "modifyProduction" and expected["position"] is not None)
            or (task != "modifyProduction" and (type(expected["position"]) is not int
                                                or not 0 <= expected["position"] <= 80))
            or any(type(expected[k]) is not type(plan[k]) or expected[k] != plan[k]
                   for k in ("maximum", "extra", "current", "target"))
            or config != {"city_id": city_id, **draft, "expected": expected}):
        raise ValueError("Invalid reviewed worker config")
    return {k: plan[k] for k in ("task", "city_id", "city_name", "percentage",
                                 "project", "overcharge", "maximum", "extra",
                                 "current", "target", "ready", "config")}

def validated_layout_draft(city_id: object, draft: object) -> int:
    if (type(city_id) is not int or not 0 < city_id < 10**12
            or not isinstance(draft, dict) or set(draft) != {"template_city_id"}
            or type(draft["template_city_id"]) is not int
            or not 0 < draft["template_city_id"] < 10**12
            or city_id == draft["template_city_id"]):
        raise ValueError("Choose two different owned cities")
    return draft["template_city_id"]


def validate_layout_plan(city_id: int, template_id: int, plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or plan.get("template_city_id") != template_id
            or any(not isinstance(plan.get(k), str) or not 0 < len(plan[k]) <= 100
                   for k in ("city_name", "template_name"))
            or not isinstance(plan.get("moves"), list) or len(plan["moves"]) > 80
            or plan.get("ready") is not bool(plan["moves"])):
        raise ValueError("Invalid layout preview")
    for move in plan["moves"]:
        if (not isinstance(move, dict) or set(move) != {"from", "to", "building", "displaced"}
                or any(type(move[k]) is not int or not 0 <= move[k] <= 80 for k in ("from", "to"))
                or move["from"] == move["to"]
                or any(not isinstance(move[k], str) or not 0 < len(move[k]) <= 64
                       for k in ("building", "displaced"))):
            raise ValueError("Invalid layout move")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", "template_city_id", "expected"}
            or config["city_id"] != city_id or config["template_city_id"] != template_id
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid layout fingerprint")
    return {k: plan[k] for k in ("city_id", "template_city_id", "city_name", "template_name",
                                 "moves", "ready", "config")}

def validated_build_draft(draft: object) -> dict[str, int]:
    if (not isinstance(draft, dict) or set(draft) != {"position", "building_id"}
            or type(draft["position"]) is not int or not 0 <= draft["position"] <= 80
            or type(draft["building_id"]) is not int or not 0 < draft["building_id"] < 10**6):
        raise ValueError("Invalid new building choice")
    return dict(draft)


def _resources(value: object) -> bool:
    return isinstance(value, list) and len(value) == 5 and all(
        type(n) is int and 0 <= n <= 10**15 for n in value
    )


def _valid_build_option(option: object, available: list[int], busy: bool) -> bool:
    return (isinstance(option, dict) and type(option.get("position")) is int
            and 0 <= option["position"] <= 80 and type(option.get("building_id")) is int
            and 0 < option["building_id"] < 10**6
            and option.get("surface") in ("sea", "land", "shore", "wall", "dockyard")
            and isinstance(option.get("name"), str) and 0 < len(option["name"]) <= 100
            and _resources(option.get("costs")) and any(option["costs"])
            and option.get("ready") is (not busy and all(a >= n for a, n in zip(available, option["costs"]))))


def validate_build_inventory(city_id: int, data: object) -> dict[str, object]:
    if (not isinstance(data, dict) or data.get("city_id") != city_id
            or not isinstance(data.get("city_name"), str) or not 0 < len(data["city_name"]) <= 100
            or not _resources(data.get("available")) or type(data.get("busy")) is not bool
            or not isinstance(data.get("options"), list) or len(data["options"]) > 500
            or any(not _valid_build_option(o, data["available"], data["busy"]) for o in data["options"])):
        raise ValueError("Invalid building inventory")
    keys = [(o["position"], o["building_id"]) for o in data["options"]]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate building option")
    return {"city_id": city_id, "city_name": data["city_name"], "available": data["available"],
            "busy": data["busy"], "options": [{k: o[k] for k in (
                "position", "building_id", "name", "surface", "costs", "ready")} for o in data["options"]]}


def validate_build_plan(city_id: int, draft: dict[str, int], plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or any(plan.get(k) != v for k, v in draft.items())
            or not isinstance(plan.get("city_name"), str) or not 0 < len(plan["city_name"]) <= 100
            or not _resources(plan.get("available")) or type(plan.get("busy")) is not bool
            or not _valid_build_option(plan, plan["available"], plan["busy"])
            or plan.get("missing") != [max(0, n - a) for n, a in zip(plan["costs"], plan["available"])]):
        raise ValueError("Invalid building plan")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", "position", "building_id", "expected"}
            or config["city_id"] != city_id or any(config.get(k) != v for k, v in draft.items())
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid building fingerprint")
    return {k: plan[k] for k in ("city_id", "city_name", "position", "building_id", "name", "surface",
                                 "available", "costs", "missing", "busy", "ready", "config")}

def validated_station_draft(city_id: object, draft: object) -> dict[str, object]:
    if (not isinstance(draft, dict) or set(draft) != {"destination_city_id", "ground"}
            or type(draft["ground"]) is not bool):
        raise ValueError("Invalid deployment draft")
    validated_layout_draft(city_id, {"template_city_id": draft["destination_city_id"]})
    return dict(draft)


def validate_station_plan(city_id: int, draft: dict[str, object], plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or plan.get("destination_city_id") != draft["destination_city_id"]
            or plan.get("ground") is not draft["ground"]
            or any(not isinstance(plan.get(k), str) or not 0 < len(plan[k]) <= 100
                   for k in ("city_name", "destination_name"))
            or type(plan.get("total")) is not int or not 0 <= plan["total"] <= 10**12):
        raise ValueError("Invalid deployment preview")
    if draft["ground"]:
        if any(type(plan.get(k)) is not int or not 0 <= plan[k] <= 10**16
               for k in ("weight", "capacity")):
            raise ValueError("Invalid transport capacity")
    elif plan.get("weight") is not None or plan.get("capacity") is not None:
        raise ValueError("Unexpected fleet cargo capacity")
    if plan.get("ready") is not (plan["total"] > 0 and (
            not draft["ground"] or plan["weight"] <= plan["capacity"])):
        raise ValueError("Invalid deployment readiness")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", *draft, "expected"}
            or config["city_id"] != city_id or any(config.get(k) != v for k, v in draft.items())
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid deployment fingerprint")
    return {k: plan[k] for k in ("city_id", "destination_city_id", "ground", "city_name",
                                 "destination_name", "total", "weight", "capacity", "ready", "config")}

def validated_grind_draft(city_id: object, draft: object) -> dict[str, object]:
    if (type(city_id) is not int or not 0 < city_id < 10**12
            or not isinstance(draft, dict) or set(draft) != {"target_city_id", "send_notifications"}
            or type(draft["target_city_id"]) is not int or not 0 < draft["target_city_id"] < 10**12
            or type(draft["send_notifications"]) is not bool):
        raise ValueError("Invalid automatic attack draft")
    return dict(draft)


def validate_grind_plan(city_id: int, draft: dict[str, object], plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or plan.get("target_city_id") != draft["target_city_id"]
            or plan.get("send_notifications") is not draft["send_notifications"]
            or any(not isinstance(plan.get(k), str) or not 0 < len(plan[k]) <= 100
                   for k in ("city_name", "target_name"))
            or type(plan.get("level")) is not int or not 1 <= plan["level"] <= 39
            or any(type(plan.get(k)) is not int or not 0 <= plan[k] <= 10**12
                   for k in ("required_ships", "available_ships"))
            or any(type(plan.get(k)) is not bool for k in ("destroyed", "notifications_ready", "ready"))
            or not isinstance(plan.get("requirements"), list)
            or not 1 <= len(plan["requirements"]) <= 100):
        raise ValueError("Invalid automatic attack preview")
    for row in plan["requirements"]:
        if (not isinstance(row, dict) or set(row) != {"name", "required", "available"}
                or not isinstance(row["name"], str) or not 0 < len(row["name"]) <= 100
                or type(row["required"]) is not int or not 0 < row["required"] <= 10**9
                or type(row["available"]) is not int or not 0 <= row["available"] <= 10**9):
            raise ValueError("Invalid unit requirement")
    if plan["ready"] is not (not plan["destroyed"] and plan["notifications_ready"]
                             and plan["available_ships"] >= plan["required_ships"]
                             and all(r["available"] >= r["required"] for r in plan["requirements"])):
        raise ValueError("Invalid automatic attack eligibility")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", *draft, "expected"}
            or config["city_id"] != city_id or any(config.get(k) != v for k, v in draft.items())
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid automatic attack fingerprint")
    return {k: plan[k] for k in ("city_id", "target_city_id", "send_notifications", "city_name",
                                 "target_name", "level", "requirements", "required_ships", "available_ships",
                                 "destroyed", "notifications_ready", "ready", "config")}
