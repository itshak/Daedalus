"""Bounded review of recurring policies, not a promise of future game effects."""
import re

from daedalus.daily_distribution_review import _city

RECURRING_TASKS = frozenset({
    "consolidateResources", "resourceTransportManager", "donationBot",
    "searchForIslandSpaces", "dumpWorld", "autoPirate",
})
COORD = re.compile(r"(?:[1-9][0-9]?|100):(?:[1-9][0-9]?|100)")
MAX_AMOUNT = 10**9


def integer(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def ids(v):
    if not isinstance(v, list) or not 1 <= len(v) <= 100:
        raise ValueError("Choose actual cities")
    result = [_city(i) for i in v]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate city")
    return result


def amounts(v, lo=0, nullable=False):
    if not isinstance(v, list) or len(v) != 5 or any(
        not (nullable and n is None) and not integer(n, lo, MAX_AMOUNT) for n in v
    ):
        raise ValueError("Invalid resource policy")
    return v


def recurring_draft(task, v):
    if not isinstance(v, dict) or task not in RECURRING_TASKS:
        raise ValueError("Invalid recurring policy")
    if task == "consolidateResources":
        if (set(v) != {"limits", "sourceCityIds", "destinationCityId", "intervalInHours", "shipType"}
                or not integer(v["intervalInHours"], 1, 336) or not integer(v["shipType"], 1, 3)):
            raise ValueError("Invalid consolidation policy")
        origins, target = ids(v["sourceCityIds"]), _city(v["destinationCityId"])
        if target in origins or all(n == -1 for n in amounts(v["limits"], -1)):
            raise ValueError("Choose distinct routes and a resource")
        return {**v, "sourceCityIds": origins, "destinationCityId": target}
    if task == "resourceTransportManager":
        common = {"mode", "interval_hours", "resource_config", "useFreighters", "notify"}
        if (not common <= set(v) or not integer(v["interval_hours"], 0, 720)
                or type(v["useFreighters"]) is not bool or v["notify"] not in ("none", "start", "all")):
            raise ValueError("Invalid transport policy")
        if v["mode"] == "consolidate":
            required = common | {"origin_cities", "destination_city", "send_mode"}
            if set(v) not in (required, required | {"island", "recipient"}) or v["send_mode"] not in ("keep", "send"):
                raise ValueError("Invalid receiving scope")
            origins, target = ids(v["origin_cities"]), _city(v["destination_city"])
            a = amounts(v["resource_config"], nullable=True)
            if target in origins or not (any(n is not None for n in a) if v["send_mode"] == "keep" else any(a)):
                raise ValueError("Invalid routes or amounts")
            ext = {k: _city(v[k]) for k in ("island", "recipient")} if "recipient" in v else {}
            return {**v, **ext, "origin_cities": origins, "destination_city": target}
        if v["mode"] != "distribute" or set(v) != common | {"origin_city", "destination_cities"}:
            raise ValueError("Invalid transport strategy")
        origin, targets = _city(v["origin_city"]), ids(v["destination_cities"])
        if origin in targets or not any(amounts(v["resource_config"])):
            raise ValueError("Invalid routes or amounts")
        return {**v, "origin_city": origin, "destination_cities": targets}
    if task == "donationBot":
        if (set(v) != {"cities_dict", "waiting_time", "donate_method"}
                or not integer(v["waiting_time"], 1, 10080) or not integer(v["donate_method"], 1, 3)
                or not isinstance(v["cities_dict"], dict) or not 1 <= len(v["cities_dict"]) <= 100):
            raise ValueError("Invalid donation policy")
        for k, row in v["cities_dict"].items():
            if (not isinstance(k, str) or str(_city(k)) != k or not isinstance(row, dict)
                    or set(row) != {"donation_type", "percentage"} or row["donation_type"] not in ("resource", "tradegood", "both")
                    or not integer(row["percentage"], 0, MAX_AMOUNT if v["donate_method"] == 3 else 100)):
                raise ValueError("Invalid donation city or amount")
        return v
    if task == "searchForIslandSpaces":
        if not {"time", "fights"} <= set(v) <= {"time", "fights", "islandList"} or not integer(v["time"], 3, 1440):
            raise ValueError("Invalid island monitoring")
        coords = v.get("islandList", [])
        fights = v["fights"]
        if type(fights) is bool:
            fights = "y" if fights else "n"
        if (fights not in ("y", "n") or not isinstance(coords, list) or len(coords) > 100
                or any(not isinstance(c, str) or not COORD.fullmatch(c) for c in coords)
                or len(set(coords)) != len(coords)):
            raise ValueError("Invalid island selection")
        return {"time": v["time"], "fights": fights, "islandList": coords}
    if task == "dumpWorld":
        if (not {"waiting_time", "shallow", "non_empty_islands"} <= set(v) <= {"waiting_time", "coords", "radius", "shallow", "non_empty_islands"}
                or type(v["waiting_time"]) not in (int, float) or not 1 <= v["waiting_time"] <= 10
                or type(v["shallow"]) is not bool or type(v["non_empty_islands"]) is not bool):
            raise ValueError("Invalid map policy")
        coords, radius = v.get("coords"), v.get("radius")
        if (coords is None and radius is not None or coords is not None and
            (not isinstance(coords, list) or len(coords) != 2 or not all(integer(x, 0, 100) for x in coords)
             or not integer(radius, 0, 200)) or v["shallow"] and (coords is not None or v["non_empty_islands"])):
            raise ValueError("Invalid map scope")
        return {**v, "coords": coords, "radius": radius}
    required = {"pirateCount", "pirateSchedule", "pirateMissionChoice", "pirateMissionDayChoice",
                "pirateMissionNightChoice", "dayStart", "dayEnd", "nightStart", "nightEnd",
                "autoConvert", "convertPerMission", "maxRandomWaitingTime", "piracyCities"}
    if (set(v) != required or not integer(v["pirateCount"], 1, 100000)
            or type(v["pirateSchedule"]) is not bool or not integer(v["maxRandomWaitingTime"], 0, 3600)
            or v["autoConvert"] not in ("y", "n") or not isinstance(v["piracyCities"], list)
            or len(v["piracyCities"]) != 1 or not isinstance(v["piracyCities"][0], dict)
            or set(v["piracyCities"][0]) != {"id"}):
        raise ValueError("Invalid fortress policy")
    convert = v["convertPerMission"]
    if (v["autoConvert"] == "n" and (type(convert) is not int or convert != 0)
            or v["autoConvert"] == "y" and convert != "all" and not integer(convert, 0, MAX_AMOUNT)):
        raise ValueError("Invalid conversion policy")
    hours = ("dayStart", "dayEnd", "nightStart", "nightEnd")
    if v["pirateSchedule"]:
        if (v["pirateMissionChoice"] is not None or not integer(v["pirateMissionDayChoice"], 1, 9)
                or not integer(v["pirateMissionNightChoice"], 1, 9) or any(not integer(v[k], 0, 23) for k in hours)):
            raise ValueError("Invalid mission schedule")
    elif (not integer(v["pirateMissionChoice"], 1, 9) or any(v[k] is not None for k in
            (*hours, "pirateMissionDayChoice", "pirateMissionNightChoice"))):
        raise ValueError("Invalid mission choice")
    return {**v, "piracyCities": [{"id": _city(v["piracyCities"][0]["id"])}]}


def route_scope(task, d):
    if task == "consolidateResources":
        return d["sourceCityIds"], [d["destinationCityId"]]
    if d["mode"] == "consolidate":
        return d["origin_cities"], [d["destination_city"]]
    return [d["origin_city"]], d["destination_cities"]


def named(v):
    return isinstance(v, str) and 0 < len(v) <= 120 and not any(ord(c) < 32 or c in "<>" for c in v)


def validate_recurring(task, d, o):
    if not isinstance(o, dict):
        raise ValueError("Invalid recurring observation")  # noqa: TRY004
    if task in {"consolidateResources", "resourceTransportManager", "donationBot"}:
        if task == "donationBot":
            expected = set(map(int, d["cities_dict"]))
            if set(o) != {"cities"}:
                raise ValueError("Invalid donation observation")
        else:
            source, dest = route_scope(task, d)
            expected = set(source + ([] if "recipient" in d else dest))
            if set(o) != {"cities", "fleets", "external"}:
                raise ValueError("Invalid transport observation")
            ext = o["external"]
            if "recipient" in d:
                if (not isinstance(ext, dict) or set(ext) != {"id", "island", "recipient", "name", "owner"}
                        or any(ext[k] != d[k] for k in ("island", "recipient"))
                        or ext["id"] != dest[0] or not named(ext["name"]) or not named(ext["owner"])):
                    raise ValueError("External recipient changed")
            elif ext is not None:
                raise ValueError("Unexpected external recipient")
            fleet = o["fleets"]
            expected_fleets = (["trade", "freighter"] if d.get("shipType") == 3 else
                ["freighter"] if d.get("shipType") == 2 or d.get("useFreighters") else ["trade"])
            if not isinstance(fleet, dict) or set(fleet) != set(expected_fleets):
                raise ValueError("Invalid fleet scope")
            for row in fleet.values():
                if (not isinstance(row, dict) or set(row) != {"capacity", "free", "total"}
                        or not integer(row["capacity"], 0, 10**8) or not integer(row["total"], 0, 10**8)
                        or not integer(row["free"], 0, row["total"])):
                    raise ValueError("Invalid fleet observation")
            if not any(r["capacity"] and r["total"] for r in fleet.values()):
                raise ValueError("No usable fleet")
        rows = o["cities"]
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("City scope changed")
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"id", "name", "stock", "space", "coords"}
                    or type(row["id"]) is not int or row["id"] not in expected or row["id"] in seen
                    or not named(row["name"]) or not isinstance(row["coords"], str) or not COORD.fullmatch(row["coords"])
                    or any(not isinstance(row[k], list) or len(row[k]) != 5 or
                           any(not integer(n, 0, 10**15) for n in row[k]) for k in ("stock", "space"))):
                raise ValueError("Invalid city observation")
            seen.add(row["id"])
    elif task == "searchForIslandSpaces":
        coords = o.get("islands")
        if (set(o) != {"islands"} or not isinstance(coords, list) or not 1 <= len(coords) <= 100
                or any(not isinstance(c, str) or not COORD.fullmatch(c) for c in coords)
                or len(set(coords)) != len(coords) or d["islandList"] and set(coords) != set(d["islandList"])):
            raise ValueError("Island scope changed")
    elif task == "dumpWorld":
        if o != {"scope": "region" if d["coords"] is not None else "world", "aggregate_only": True}:
            raise ValueError("Invalid map observation")
    else:
        r = o.get("fortress")
        missions = [d["pirateMissionDayChoice"], d["pirateMissionNightChoice"]] if d["pirateSchedule"] else [d["pirateMissionChoice"]]
        if (set(o) != {"fortress", "human_challenge"} or o["human_challenge"] != "stop"
                or not isinstance(r, dict) or set(r) != {"city_id", "city_name", "fortress_level", "missions"}
                or r["city_id"] != d["piracyCities"][0]["id"] or not named(r["city_name"])
                or not integer(r["fortress_level"], 1, 100) or not isinstance(r["missions"], list)
                or not 1 <= len(r["missions"]) <= 9):
            raise ValueError("Invalid fortress observation")
        seen = set()
        for m in r["missions"]:
            if (not isinstance(m, dict) or set(m) != {"number", "duration_seconds"} or not integer(m["number"], 1, 9)
                    or m["number"] in seen or r["fortress_level"] < 2*m["number"]-1
                    or not integer(m["duration_seconds"], 1, 86400)):
                raise ValueError("Invalid mission observation")
            seen.add(m["number"])
        if not set(missions) <= seen:
            raise ValueError("Mission unavailable")
    return o


def recurring_summary(task, d, o):
    validate_recurring(task, d, o)
    resources = ("wood", "wine", "marble", "crystal", "sulfur")
    if "cities" in o:
        by_id = {r["id"]: r["name"] for r in o["cities"]}
        lines = []
        if task == "donationBot":
            method = ("storage percentage to keep", "production percentage to donate", "fixed donation amount")[d["donate_method"]-1]
            lines.append(f"Every {d['waiting_time']} minutes; {method}")
            lines += [f"{by_id[int(cid)]}: {row['donation_type']} = {row['percentage']:,}"
                      for cid, row in d["cities_dict"].items()]
        else:
            source, dest = route_scope(task, d)
            target_names = [by_id[c] if c in by_id else o["external"]["name"] + " — " + o["external"]["owner"] for c in dest]
            lines.append(", ".join(by_id[c] for c in source) + " → " + ", ".join(target_names))
            if task == "consolidateResources":
                lines.append(f"Repeat every {d['intervalInHours']} hours; retain:")
                policy = d["limits"]
            else:
                lines.append(f"Interval {d['interval_hours']} hours (0 once); {d.get('send_mode', 'send')}; notifications {d['notify']}")
                policy = d["resource_config"]
            lines.append("; ".join(f"{k}: {n:,}" if n not in (None, -1) else f"{k}: ignore" for k, n in zip(resources, policy)))
        lines += [f"{r['name']} ({r['coords']}): stock " + " / ".join(f"{n:,}" for n in r["stock"])
                  + "; free space " + " / ".join(f"{n:,}" for n in r["space"]) for r in o["cities"]]
        lines.append("Resource order: wood / wine / marble / crystal / sulfur. Current inventory, not guaranteed future cargo or donation.")
        for name, row in o.get("fleets", {}).items():
            lines.append(f"{name}: {row['free']}/{row['total']} free, {row['capacity']:,} cargo per ship")
        if o.get("external"):
            lines.append("External destination: " + o["external"]["name"] + " — " + o["external"]["owner"] + "; storage unknown")
        return "\n".join(lines)
    if task == "searchForIslandSpaces":
        return f"Every {d['time']} minutes; fights: {d['fights']}; " + ("explicit selection" if d["islandList"] else "all owned islands") + "\nVerified islands: " + ", ".join(o["islands"])
    if task == "dumpWorld":
        area = f"Region {d['coords']} radius {d['radius']}" if d["coords"] is not None else "Whole world"
        return f"{area}; delay {d['waiting_time']} seconds; shallow: {d['shallow']}; occupied only: {d['non_empty_islands']}. Private aggregate report."
    r = o["fortress"]
    missions = {m["number"]: m["duration_seconds"] for m in r["missions"]}
    if d["pirateSchedule"]:
        schedule = f"Day mission {d['pirateMissionDayChoice']} ({d['dayStart']}–{d['dayEnd']}); night {d['pirateMissionNightChoice']} ({d['nightStart']}–{d['nightEnd']})"
    else:
        mission = d["pirateMissionChoice"]
        schedule = f"Mission {mission} ({missions[mission]} seconds)"
    return f"{r['city_name']}: fortress level {r['fortress_level']}; {d['pirateCount']} missions. {schedule}; conversion: {d['convertPerMission']}. Stops at a human challenge."
