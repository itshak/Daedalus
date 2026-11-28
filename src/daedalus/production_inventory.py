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


def validate_production_draft(draft):
    fields = {"resource", "mode", "amount", "overcharge", "available_only", "allow_fallback"}
    if not isinstance(draft, dict) or set(draft) not in (fields, fields | {"fill_both"}):
        raise ValueError("Invalid production draft")
    mode, amount = draft["mode"], draft["amount"]
    if (draft["resource"] not in ("wood", "wine", "marble", "crystal", "sulfur")
            or mode not in ("maximum", "percentage", "exact")
            or any(type(draft[k]) is not bool for k in ("overcharge", "available_only", "allow_fallback"))
            or (mode == "maximum" and amount is not None)
            or (mode == "percentage" and (type(amount) is not int or not 0 <= amount <= 100))
            or (mode == "exact" and (type(amount) is not int or not 0 <= amount <= 2_000_000))
            or (mode == "percentage" and draft["overcharge"] and amount != 100)
            or (draft["available_only"] and draft["allow_fallback"])
            or ("fill_both" in draft and (draft["fill_both"] is not True
                or mode != "maximum" or draft["allow_fallback"]))):
        raise ValueError("Invalid production target")
    return dict(draft)


def validate_priority_draft(city_id, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise ValueError("Select 1 to 16 production cities per account")
    clean = []
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"city_id", "draft"}
                or type(row["city_id"]) is not int or not 0 < row["city_id"] < 10**12
                or row["city_id"] in seen):
            raise ValueError("Invalid production city selection")
        seen.add(row["city_id"])
        clean.append({"city_id": row["city_id"], "draft": validate_production_draft(row["draft"])})
    if clean[0]["city_id"] != city_id:
        raise ValueError("Production review city mismatch")
    return clean


def validate_priority_plan(city_id, draft, plan):
    """Validate the engine's bounded receipt and reviewed displacement limits."""
    fields = {"city_id", "island_id", "resource", "luxury", "target_kind", "donor_kind",
              "target_before", "donor_before", "desired", "target_after", "donor_release",
              "donor_after", "shortfall", "fallback", "free_citizens", "target_capacity",
              "donor_capacity", "draft"}
    if not isinstance(plan, dict) or set(plan) != fields or plan["draft"] != draft:
        raise ValueError("Invalid production plan")
    if (type(plan["city_id"]) is not int or plan["city_id"] != city_id
            or type(plan["island_id"]) is not int or not 0 < plan["island_id"] < 10**12
            or plan["resource"] != draft["resource"] or not isinstance(plan["luxury"], str) or plan["luxury"] not in RESOURCES
            or (plan["resource"] != "wood" and plan["resource"] != plan["luxury"])
            or plan["target_kind"] != ("resource" if plan["resource"] == "wood" else "tradegood")
            or plan["donor_kind"] != ("tradegood" if plan["target_kind"] == "resource" else "resource")
            or type(plan["fallback"]) is not bool):
        raise ValueError("Invalid production plan identity")
    for key in ("target_capacity", "donor_capacity"):
        if not isinstance(plan[key], list) or len(plan[key]) != 2 or any(
                (n is not None or key != "target_capacity") and (type(n) is not int or not 0 <= n <= 1_000_000) for n in plan[key]):
            raise ValueError("Invalid production capacity")
    for key in ("target_before", "donor_before", "donor_release"):
        if type(plan[key]) is not int or not 0 <= plan[key] <= 2_000_000:
            raise ValueError("Invalid production quantity")
    if ((None not in plan["target_capacity"] and plan["target_before"] > sum(plan["target_capacity"]))
            or plan["donor_before"] > sum(plan["donor_capacity"])
            or plan["donor_release"] > plan["donor_before"]
            or (draft["available_only"] and plan["donor_release"])
            or not _count(plan["free_citizens"], 2_000_000)):
        raise ValueError("Invalid reviewed displacement")
    normal, extra = plan["target_capacity"]
    if normal is None or extra is None:
        if (draft["mode"] != "maximum" or not draft["allow_fallback"] or draft["available_only"]
                or draft.get("fill_both") or not plan["fallback"] or not plan["donor_before"]
                or plan["donor_release"] != plan["donor_before"]
                or any(plan[k] is not None for k in ("desired","target_after","donor_after","shortfall"))):
            raise ValueError("Invalid unknown-capacity fallback")
        return plan
    if type(plan["desired"]) is not int or not 0 <= plan["desired"] <= 2_000_000:
        raise ValueError("Invalid production quantity")
    capacity = normal + (extra if draft["overcharge"] else 0)
    desired = (capacity if draft["mode"] == "maximum" else
               normal * draft["amount"] // 100 + (extra if draft["overcharge"] else 0)
               if draft["mode"] == "percentage" else draft["amount"])
    if desired != plan["desired"] or desired > capacity:
        raise ValueError("Invalid production target")
    free = plan["free_citizens"]
    needed = max(0, desired - plan["target_before"])
    if plan["fallback"]:
        if (free is not None or not needed or not draft["allow_fallback"] or draft["available_only"]
                or not plan["donor_before"] or plan["donor_release"] != plan["donor_before"]
                or any(plan[k] is not None for k in ("target_after", "donor_after", "shortfall"))):
            raise ValueError("Invalid fallback displacement")
    else:
        if needed and free is None:
            raise ValueError("Unknown population")
        expected_release = (0 if draft["available_only"] else
                            min(plan["donor_before"], max(0, needed - (free or 0))))
        expected_target = min(desired, plan["target_before"] + (free or 0) + expected_release)
        donor_after = plan["donor_before"] - expected_release
        if draft.get("fill_both"):
            if free is None:
                raise ValueError("Both-resource planning requires known population")
            secondary_cap = plan["donor_capacity"][0] + (plan["donor_capacity"][1] if draft["overcharge"] else 0)
            donor_after = max(donor_after, min(secondary_cap, donor_after + free + plan["target_before"] + expected_release - expected_target))
        expected = {"donor_release": expected_release, "target_after": expected_target,
                    "donor_after": donor_after,
                    "shortfall": desired - expected_target}
        if any(type(plan[k]) is not int or plan[k] != v for k, v in expected.items()):
            raise ValueError("Invalid production feasibility")
    return plan


def validate_production_progress(account_id, data):
    import re

    if (not isinstance(data, dict) or data.get("account_id") != account_id
            or not isinstance(data.get("runs"), list) or len(data["runs"]) > 20):
        raise ValueError("Invalid production history")
    ids = set()
    for run in data["runs"]:
        if (not isinstance(run, dict) or not isinstance(run.get("run_id"), str)
                or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", run["run_id"])
                or run["run_id"] in ids or run.get("status") not in
                {"prepared", "complete", "partial", "rejected", "reconciled"}
                or not isinstance(run.get("cities"), list) or not 1 <= len(run["cities"]) <= 16):
            raise ValueError("Invalid production run")
        ids.add(run["run_id"])
        cities = set()
        for row in run["cities"]:
            if (not isinstance(row, dict) or type(row.get("city_id")) is not int
                    or not 0 < row["city_id"] < 10**12 or row["city_id"] in cities
                    or row.get("resource") not in {"wood", *RESOURCES}
                    or row.get("status") not in {"not_started", "running", "complete", "stale"}
                    or not isinstance(row.get("stages"), list) or len(row["stages"]) > 3
                    or any(type(row.get(k)) is not int or not 0 <= row[k] <= 2_000_000
                           for k in ("target_before", "donor_before", "donor_release"))
                    or not _count(row.get("desired"), 2_000_000)):
                raise ValueError("Invalid production city receipt")
            cities.add(row["city_id"])
            stages = set()
            for stage in row["stages"]:
                if (not isinstance(stage, dict) or stage.get("stage") not in {"release", "target", "restore", "secondary"}
                        or stage["stage"] in stages or stage.get("kind") not in {"resource", "tradegood"}
                        or stage.get("status") not in {"pending", "confirmed"}
                        or type(stage.get("value")) is not int or not 0 <= stage["value"] <= 2_000_000):
                    raise ValueError("Invalid production stage")
                stages.add(stage["stage"])
            result = row.get("result")
            if result is not None and (not isinstance(result, dict) or result.get("city_id") != row["city_id"]
                    or any(type(result.get(k)) is not int or not 0 <= result[k] <= 2_000_000
                           for k in ("target", "donor", "shortfall"))):
                raise ValueError("Invalid production result")
    return data


def validate_reconciliation(account_id, run_id, data, *, resolved=False):
    import re

    if (not isinstance(data, dict) or data.get("account_id") != account_id or data.get("run_id") != run_id
            or data.get("status") != ("reconciled" if resolved else "review")
            or not isinstance(data.get("observations"), list) or not 1 <= len(data["observations"]) <= 16):
        raise ValueError("Invalid production reconciliation")
    if not resolved and (not isinstance(data.get("preview_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", data["preview_id"])
            or type(data.get("expires_in")) is not int or not 1 <= data["expires_in"] <= 120):
        raise ValueError("Invalid reconciliation ticket")
    seen = set()
    for row in data["observations"]:
        if (not isinstance(row, dict) or set(row) != {"city_id", "city_name", "island_id", "luxury", "resource", "tradegood"}
                or any(type(row[k]) is not int or not 0 < row[k] < 10**12 for k in ("city_id", "island_id"))
                or not isinstance(row["city_name"], str) or not 0 < len(row["city_name"]) <= 100
                or row["luxury"] not in RESOURCES or row["city_id"] in seen
                or any(type(row[k]) is not int or not 0 <= row[k] <= 2_000_000 for k in ("resource", "tradegood"))):
            raise ValueError("Invalid reconciled allocation")
        seen.add(row["city_id"])
    return data
