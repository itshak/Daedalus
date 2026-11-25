"""Review bounded recruitment batches from authenticated engine catalogs."""
from __future__ import annotations

import math
import re

RESOURCES = ("wood", "wine", "marble", "crystal", "sulfur", "citizens")


def training_draft(value: object) -> dict[str, object]:
    if (not isinstance(value, dict) or set(value) != {"city_ids", "train_troops", "rounds", "cycles"}
            or type(value["train_troops"]) is not bool or type(value["cycles"]) is not int
            or not 1 <= value["cycles"] <= 10):
        raise ValueError("Invalid recruitment draft")
    ids, rounds = value["city_ids"], value["rounds"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 32
            or any(type(cid) is not int or not 0 < cid < 10**12 for cid in ids)
            or len(set(ids)) != len(ids) or not isinstance(rounds, list) or not 1 <= len(rounds) <= 10
            or len(ids) * len(rounds) * value["cycles"] > 200):
        raise ValueError("Invalid recruitment scope")
    for group in rounds:
        if not isinstance(group, list) or not 1 <= len(group) <= 50:
            raise ValueError("Invalid recruitment round")
        seen = set()
        for row in group:
            if (not isinstance(row, dict) or set(row) != {"unit_type_id", "cantidad"}
                    or type(row["unit_type_id"]) is not int or not 0 < row["unit_type_id"] < 10**7
                    or row["unit_type_id"] in seen or type(row["cantidad"]) is not int
                    or not 1 <= row["cantidad"] <= 100000):
                raise ValueError("Invalid recruitment unit")
            seen.add(row["unit_type_id"])
    return dict(value)


def build_training_review(account_id, draft, catalogs):
    """Use only the engine's scoped, current catalog; no game writes."""
    draft = training_draft(draft)
    if len(catalogs) != len(draft["city_ids"]):
        raise ValueError("Incomplete recruitment inventory")
    rows, jobs = [], []
    for cid, catalog in zip(draft["city_ids"], catalogs):
        if (catalog.get("account_id") != account_id or catalog.get("city_id") != cid
                or catalog.get("train_troops") is not draft["train_troops"]):
            raise ValueError("Recruitment inventory scope changed")
        city = catalog["city"]
        if (city.get("id") != str(cid) or not isinstance(city.get("pos"), str)
                or not re.fullmatch(r"[0-9]{1,2}", city["pos"]) or int(city["pos"]) > 80
                or not isinstance(city.get("cityName"), str) or not 0 < len(city["cityName"]) <= 100):
            raise ValueError("Invalid recruiting building")
        city = {k: city[k] for k in ("id", "pos", "cityName")}
        units = {u["unit_type_id"]: u for u in catalog["units"]}
        stocks = [*catalog["available"], catalog["free_citizens"]]
        if len(stocks) != 6 or any(type(v) is not int or not 0 <= v <= 10**15 for v in stocks):
            raise ValueError("Invalid recruitment stock")
        rounds, costs = [], []
        for group in draft["rounds"]:
            selected = []
            for item in group:
                unit = units.get(item["unit_type_id"])
                if unit is None:
                    raise ValueError("Selected unit unavailable in a selected city")
                if (not isinstance(unit.get("local_name"), str) or not 0 < len(unit["local_name"]) <= 100
                        or not isinstance(unit.get("costs"), dict)
                        or not set(unit["costs"]) <= set(RESOURCES) | {"upkeep", "completiontime"}
                        or any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 10**9
                               for v in unit["costs"].values())):
                    raise ValueError("Invalid recruitment unit observation")
                selected.append({**item, "local_name": unit["local_name"], "costs": unit["costs"]})
            rounds.append(selected)
            costs.append([sum(u["costs"].get(k, 0)*u["cantidad"] for u in selected) for k in RESOURCES])
        jobs.append({"city": city, "rounds": rounds})
        rows.append({"city_id": cid, "city_name": city["cityName"], "position": int(city["pos"]),
                     "rounds": rounds, "stock": stocks, "round_costs": costs,
                     "total_costs": [sum(col)*draft["cycles"] for col in zip(*costs)],
                     "ready": all(a <= b for a,b in zip(costs[0], stocks))})
    config = {"city": jobs[0]["city"], "tranings": [draft["rounds"][0]],
              "trainTroops": draft["train_troops"], "replicate": "n", "countRepeat": 0,
              "cityTrainings": [], "units": [],
              "reviewed_jobs": {"cycles": draft["cycles"], "jobs": jobs}}
    from daedalus.task_control import validated_configuration

    validated_configuration(config)
    return {"account_id": account_id, **draft, "cities": rows, "ready": all(r["ready"] for r in rows),
            "config": config}


def validate_training_review(account_id, draft, plan):
    draft = training_draft(draft)
    if (not isinstance(plan, dict) or plan.get("account_id") != account_id
            or any(plan.get(k) != v for k,v in draft.items()) or not isinstance(plan.get("cities"), list)
            or len(plan["cities"]) != len(draft["city_ids"])):
        raise ValueError("Invalid recruitment review")
    catalogs = []
    for row in plan["cities"]:
        if not isinstance(row, dict) or not isinstance(row.get("rounds"), list):
            raise ValueError("Invalid recruitment city")  # noqa: TRY004 - malformed remote observation
        units = {}
        for group in row["rounds"]:
            if not isinstance(group, list):
                raise ValueError("Invalid recruitment round")  # noqa: TRY004 - malformed remote observation
            for u in group:
                if not isinstance(u, dict) or set(u) != {"unit_type_id", "cantidad", "local_name", "costs"}:
                    raise ValueError("Invalid recruitment unit")
                units[u["unit_type_id"]] = u
        catalogs.append({"account_id": account_id, "city_id": row["city_id"],
                         "city": {"id": str(row["city_id"]), "cityName": row["city_name"],
                                  "pos": str(row["position"])}, "train_troops": draft["train_troops"],
                         "units": list(units.values()), "available": row["stock"][:5],
                         "free_citizens": row["stock"][5]})
    expected = build_training_review(account_id, draft, catalogs)
    expected.pop("config")
    if any(plan.get(k) != v for k,v in expected.items()):
        raise ValueError("Recruitment review changed")
    if plan["ready"] and (not isinstance(plan.get("preview_id"), str)
                          or not re.fullmatch(r"[A-Za-z0-9_-]{43}", plan["preview_id"])
                          or type(plan.get("expires_in")) is not int or not 1 <= plan["expires_in"] <= 120):
        raise ValueError("Invalid recruitment ticket")
    return expected
