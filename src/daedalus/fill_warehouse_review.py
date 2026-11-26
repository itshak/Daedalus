"""Account-specific, independently checked warehouse fill allocation."""
from daedalus.daily_distribution_review import _city

TASK = "fillCityWarehouse"
RESOURCES = ("wood", "wine", "marble", "crystal", "sulfur")
FILL_PREVIEW_MESSAGES = {
    "fill_destination_unavailable": "Destination warehouse could not be read. Refresh city data and retry.",
    "fill_incoming_unavailable": "Incoming cargo could not be verified. No transfer was started.",
    "fill_source_unavailable": "Source city stock could not be read. Refresh city data and retry.",
    "fill_fleet_unavailable": "Selected fleet is unavailable or its capacity could not be verified.",
}



def draft_fill(v):
    if (not isinstance(v, dict) or set(v) != {"destination_city", "resource", "useFreighters"}
            or v["resource"] not in RESOURCES or type(v["useFreighters"]) is not bool):
        raise ValueError("Choose a destination, resource and fleet")
    return {**v, "destination_city": _city(v["destination_city"])}


def amount(v, max_value=10**12):
    return type(v) is int and 0 <= v <= max_value


def name(v):
    return isinstance(v, str) and 0 < len(v) <= 120 and not any(ord(c) < 32 or c in "<>" for c in v)


def validate_fill(d, o):
    keys = {"destination_city", "destination_name", "stock", "free_space", "incoming",
            "budget", "amount", "sources", "capacity", "total_ships", "available_ships"}
    if (not isinstance(o, dict) or set(o) != keys or o["destination_city"] != d["destination_city"]
            or not name(o["destination_name"]) or any(not amount(o[k]) for k in ("stock", "free_space", "incoming", "budget", "amount"))
            or o["budget"] != max(0, o["free_space"]-o["incoming"])
            or any(not amount(o[k], 10**8) for k in ("capacity", "total_ships", "available_ships"))
            or o["available_ships"] > o["total_ships"] or not isinstance(o["sources"], list)
            or not 0 <= len(o["sources"]) <= 99):
        raise ValueError("Invalid fill observation")
    remaining, last = o["budget"], 0
    for row in o["sources"]:
        if (not isinstance(row, dict) or set(row) != {"city_id", "city_name", "stock", "amount"}
                or type(row["city_id"]) is not int or not last < row["city_id"] < 10**12
                or row["city_id"] == d["destination_city"] or not name(row["city_name"])
                or not amount(row["stock"]) or not amount(row["amount"])
                or row["amount"] != min(remaining, row["stock"])):
            raise ValueError("Invalid source allocation")
        last = row["city_id"]
        remaining -= row["amount"]
    if o["amount"] != o["budget"]-remaining or o["amount"] and not (o["capacity"] and o["total_ships"]):
        raise ValueError("Invalid warehouse budget or fleet")
    return o


def fill_summary(d, o):
    validate_fill(d, o)
    lines = [f"{o['destination_name']} · {d['resource']}",
             f"Current stock: {o['stock']:,}; free space: {o['free_space']:,}; incoming: {o['incoming']:,}",
             f"Available budget: {o['budget']:,}; planned transfer: {o['amount']:,}",
             f"{o['available_ships']:,}/{o['total_ships']:,} vessels free; {o['capacity']:,} per vessel."]
    lines += [f"{r['city_name']}: {r['amount']:,} of {r['stock']:,}" for r in o["sources"]]
    lines.append("One-time transfer. Current storage and incoming cargo rechecked before every load. No automatic replay.")
    return "\n".join(lines)
