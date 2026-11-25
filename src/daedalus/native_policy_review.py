"""Exact scoped observations for native research, tavern, faith and workshop policies."""
import re

from daedalus.daily_distribution_review import _city
from daedalus.recurring_review import (
    RECURRING_TASKS,
    recurring_draft,
    recurring_summary,
    validate_recurring,
)
from daedalus.research_choices import validate_study_choice
from daedalus.tavern_choices import fixed_tavern_review, validate_fixed_tavern

POLICY_TASKS = RECURRING_TASKS | {"research", "tavernManager", "activateMiracle", "activateShrine", "UpgradeUnits"}


def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def _ids(value, maximum=100):
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise ValueError("Choose actual cities")
    result = [_city(v) for v in value]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate city")
    return result


def _name(value):
    return isinstance(value, str) and 0 < len(value) <= 160 and not any(ord(c) < 32 or c in "<>" for c in value)


def policy_draft(task, value):
    if task not in POLICY_TASKS or not isinstance(value, dict):
        raise ValueError("Invalid native policy")
    if task in RECURRING_TASKS:
        return recurring_draft(task, value)
    if task == "research":
        if set(value) == {"study_choice"}:
            return {"study_choice": validate_study_choice(value["study_choice"])}
        if not {"cities_ids"} <= set(value) <= {"cities_ids", "qty"}:
            raise ValueError("Invalid experiment policy")
        ids, qty = _ids(value["cities_ids"]), value.get("qty")
        if qty is not None and (not _integer(qty, 1, 10000) or len(ids) != 1):
            raise ValueError("Choose one academy for fixed experiments")
        return {"cities_ids": ids, "qty": qty}
    if task == "tavernManager":
        if set(value) == {"run_hours", "fixed_servings"} and type(value["run_hours"]) is int and value["run_hours"] == 0:
            return {"run_hours": 0, "fixed_servings": validate_fixed_tavern(value["fixed_servings"])}
        if (not {"run_hours"} <= set(value) <= {"cities_ids", "run_hours", "notification_mode"}
                or not _integer(value["run_hours"], 0, 24) or not _integer(value.get("notification_mode", 2), 1, 3)):
            raise ValueError("Invalid tavern policy")
        return {"cities_ids": _ids(value["cities_ids"]) if value.get("cities_ids") is not None else None,
                "run_hours": value["run_hours"], "notification_mode": value.get("notification_mode", 2)}
    if task == "activateMiracle":
        if (set(value) != {"wonder", "iterations"} or value["wonder"] not in tuple("12345678")
                or not _integer(value["iterations"], 1, 100)):
            raise ValueError("Invalid miracle policy")
        return value
    if task == "activateShrine":
        if not {"godids", "mode"} <= set(value) <= {"godids", "mode", "times"}:
            raise ValueError("Invalid shrine policy")
        gods, mode, times = value["godids"], value["mode"], value.get("times", 0)
        if (not isinstance(gods, list) or not 1 <= len(gods) <= 6 or any(not _integer(g, 1, 6) for g in gods)
                or len(set(gods)) != len(gods) or not _integer(mode, 1, 3)
                or not _integer(times, 0 if mode == 2 else 1, 0 if mode == 2 else 10)):
            raise ValueError("Invalid shrine schedule")
        return {"godids": gods, "mode": mode, "times": times}
    if set(value) != {"jobs"} or not isinstance(value["jobs"], list) or len(value["jobs"]) != 1:
        raise ValueError("Choose one workshop")
    job = value["jobs"][0]
    if not isinstance(job, dict) or set(job) != {"city_id", "upgrades"} or not isinstance(job["upgrades"], list) or not 1 <= len(job["upgrades"]) <= 50:
        raise ValueError("Choose workshop upgrades")
    seen = set()
    for row in job["upgrades"]:
        if (not isinstance(row, dict) or set(row) != {"unitId", "upgradeType", "target"}
                or not isinstance(row["unitId"], str) or not re.fullmatch(r"[0-9]{1,16}", row["unitId"])
                or not isinstance(row["upgradeType"], str) or not re.fullmatch(r"[A-Za-z_]{1,40}", row["upgradeType"])
                or not _integer(row["target"], 1, 25) or (row["unitId"], row["upgradeType"]) in seen):
            raise ValueError("Invalid workshop target")
        seen.add((row["unitId"], row["upgradeType"]))
    return {"jobs": [{"city_id": _city(job["city_id"]), "upgrades": job["upgrades"]}]}


def observe_policy(ipc, account, task, draft):
    """Use only account-attested existing read-only inventories."""
    if task in RECURRING_TASKS:
        if task == "autoPirate":
            fortress = next((r for r in ipc.pirate_fortresses(account)["fortresses"]
                             if r["city_id"] == draft["piracyCities"][0]["id"]), None)
            return validate_recurring(task, draft, {"fortress": fortress, "human_challenge": "stop"})
        return validate_recurring(task, draft, ipc.recurring_preview(account, task, draft))
    if task == "research":
        data = ipc.academies(account)
        if "study_choice" in draft:
            choice = draft["study_choice"]
            if choice not in (data.get("studies") or []):
                raise ValueError("Study changed; refresh")
            observation = {"study": choice}
        else:
            observation = {"academies": [{k:r[k] for k in ("city_id", "city_name", "crystal", "cooldown", "can_experiment_now")}
                                          for r in data["academies"] if r["city_id"] in draft["cities_ids"]]}
    elif task == "tavernManager":
        data = ipc.taverns(account)
        if "fixed_servings" in draft:
            fixed = draft["fixed_servings"]
            by_id = {r["city_id"]:r for r in data["taverns"] if r["has_tavern"]}
            if any(r["city_id"] not in by_id for r in fixed["rows"]):
                raise ValueError("Tavern unavailable")
            observation = {"fixed_servings": fixed_tavern_review([by_id[r["city_id"]] for r in fixed["rows"]], fixed["percentage"])}
        else:
            observation = {"taverns": [{k:r[k] for k in ("city_id", "city_name", "wine", "serving_level", "wine_per_hour")}
                                       for r in data["taverns"] if r["has_tavern"] and
                                       (draft["cities_ids"] is None or r["city_id"] in draft["cities_ids"])]}
    elif task == "activateMiracle":
        observation = {"miracle": next((r for r in ipc.miracles(account)["miracles"] if r["wonder"] == draft["wonder"]), None)}
    elif task == "activateShrine":
        observation = {"shrine": ipc.shrine_status(account)["shrine"], "favor_per_cycle": 100 * len(draft["godids"])}
    else:
        job = draft["jobs"][0]
        data = ipc.workshop_upgrades(account, job["city_id"])
        selected = []
        for choice in job["upgrades"]:
            row = next((r for r in data["upgrades"] if r["unit_id"] == choice["unitId"] and r["upgrade_type"] == choice["upgradeType"]), None)
            if row is None:
                raise ValueError("Workshop option unavailable")
            selected.append({**row, "target": choice["target"]})
        observation = {"city_id": job["city_id"], "upgrades": selected}
    return validate_policy_observation(task, draft, observation)


def validate_policy_observation(task, draft, value):
    if task in RECURRING_TASKS:
        return validate_recurring(task, draft, value)
    if not isinstance(value, dict):
        raise ValueError("Invalid policy observation")  # noqa: TRY004 - invalid remote observation
    if task == "research":
        if "study_choice" in draft:
            if value != {"study": draft["study_choice"]}:
                raise ValueError("Study changed")
        else:
            rows = value.get("academies")
            if (set(value) != {"academies"} or not isinstance(rows, list) or len(rows) != len(draft["cities_ids"])
                    or any(not isinstance(r, dict) or set(r) != {"city_id", "city_name", "crystal", "cooldown", "can_experiment_now"}
                           or not _name(r["city_name"]) or not _integer(r["crystal"], 0, 10**15)
                           or type(r["cooldown"]) is not bool or type(r["can_experiment_now"]) is not bool
                           or (r["can_experiment_now"] and (r["cooldown"] or r["crystal"] < 300000))
                           or (draft["qty"] is not None and r["crystal"] < 300000) for r in rows)
                    or set(_ids([r["city_id"] for r in rows])) != set(draft["cities_ids"])):
                raise ValueError("Invalid academy observation")
    elif task == "tavernManager":
        if "fixed_servings" in draft:
            if value != {"fixed_servings": draft["fixed_servings"]}:
                raise ValueError("Tavern serving changed")
        else:
            rows = value.get("taverns")
            if (set(value) != {"taverns"} or not isinstance(rows, list) or not 1 <= len(rows) <= 100
                    or any(not isinstance(r, dict) or set(r) != {"city_id", "city_name", "wine", "serving_level", "wine_per_hour"}
                           or not _name(r["city_name"]) or not _integer(r["wine"], 0, 10**15)
                           or not _integer(r["serving_level"], 0, 150) or not _integer(r["wine_per_hour"], 0, 10**9) for r in rows)):
                raise ValueError("Invalid tavern observation")
            ids = _ids([r["city_id"] for r in rows])
            if draft["cities_ids"] is not None and set(ids) != set(draft["cities_ids"]):
                raise ValueError("Tavern scope changed")
    elif task == "activateMiracle":
        r = value.get("miracle")
        if (set(value) != {"miracle"} or not isinstance(r, dict) or set(r) != {"city_id", "temple_city", "island_id", "wonder", "wonder_name", "level", "available", "available_in_seconds"}
                or r["wonder"] != draft["wonder"] or not _name(r["temple_city"]) or not _name(r["wonder_name"])
                or not isinstance(r["island_id"], str) or not re.fullmatch(r"[0-9]{1,30}", r["island_id"])
                or not _integer(r["city_id"], 1, 10**12-1) or not _integer(r["level"], 0, 5)
                or type(r["available"]) is not bool or not _integer(r["available_in_seconds"], 0, 7*86400)):
            raise ValueError("Invalid miracle observation")
    elif task == "activateShrine":
        r = value.get("shrine")
        if (set(value) != {"shrine", "favor_per_cycle"} or value["favor_per_cycle"] != 100*len(draft["godids"])
                or not isinstance(r, dict) or set(r) != {"city_id", "city_name", "position", "favor"}
                or not _name(r["city_name"]) or not _integer(r["city_id"], 1, 10**12-1)
                or not _integer(r["position"], 0, 80) or not _integer(r["favor"], 0, 10**12)):
            raise ValueError("Invalid shrine observation")
    else:
        job = draft["jobs"][0]
        rows = value.get("upgrades")
        if (set(value) != {"city_id", "upgrades"} or value["city_id"] != job["city_id"]
                or not isinstance(rows, list) or len(rows) != len(job["upgrades"])):
            raise ValueError("Invalid workshop scope")
        for choice, row in zip(job["upgrades"], rows):
            if (not isinstance(row, dict) or set(row) != {"unit_id", "name", "upgrade_type", "description", "current_level", "max_level", "target"}
                    or row["unit_id"] != choice["unitId"] or row["upgrade_type"] != choice["upgradeType"]
                    or row["target"] != choice["target"] or not _name(row["name"])
                    or not isinstance(row["description"], str) or len(row["description"]) > 100
                    or not _integer(row["current_level"], 0, 24) or not _integer(row["max_level"], row["target"], 25)
                    or row["current_level"] >= row["target"]):
                raise ValueError("Workshop target changed")
    return value


def policy_summary(task, draft, value):
    if task in RECURRING_TASKS:
        return recurring_summary(task, draft, value)
    validate_policy_observation(task, draft, value)
    if task == "research":
        if "study" in value:
            return "Verified study: " + value["study"]["name"]
        return "\n".join(f"{r['city_name']}: {r['crystal']:,} crystal; cooldown: {r['cooldown']}; ready: {r['can_experiment_now']}" for r in value["academies"])
    if task == "tavernManager":
        if "fixed_servings" in value:
            return "\n".join(f"{r['city_name']}: {r['current_level']} → {r['target_level']}; wine/hour {r['current_wine']} → {r['target_wine']}" for r in value["fixed_servings"]["rows"])
        return "\n".join(f"{r['city_name']}: wine {r['wine']:,}; serving {r['serving_level']}; wine/hour {r['wine_per_hour']}" for r in value["taverns"])
    if task == "activateMiracle":
        r = value["miracle"]
        return f"{r['wonder_name']} · {r['temple_city']} · level {r['level']}; available in {r['available_in_seconds']} seconds"
    if task == "activateShrine":
        r = value["shrine"]
        return f"{r['city_name']}: {r['favor']:,} observed favour; {value['favor_per_cycle']} per cycle"
    return "\n".join(f"{r['name']} ({r['upgrade_type']}): level {r['current_level']} → {r['target']}" for r in value["upgrades"])
