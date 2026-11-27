"""Strict public projection for read-only existing-session workforce observations."""

RESOURCES = frozenset({"wine", "marble", "crystal", "sulfur"})
SITES = frozenset({"resource", "tradegood", "academy", "temple"})


def _count(value, upper):
    return value is None or type(value) is int and 0 <= value <= upper


def validate_production_inventory(city_id, data):
    if (type(city_id) is not int or not 0 < city_id < 10**12
            or not isinstance(data, dict)
            or set(data) != {"city_id", "city_name", "island_id", "luxury", "free_citizens", "sites"}
            or type(data["city_id"]) is not int or data["city_id"] != city_id
            or not isinstance(data["city_name"], str) or not 0 < len(data["city_name"]) <= 100
            or type(data["island_id"]) is not int or not 0 < data["island_id"] < 10**12
            or not isinstance(data["luxury"], str) or data["luxury"] not in RESOURCES
            or not _count(data["free_citizens"], 2_000_000)
            or not isinstance(data["sites"], dict) or set(data["sites"]) != SITES):
        raise ValueError("Invalid production inventory")
    for kind, site in data["sites"].items():
        if not isinstance(site, dict) or type(site.get("available")) is not bool:
            raise ValueError("Invalid production site")
        if site["available"]:
            if (set(site) != {"available", "maximum", "extra", "current"}
                    or not _count(site["maximum"], 1_000_000)
                    or not _count(site["extra"], 1_000_000)
                    or not _count(site["current"], 2_000_000)
                    or kind in {"academy", "temple"} and site["extra"] != 0):
                raise ValueError("Invalid production site counts")
            if all(site[k] is not None for k in ("maximum", "extra", "current")) and (
                    site["current"] > site["maximum"] + site["extra"]):
                raise ValueError("Current assignment exceeds reported capacity")
        elif (set(site) != {"available", "reason"}
              or site["reason"] not in ("building_absent", "slider_unavailable")
              or kind in {"resource", "tradegood"} and site["reason"] == "building_absent"):
            raise ValueError("Invalid unavailable site")
    return data
