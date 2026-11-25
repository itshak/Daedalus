"""Typed one-shot drafts shared by the controller and native client."""
from __future__ import annotations

WORKER_TASKS = frozenset({"modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers"})
CITY_REVIEW_TASKS = WORKER_TASKS | {"trainArmy", "donate", "reorganizeCityBuildings", "constructBuilding", "stationArmy", "autoBarbarians", "attackBarbarians", "vacationMode"}


def validated_worker_draft(task: object, draft: object) -> dict[str, object]:
    if not isinstance(task, str) or task not in WORKER_TASKS or not isinstance(draft, dict):
        raise ValueError("Unknown worker operation")
    production = task == "modifyProduction"
    keys = {"percentage", "project", "overcharge"} if production else {"percentage"}
    if (not keys <= set(draft) <= keys | {"additional_city_ids"} or type(draft.get("percentage")) is not int
            or not 0 <= draft["percentage"] <= 100):
        raise ValueError("Invalid worker draft")
    if production and (draft["project"] not in ("resource", "tradegood", "both")
                       or type(draft["overcharge"]) is not bool
                       or (draft["overcharge"] and draft["percentage"] != 100)):
        raise ValueError("Invalid worker project or overcharge")
    if "additional_city_ids" in draft:
        ids = draft["additional_city_ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 31
                or any(type(cid) is not int or not 0 < cid < 10**12 for cid in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("Invalid additional worker cities")
    return dict(draft)


def validate_worker_plan(task: str, city_id: int, draft: dict[str, object],
                         plan: object) -> dict[str, object]:
    """Check a bounded engine observation; never synthesize missing values."""
    if "additional_city_ids" in draft or draft.get("project") == "both":
        return _validate_worker_aggregate(task, city_id, draft, plan, with_config=True)
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

def _validate_worker_aggregate(task, city_id, draft, plan, *, with_config):
    ids = [city_id, *draft.get("additional_city_ids", [])]
    projects = ["resource", "tradegood"] if draft.get("project") == "both" else [draft.get("project")]
    if (not isinstance(plan, dict) or len(set(ids)) != len(ids) or plan.get("task") != task
            or plan.get("city_id") != city_id or plan.get("percentage") != draft["percentage"]
            or plan.get("project") != draft.get("project")
            or plan.get("overcharge") is not draft.get("overcharge", False)
            or plan.get("additional_city_ids") != draft.get("additional_city_ids")
            or plan.get("ready") is not True or not isinstance(plan.get("assignments"), list)
            or len(plan["assignments"]) != len(ids) * len(projects)):
        raise ValueError("Invalid worker assignment scope")
    config = plan.get("config") if with_config else None
    if with_config and (not isinstance(config, dict) or not isinstance(config.get("expected"), list)
                        or len(config["expected"]) != len(plan["assignments"])
                        or config != {"city_id": city_id, **draft, "expected": config["expected"]}):
        raise ValueError("Invalid worker assignment config")
    names = {}
    for i, ((cid, project), row) in enumerate(zip(
            [(cid, project) for cid in ids for project in projects], plan["assignments"])):
        if (not isinstance(row, dict) or set(row) != {"city_id", "city_name", "project", "maximum", "extra", "current", "target"}
                or type(row["city_id"]) is not int or row["city_id"] != cid or row["project"] != project
                or not isinstance(row["city_name"], str) or not 0 < len(row["city_name"]) <= 100
                or any(type(row[k]) is not int or not 0 <= row[k] <= 2*10**6 for k in ("maximum", "extra", "target"))
                or (row["current"] is not None and (type(row["current"]) is not int or not 0 <= row["current"] <= 2*10**6))
                or row["target"] != row["maximum"] * draft["percentage"] // 100
                    + (row["extra"] if draft.get("overcharge") else 0)
                or (task != "modifyProduction" and row["extra"] != 0)
                or (cid in names and names[cid] != row["city_name"])):
            raise ValueError("Invalid worker assignment row")
        names[cid] = row["city_name"]
        if with_config:
            entry = config["expected"][i]
            if (not isinstance(entry, dict) or set(entry) != {"city_id", "project", "observation"}
                    or entry["city_id"] != cid or entry["project"] != project):
                raise ValueError("Invalid worker assignment fingerprint")
            single = {"percentage": draft["percentage"]}
            if task == "modifyProduction":
                single.update(project=project, overcharge=draft["overcharge"])
            validate_worker_plan(task, cid, single, {
                **row, "task": task, "percentage": draft["percentage"],
                "overcharge": draft.get("overcharge", False), "ready": True,
                "config": {"city_id": cid, **single, "expected": entry["observation"]}})
    rows = plan["assignments"]
    current = sum(r["current"] for r in rows) if all(r["current"] is not None for r in rows) else None
    if (plan.get("city_name") != names[city_id]
            or any(type(plan.get(k)) is not int or plan[k] != sum(r[k] for r in rows) for k in ("maximum", "extra", "target"))
            or type(plan.get("current")) is not type(current) or plan["current"] != current):
        raise ValueError("Invalid worker assignment totals")
    keys = ("task", "city_id", "city_name", "percentage", "project", "overcharge",
            "maximum", "extra", "current", "target", "assignments", "ready")
    return {**{k: plan[k] for k in keys},
            **({"additional_city_ids": draft["additional_city_ids"]} if "additional_city_ids" in draft else {}),
            **({"config": config} if with_config else {})}


def validate_worker_observation(task, city_id, draft, plan):
    if "additional_city_ids" in draft or draft.get("project") == "both":
        return _validate_worker_aggregate(task, city_id, draft, plan, with_config=False)
    if (not isinstance(plan, dict) or "assignments" in plan or "additional_city_ids" in plan
            or plan.get("task") != task or plan.get("city_id") != city_id
            or plan.get("percentage") != draft["percentage"] or plan.get("project") != draft.get("project")
            or plan.get("overcharge") is not draft.get("overcharge", False) or plan.get("ready") is not True
            or not isinstance(plan.get("city_name"), str) or not 0 < len(plan["city_name"]) <= 100
            or any(type(plan.get(k)) is not int or not 0 <= plan[k] <= 2*10**6 for k in ("maximum", "extra", "target"))
            or (plan.get("current") is not None and (type(plan["current"]) is not int or not 0 <= plan["current"] <= 2*10**6))
            or plan["target"] != plan["maximum"] * draft["percentage"] // 100
                + (plan["extra"] if draft.get("overcharge") else 0)
            or (task != "modifyProduction" and plan["extra"] != 0)):
        raise ValueError("Invalid worker preview")
    return plan


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
    required = {"destination_city_id", "ground"}
    if (not isinstance(draft, dict) or not required <= set(draft) <= required | {"all_origins", "both"}
            or type(draft["ground"]) is not bool
            or any(draft[k] is not True for k in set(draft) - required)
            or (draft.get("both") and not draft["ground"])):
        raise ValueError("Invalid deployment draft")
    validated_layout_draft(city_id, {"template_city_id": draft["destination_city_id"]})
    return dict(draft)


def validate_station_observation(city_id: int, draft: dict[str, object], plan: object) -> dict[str, object]:
    """Validate the same safe projection at worker and client boundaries."""
    keys = ("city_id", "destination_city_id", "ground", "city_name",
            "destination_name", "total", "weight", "capacity", "ready")
    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or type(plan.get("city_id")) is not int
            or plan.get("destination_city_id") != draft["destination_city_id"]
            or type(plan.get("destination_city_id")) is not int
            or plan.get("ground") is not draft["ground"]
            or any(not isinstance(plan.get(k), str) or not 0 < len(plan[k]) <= 100
                   for k in ("city_name", "destination_name"))
            or type(plan.get("total")) is not int or not 0 <= plan["total"] <= 10**12):
        raise ValueError("Invalid deployment preview")

    def valid_capacity(row):
        if row["ground"]:
            return all(type(row.get(k)) is int and 0 <= row[k] <= 10**16 for k in ("weight", "capacity"))
        return row.get("weight") is None and row.get("capacity") is None

    if not valid_capacity(plan):
        raise ValueError("Invalid transport capacity")
    if plan.get("ready") is not (plan["total"] > 0 and (
            not draft["ground"] or plan["weight"] <= plan["capacity"])):
        raise ValueError("Invalid deployment readiness")
    extras = set(draft) - {"destination_city_id", "ground"}
    if any(plan.get(k) is not True for k in extras):
        raise ValueError("Deployment options changed")
    if extras:
        rows = plan.get("deployments")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
            raise ValueError("Invalid deployment routes")
        seen = set()
        names = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"city_id", "city_name", "ground", "total", "weight", "capacity"}
                    or type(row["city_id"]) is not int or not 0 < row["city_id"] < 10**12
                    or row["city_id"] == draft["destination_city_id"] or type(row["ground"]) is not bool
                    or not isinstance(row["city_name"], str) or not 0 < len(row["city_name"]) <= 100
                    or type(row["total"]) is not int or not 0 <= row["total"] <= 10**12
                    or not valid_capacity(row) or (row["city_id"], row["ground"]) in seen
                    or (row["city_id"] in names and names[row["city_id"]] != row["city_name"])):
                raise ValueError("Invalid deployment route")
            seen.add((row["city_id"], row["ground"]))
            names[row["city_id"]] = row["city_name"]
        modes = {True, False} if draft.get("both") else {draft["ground"]}
        if (city_id not in names or names[city_id] != plan["city_name"] or len(names) > 32
                or (not draft.get("all_origins") and set(names) != {city_id})
                or seen != {(cid, mode) for cid in names for mode in modes}
                or sum(r["total"] for r in rows) != plan["total"]):
            raise ValueError("Invalid deployment coverage")
        ground_rows = [r for r in rows if r["ground"]]
        if ground_rows and (sum(r["weight"] for r in ground_rows) != plan["weight"]
                            or min(r["capacity"] for r in ground_rows) != plan["capacity"]):
            raise ValueError("Invalid shared fleet capacity")
        keys += ("deployments", *sorted(extras))
    elif "deployments" in plan or any(k in plan for k in ("all_origins", "both")):
        raise ValueError("Unexpected deployment routes")
    return {k: plan[k] for k in keys}


def validate_station_plan(city_id: int, draft: dict[str, object], plan: object) -> dict[str, object]:
    import re

    observation = validate_station_observation(city_id, draft, plan)
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", *draft, "expected"}
            or config["city_id"] != city_id or any(config.get(k) != v for k, v in draft.items())
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid deployment fingerprint")
    return {**observation, "config": config}


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

def validated_attack_draft(city_id: object, draft: object) -> dict[str, object]:
    import re

    if (type(city_id) is not int or not 0 < city_id < 10**12
            or not isinstance(draft, dict) or set(draft) != {"target_city_id", "waves"}
            or type(draft["target_city_id"]) is not int or not 0 < draft["target_city_id"] < 10**12
            or not isinstance(draft["waves"], list) or not 1 <= len(draft["waves"]) <= 8):
        raise ValueError("Invalid manual attack draft")
    previous = 0
    for index, wave in enumerate(draft["waves"]):
        if (not isinstance(wave, dict) or set(wave) != {"round", "loot", "ships", "units"}
                or type(wave["round"]) is not int or not previous < wave["round"] <= 100
                or (index == 0 and wave["round"] != 1)
                or type(wave["loot"]) is not bool
                or (wave["loot"] and (index == 0 or index != len(draft["waves"])-1))
                or type(wave["ships"]) is not int or not 0 <= wave["ships"] <= 10**9
                or (wave["loot"] and wave["ships"] != 0)
                or not isinstance(wave["units"], dict) or not 1 <= len(wave["units"]) <= 100
                or any(not isinstance(uid, str) or not re.fullmatch(r"[0-9]{1,6}", uid)
                       or type(n) is not int or not 1 <= n <= 10**9
                       for uid, n in wave["units"].items())):
            raise ValueError("Invalid manual attack wave")
        previous = wave["round"]
    return dict(draft)


def validate_attack_inventory(city_id: int, data: object) -> dict[str, object]:
    import re

    if (not isinstance(data, dict) or data.get("city_id") != city_id
            or not isinstance(data.get("city_name"), str) or not 0 < len(data["city_name"]) <= 100
            or type(data.get("available_ships")) is not int or not 0 <= data["available_ships"] <= 10**9
            or not isinstance(data.get("units"), list) or len(data["units"]) > 100):
        raise ValueError("Invalid attack inventory")
    seen = set()
    for row in data["units"]:
        if (not isinstance(row, dict) or set(row) != {"unit_id", "name", "available"}
                or not isinstance(row["unit_id"], str) or not re.fullmatch(r"[0-9]{1,6}", row["unit_id"])
                or row["unit_id"] in seen or not isinstance(row["name"], str)
                or not 0 < len(row["name"]) <= 100 or type(row["available"]) is not int
                or not 0 < row["available"] <= 10**9):
            raise ValueError("Invalid attack troop")
        seen.add(row["unit_id"])
    return {k: data[k] for k in ("city_id", "city_name", "available_ships", "units")}


def validate_attack_plan(city_id: int, draft: dict[str, object], plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or plan.get("target_city_id") != draft["target_city_id"]
            or any(not isinstance(plan.get(k), str) or not 0 < len(plan[k]) <= 100
                   for k in ("city_name", "target_name"))
            or type(plan.get("level")) is not int or not 1 <= plan["level"] <= 1000
            or any(type(plan.get(k)) is not int or not 0 <= plan[k] <= 10**12
                   for k in ("required_ships", "available_ships"))
            or type(plan.get("ready")) is not bool
            or (plan["ready"] and plan["available_ships"] < plan["required_ships"])
            or not isinstance(plan.get("waves"), list) or len(plan["waves"]) != len(draft["waves"])):
        raise ValueError("Invalid manual attack preview")
    total_ships = 0
    for wave, requested in zip(plan["waves"], draft["waves"]):
        if (not isinstance(wave, dict) or set(wave) != {"round", "loot", "ships", "transport_ships", "units"}
                or any(wave[k] != requested[k] for k in ("round", "loot", "ships"))
                or type(wave["transport_ships"]) is not int or not 0 <= wave["transport_ships"] <= 10**12
                or not isinstance(wave["units"], list) or len(wave["units"]) != len(requested["units"])):
            raise ValueError("Invalid manual wave preview")
        for row in wave["units"]:
            if (not isinstance(row, dict) or set(row) != {"name", "amount"}
                    or not isinstance(row["name"], str) or not 0 < len(row["name"]) <= 100
                    or type(row["amount"]) is not int or not 0 < row["amount"] <= 10**9):
                raise ValueError("Invalid troop quantity")
        if sorted(r["amount"] for r in wave["units"]) != sorted(requested["units"].values()):
            raise ValueError("Manual wave quantity mismatch")
        total_ships += wave["transport_ships"] + wave["ships"]
    if total_ships != plan["required_ships"]:
        raise ValueError("Manual attack ship mismatch")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", *draft, "expected"}
            or config["city_id"] != city_id or any(config.get(k) != v for k, v in draft.items())
            or not isinstance(config["expected"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid manual attack fingerprint")
    return {k: plan[k] for k in ("city_id", "target_city_id", "city_name", "target_name", "level",
                                 "waves", "available_ships", "required_ships", "ready", "config")}

def validate_vacation_plan(city_id: int, plan: object) -> dict[str, object]:
    import re

    if (not isinstance(plan, dict) or plan.get("city_id") != city_id
            or not isinstance(plan.get("city_name"), str) or not 0 < len(plan["city_name"]) <= 100
            or type(plan.get("active_jobs")) is not int or not 0 <= plan["active_jobs"] <= 10000
            or plan.get("ready") is not (plan["active_jobs"] == 0)):
        raise ValueError("Invalid vacation preview")
    config = plan.get("config")
    if (not isinstance(config, dict) or set(config) != {"city_id", "expected"}
            or config["city_id"] != city_id or not isinstance(config["expected"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", config["expected"])):
        raise ValueError("Invalid vacation fingerprint")
    return {k: plan[k] for k in ("city_id", "city_name", "active_jobs", "ready", "config")}


def validated_coordinates(x: object, y: object) -> tuple[int, int]:
    if any(type(v) is not int or not 1 <= v <= 100 for v in (x, y)):
        raise ValueError("Choose coordinates between 1 and 100")
    return x, y


def validate_island_destinations(x: int, y: int, result: object) -> list[dict[str, object]]:
    if (not isinstance(result, dict) or result.get("x") != x or result.get("y") != y
            or not isinstance(result.get("cities"), list) or len(result["cities"]) > 100):
        raise ValueError("Invalid island inventory")
    seen = set()
    islands = set()
    for row in result["cities"]:
        if (not isinstance(row, dict) or set(row) != {"id", "recipient", "island", "name", "owner"}
                or any(type(row[k]) is not int or not 0 < row[k] < 10**12 for k in ("id", "recipient", "island"))
                or row["id"] in seen or any(not isinstance(row[k], str) or not 0 < len(row[k]) <= 120
                                            for k in ("name", "owner"))):
            raise ValueError("Invalid recipient")
        seen.add(row["id"])
        islands.add(row["island"])
    if len(islands) > 1:
        raise ValueError("Mixed island inventory")
    return result["cities"]


def validated_shipment_draft(draft: object) -> dict[str, object]:
    if (not isinstance(draft, dict) or set(draft) != {"routes", "useFreighters"}
            or type(draft["useFreighters"]) is not bool
            or not isinstance(draft["routes"], list) or not 1 <= len(draft["routes"]) <= 20):
        raise ValueError("Invalid shipment draft")
    totals = {}
    for route in draft["routes"]:
        if (not isinstance(route, dict) or set(route) not in (
                {"from", "to", "resources"}, {"from", "to", "resources", "island", "recipient"})
                or any(type(route[k]) is not int or not 0 < route[k] < 10**12
                       for k in set(route) - {"resources"})
                or route["from"] == route["to"] or not isinstance(route["resources"], list)
                or len(route["resources"]) != 5 or any(type(v) is not int or not 0 <= v <= 10**9
                                                       for v in route["resources"])
                or not any(route["resources"])):
            raise ValueError("Invalid shipment route")
        totals[route["from"]] = [a+b for a,b in zip(totals.get(route["from"], [0]*5), route["resources"])]
        if any(v > 10**9 for v in totals[route["from"]]):
            raise ValueError("Aggregate cargo exceeds the limit")
    return draft


def validate_shipment_plan(draft: dict[str, object], plan: object) -> dict[str, object]:
    if (not isinstance(plan, dict) or plan.get("useFreighters") is not draft["useFreighters"]
            or any(type(plan.get(k)) is not int or not 0 <= plan[k] <= 10**8
                   for k in ("capacity", "available_ships", "total_ships"))
            or plan["available_ships"] > plan["total_ships"]
            or plan.get("ready") is not bool(plan["capacity"] and plan["total_ships"])
            or not isinstance(plan.get("routes"), list) or len(plan["routes"]) != len(draft["routes"])):
        raise ValueError("Invalid fleet observation")
    for requested, row in zip(draft["routes"], plan["routes"]):
        if (not isinstance(row, dict) or set(row) - {"first_load_timing"} != {"from", "to", "origin_name", "destination_name",
                "resources", "stock", "destination_space", "first_load_limit", "minimum_loads"}
                or any(row[k] != requested[k] for k in ("from", "to", "resources"))
                or any(not isinstance(row[k], str) or not 0 < len(row[k]) <= 250
                       for k in ("origin_name", "destination_name"))
                or not _resources(row["stock"])
                or ("recipient" in requested and row["destination_space"] is not None)
                or ("recipient" not in requested and not _resources(row["destination_space"]))):
            raise ValueError("Invalid shipment observation")
        cargo = sum(row["resources"])
        expected = min(cargo, plan["capacity"] * plan["available_ships"])
        if row["destination_space"] is not None:
            expected = min(expected, sum(min(a, b) for a, b in zip(row["resources"], row["destination_space"])))
        full = plan["capacity"] * plan["total_ships"]
        loads = (cargo+full-1)//full if full else None
        if (type(row["first_load_limit"]) is not int or row["first_load_limit"] != expected
                or row["minimum_loads"] != loads):
            raise ValueError("Invalid shipment capacity calculation")
        timing = row.get("first_load_timing")
        if timing is not None:
            seconds = ("total_seconds", "loading_seconds", "travel_seconds", "queue_seconds")
            if (not isinstance(timing, dict) or set(timing) != {"cargo", *seconds}
                    or type(timing["cargo"]) is not int or timing["cargo"] != expected or not expected
                    or any(type(timing[k]) is not int or not 0 <= timing[k] <= 365 * 86400 for k in seconds)
                    or timing["travel_seconds"] <= 0
                    or timing["total_seconds"] != sum(timing[k] for k in seconds[1:])):
                raise ValueError("Invalid first-load timing")

    totals = {}
    for row in plan["routes"]:
        previous, stock = totals.get(row["from"], ([0]*5, row["stock"]))
        if stock != row["stock"]:
            raise ValueError("Stock changed during preview")
        total = [a+b for a,b in zip(previous,row["resources"])]
        if any(a>b for a,b in zip(total, stock)):
            raise ValueError("Insufficient source stock")
        totals[row["from"]] = (total, stock)
    return {k:plan[k] for k in ("routes","useFreighters","capacity","available_ships","total_ships","ready")}



def validated_construction_supply(city_id, value):
    if (not isinstance(value, dict) or set(value) != {"source_ids", "useFreighters", "round_up", "supply_only"}
            or any(type(value[k]) is not bool for k in ("useFreighters", "round_up", "supply_only"))
            or not isinstance(value["source_ids"], list) or not 1 <= len(value["source_ids"]) <= 20
            or any(type(v) is not int or not 0 < v < 10**12 or v == city_id for v in value["source_ids"])
            or len(set(value["source_ids"])) != len(value["source_ids"])):
        raise ValueError("Invalid construction suppliers")
    return value


def validate_construction_supply(city_id, options, numbers, plan, config):
    """Independently verify shortage coverage, storage and exact reviewed cargo."""
    supply = plan.get("supply")
    if (not isinstance(supply, dict) or set(supply) != {"options", "target", "remaining", "shipment", "destination_space"}
            or supply["options"] != options or not _resources(supply["target"])
            or not _resources(supply["remaining"]) or not _resources(supply["destination_space"])
            or config.get("supply_review") != {"options": options, "costs": numbers["costs"]}
            or config.get("expand_overall") is not (not options["supply_only"])
            or config.get("wait_resources") is not (not options["supply_only"])
            or not isinstance(config.get("shipments"), list)):
        raise ValueError("Invalid construction supply preview")
    missing = [max(0, a-b) for a,b in zip(numbers["costs"], numbers["available"])]
    if numbers["missing"] != missing:
        raise ValueError("Invalid construction shortage")
    def round_up(n):
        unit = 100 if n < 1000 else 500 if n < 10000 else 1000
        return (n+unit-1)//unit*unit
    target = [min(space, round_up(n) if options["round_up"] else n)
              for space,n in zip(supply["destination_space"], missing)]
    if supply["target"] != target:
        raise ValueError("Invalid supply target")
    routes = config["shipments"]
    shipment = supply["shipment"]
    if routes:
        clean = validated_shipment_draft({"routes": routes, "useFreighters": options["useFreighters"]})
        if any(set(r) != {"from", "to", "resources"} or r["to"] != city_id
               or r["from"] not in options["source_ids"] for r in routes):
            raise ValueError("Invalid construction supply route")
        origins = [r["from"] for r in routes]
        if origins != [cid for cid in options["source_ids"] if cid in origins]:
            raise ValueError("Invalid construction supplier order")
        verified = validate_shipment_plan(clean, shipment)
        left = target.copy()
        for route, row in zip(routes, verified["routes"]):
            if row["destination_space"] != supply["destination_space"] or route["resources"] != [
                min(n, stock, 10**9) for n,stock in zip(left, row["stock"])
            ]:
                raise ValueError("Invalid construction cargo allocation")
            left = [n-v for n,v in zip(left, route["resources"])]
        sent = [a-b for a,b in zip(target,left)]
    else:
        if shipment is not None:
            raise ValueError("Unexpected construction cargo")
        verified = None
        sent = [0]*5
    remaining = [max(0, a-b) for a,b in zip(missing,sent)]
    if supply["remaining"] != remaining or plan["ready"] is not (not any(remaining) and bool(verified and verified["ready"])):
        raise ValueError("Invalid construction supply readiness")
    return supply
