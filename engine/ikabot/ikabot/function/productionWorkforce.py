"""Reviewed production policy, built on the existing IkaBot worker helpers.

No game writes occur during inventory or planning. Counts that the game does
not expose remain unknown; in particular a slider capacity is not a current
assignment and is not evidence of an independently configurable extra pool.
"""

from ikabot.config import island_url
from ikabot.function.modifyProduction import _read_worker_slider, _submit_worker_assignment
from ikabot.helpers.varios import wait
from ikabot.helpers import pedirInfo
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.taskConfig import getCityById, requireOwnCity

RESOURCE_NAMES = ("wood", "wine", "marble", "crystal", "sulfur")
SITES = ("resource", "tradegood")
MAX_COUNT = 2_000_000


def _count(value, *, maximum=MAX_COUNT):
    return value if type(value) is int and 0 <= value <= maximum else None


def _site(slider, kind):
    normal = _count(slider.get("max_value"), maximum=1_000_000)
    extra = _count(slider.get("overcharge"), maximum=1_000_000) if kind in SITES else 0
    current = _count(slider.get("value"))
    if normal is not None and extra is not None and current is not None and current > normal + extra:
        # A changed capacity can leave existing assignments above the new cap.
        # Do not offer a potentially invalid reallocation.
        current = None
    return {"maximum": normal, "extra": extra, "current": current}


def read_city_production(session, city_id):
    """Read owned city, verified island tradegood and each available slider."""
    if type(city_id) is not int or not 0 < city_id < 10**12:
        raise ValueError("Invalid production city")
    pedirInfo.ids_cache = None
    own = requireOwnCity(session, city_id, "Production city")
    city = getCityById(session, own, allow_unknown_citizens=True)
    if str(city["id"]) != own:
        raise ValueError("Production city mismatch")
    island_id = int(city["islandId"])
    if not 0 < island_id < 10**12:
        raise ValueError("Invalid production island")
    island = getIsland(session.get(island_url + str(island_id)))
    if str(island.get("id")) != str(island_id):
        raise ValueError("Production island mismatch")
    luxury_code = str(island.get("tipo"))
    if luxury_code not in ("1", "2", "3", "4"):
        raise ValueError("Unknown luxury resource")
    sites = {}
    for kind in (*SITES, "academy", "temple"):
        if kind not in SITES and not any(
                row.get("building") == kind for row in city.get("position", [])):
            sites[kind] = {"available": False, "reason": "building_absent"}
            continue
        try:
            slider, _ = _read_worker_slider(session, city, kind)
            sites[kind] = {"available": True, **_site(slider, kind)}
        except (KeyError, IndexError, TypeError, ValueError):
            sites[kind] = {"available": False, "reason": "slider_unavailable"}
    return {"city_id": city_id, "city_name": str(city.get("cityName") or city.get("name") or "")[:100],
            "island_id": island_id, "luxury": RESOURCE_NAMES[int(luxury_code)],
            "free_citizens": _count(city.get("freeCitizens")), "sites": sites}


def validate_draft(draft):
    fields = {"resource", "mode", "amount", "overcharge", "available_only", "allow_fallback"}
    if not isinstance(draft, dict) or set(draft) not in (fields, fields | {"fill_both"}):
        raise ValueError("Invalid production draft")
    resource, mode, amount = draft["resource"], draft["mode"], draft["amount"]
    if (resource not in RESOURCE_NAMES or mode not in ("maximum", "percentage", "exact")
            or any(type(draft[k]) is not bool for k in ("overcharge", "available_only", "allow_fallback"))
            or (mode == "maximum" and amount is not None)
            or (mode == "percentage" and (type(amount) is not int or not 0 <= amount <= 100))
            or (mode == "exact" and _count(amount) is None)
            or (mode == "percentage" and draft["overcharge"] and amount != 100)
            or (draft["available_only"] and draft["allow_fallback"])
            or ("fill_both" in draft and (draft["fill_both"] is not True
                or mode != "maximum" or draft["allow_fallback"]))):
        raise ValueError("Invalid production target or population policy")
    return dict(draft)


def plan_city_production(observed, draft):
    """Compute a reviewed single-resource plan; never guess population.

    A fallback is an explicitly authorized temporary release, not a predicted
    result. The actual target/donor restoration must be calculated from fresh
    authoritative state after that release.
    """
    draft = validate_draft(draft)
    resource = draft["resource"]
    kind = "resource" if resource == "wood" else "tradegood"
    if kind == "tradegood" and observed.get("luxury") != resource:
        raise ValueError("City does not produce the selected resource")
    donor_kind = "tradegood" if kind == "resource" else "resource"
    target, donor = (observed.get("sites", {}).get(k, {}) for k in (kind, donor_kind))
    if any(site.get("available") is not True or any(_count(site.get(k)) is None
            for k in ("maximum", "extra", "current")) for site in (target, donor)):
        raise ValueError("Both current allocations and capacities must be known")
    normal, extra, before, donor_before = (target["maximum"], target["extra"],
                                          target["current"], donor["current"])
    cap = normal + (extra if draft["overcharge"] else 0)
    mode, amount = draft["mode"], draft["amount"]
    wanted = (cap if mode == "maximum" else
              normal * amount // 100 + (extra if draft["overcharge"] else 0)
              if mode == "percentage" else amount)
    if wanted > cap:
        raise ValueError("Exact target exceeds reviewed capacity")
    free = _count(observed.get("free_citizens"))
    needed = max(0, wanted - before)
    fallback = False
    if needed == 0:
        release, achievable = 0, wanted
    elif free is None:
        if draft["available_only"] or not draft["allow_fallback"] or not donor_before:
            raise ValueError("Available citizens are unknown")
        release, achievable, fallback = donor_before, None, True
    else:
        deficit = max(0, needed - free)
        release = 0 if draft["available_only"] else min(donor_before, deficit)
        achievable = min(wanted, before + free + release)
    donor_after = None if fallback else donor_before - release
    if draft.get("fill_both"):
        if free is None:
            raise ValueError("Both-resource planning requires known population")
        secondary_cap = donor["maximum"] + (donor["extra"] if draft["overcharge"] else 0)
        donor_after = max(donor_after, min(secondary_cap, donor_after + free + before + release - achievable))
    return {"city_id": observed["city_id"], "island_id": observed["island_id"],
            "resource": resource, "luxury": observed["luxury"], "target_kind": kind, "donor_kind": donor_kind,
            "target_before": before, "donor_before": donor_before, "desired": wanted,
            "target_after": achievable, "donor_release": release,
            "donor_after": donor_after,
            "shortfall": None if fallback else wanted - achievable, "fallback": fallback,
            "free_citizens": free, "target_capacity": [normal, extra],
            "donor_capacity": [donor["maximum"], donor["extra"]], "draft": draft}


def feasible_after_release(plan, fresh):
    """Bound target and donor restoration by the original reviewed intent.

    The execution layer must additionally verify identity and journal stage
    before invoking either write; this helper cannot authorize a mutation.
    """
    if (fresh.get("city_id") != plan["city_id"] or fresh.get("island_id") != plan["island_id"]
            or fresh.get("luxury") != plan["luxury"]):
        raise ValueError("Production city changed")
    sites = fresh.get("sites", {})
    target, donor = (sites.get(k, {}) for k in (plan["target_kind"], plan["donor_kind"]))
    free = _count(fresh.get("free_citizens"))
    if any(s.get("available") is not True or any(
            _count(s.get(k)) is None for k in ("maximum", "extra", "current")) for s in (target, donor)):
        raise ValueError("Cannot verify post-release allocations")
    if target["current"] != plan["target_before"] or donor["current"] != plan["donor_before"] - plan["donor_release"]:
        raise ValueError("Unexpected assignment after release")
    cap = target["maximum"] + (target["extra"] if plan["draft"]["overcharge"] else 0)
    desired = min(plan["desired"], cap)
    if free is None and desired > target["current"]:
        raise ValueError("Cannot verify available citizens after release")
    achievable = min(desired, target["current"] + (free or 0))
    if plan["target_after"] is not None:
        achievable = min(achievable, plan["target_after"])
    # A new capacity loss must not implicitly reduce an existing assignment.
    if achievable < target["current"] and plan["desired"] >= target["current"]:
        raise ValueError("Target capacity changed after review")
    return achievable


def donor_restore_target(plan, fresh, verified_target):
    if (fresh.get("city_id") != plan["city_id"] or fresh.get("island_id") != plan["island_id"]
            or fresh.get("luxury") != plan["luxury"]):
        raise ValueError("Production city changed")
    sites = fresh.get("sites", {})
    target, donor = (sites.get(k, {}) for k in (plan["target_kind"], plan["donor_kind"]))
    free = _count(fresh.get("free_citizens"))
    if (free is None or donor.get("available") is not True or target.get("available") is not True
            or target.get("current") != verified_target or
            donor.get("current") != plan["donor_before"] - plan["donor_release"] or
            any(_count(donor.get(k)) is None for k in ("maximum", "extra", "current"))):
        raise ValueError("Cannot verify donor restoration")
    return max(donor["current"], min(plan["donor_before"], donor["maximum"] + donor["extra"],
                                     donor["current"] + free))


class ProductionStale(ValueError):
    """A reviewed city changed before any mutation."""


class ProductionNeedsReview(RuntimeError):
    """An assignment may have changed; do not replay or make another write."""


def _same_counts(fresh, plan, target, donor):
    if (fresh.get("city_id"), fresh.get("island_id"), fresh.get("luxury")) != (
            plan["city_id"], plan["island_id"], plan["luxury"]):
        raise ProductionNeedsReview("Production identity changed")
    for kind, expected in ((plan["target_kind"], target), (plan["donor_kind"], donor)):
        site = fresh.get("sites", {}).get(kind, {})
        if site.get("available") is not True or type(site.get("current")) is not int or site["current"] != expected:
            raise ProductionNeedsReview("Production readback differs from reviewed assignment")


def execute_city_production(session, plan, journal):
    """Execute an approved plan with write-ahead receipts and exact readback.

    A transport error, interruption or unexpected readback leaves the
    pending stage fenced. The upstream helper does not expose a definitive
    rejection contract for workerPlan; never compensate an ambiguous reply.
    """
    try:
        fresh = read_city_production(session, plan["city_id"])
        if plan_city_production(fresh, plan["draft"]) != plan:
            raise ValueError("Changed observation")
    except ValueError as exc:
        raise ProductionStale("Production review is stale") from exc
    journal.begin_city(plan)
    target = plan["target_before"]
    donor = plan["donor_before"]

    def submit(stage, kind, value, expected_target, expected_donor):
        journal.reserve(plan, stage, kind, value)
        _submit_worker_assignment(session, str(plan["city_id"]), str(plan["island_id"]),
                                  kind, None, value, reviewed=True)
        # Original interactive workerPlan spacing on the same island.
        wait(2, 2)
        after = read_city_production(session, plan["city_id"])
        _same_counts(after, plan, expected_target, expected_donor)
        journal.confirm(plan, stage, after)
        return after

    if plan["donor_release"]:
        donor -= plan["donor_release"]
        fresh = submit("release", plan["donor_kind"], donor, target, donor)
    wanted = feasible_after_release(plan, fresh)
    if wanted != target:
        fresh = submit("target", plan["target_kind"], wanted, wanted, donor)
        target = wanted
    if plan["draft"].get("fill_both"):
        _same_counts(fresh, plan, target, donor)
        site = fresh["sites"][plan["donor_kind"]]
        free = _count(fresh.get("free_citizens"))
        if free is None or any(_count(site.get(k)) is None for k in ("maximum", "extra", "current")):
            raise ProductionNeedsReview("Secondary allocation is unknown")
        cap = site["maximum"] + (site["extra"] if plan["draft"]["overcharge"] else 0)
        secondary = max(donor, min(plan["donor_after"], cap, donor + free))
        if secondary != donor:
            fresh = submit("secondary", plan["donor_kind"], secondary, target, secondary)
            donor = secondary
    elif plan["donor_release"]:
        restored = donor_restore_target(plan, fresh, target)
        if restored != donor:
            fresh = submit("restore", plan["donor_kind"], restored, target, restored)
            donor = restored
    result = {"city_id": plan["city_id"], "target": target, "donor": donor,
              "shortfall": plan["desired"] - target}
    journal.complete_city(plan, result)
    return result


def preview_priority_production(session, city_id, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise ValueError("Choose 1 to 16 production cities")
    plans, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"city_id", "draft"}:
            raise ValueError("Invalid production city")
        cid = row["city_id"]
        if type(cid) is not int or cid in seen or (not plans and cid != city_id):
            raise ValueError("Invalid production city selection")
        seen.add(cid)
        plans.append(plan_city_production(read_city_production(session, cid), row["draft"]))
    return plans


def execute_priority_production(session, plans, run_id):
    from ikabot.helpers.productionJournal import ProductionJournal

    journal = ProductionJournal(session, run_id, plans)
    for plan in plans:
        session.setStatus("Applying reviewed production allocation")
        try:
            execute_city_production(session, plan, journal)
        except ProductionStale:
            journal.skip_stale(plan)
        # An error after begin_city MUST stop the run, leaving a durable fence.
    journal.finish()
    session.setStatus("Production review processed; see per-city receipts")
