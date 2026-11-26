"""Daedalus one-time owned-city fill, using IkaBot's existing transport sender."""
import json
import math
import re
import time

from ikabot.config import actionRequest, materials_names_tec
from ikabot.helpers import pedirInfo
from ikabot.helpers.decorators import task
from ikabot.helpers.naval import getAvailableFreighters, getAvailableShips, getTotalFreighters, getTotalShips
from ikabot.helpers.planRoutes import sendGoods, waitForArrival
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import getCityById, requireOwnCity
from ikabot.helpers.varios import decodeUnicodeEscape

RESOURCES = ("wood", "wine", "marble", "crystal", "sulfur")
MAX_AMOUNT = 10**12


class FillPreviewError(ValueError):
    """Bounded reason code; never forward game HTML or exception details."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _free_space(v):
    # A legitimately overfilled warehouse can report negative remaining
    # space. Treat it as full, not an invalid or positive allocation.
    if type(v) is not int or not -MAX_AMOUNT <= v <= MAX_AMOUNT:
        raise ValueError("Invalid storage observation")
    return max(0, v)


def _amount(v):
    if type(v) is not int or not 0 <= v <= MAX_AMOUNT:
        raise ValueError("Invalid resource observation")
    return v


def _owned(session):
    pedirInfo.ids_cache = None
    ids, cities = pedirInfo.getIdsOfCities(session)
    if not 1 <= len(ids) <= 100:
        raise ValueError("Invalid owned city inventory")
    return {int(c): decodeUnicodeEscape(cities[c]["name"]) for c in ids}


def _city(session, cid):
    city = getCityById(session, str(cid))
    if str(city["id"]) != str(cid):
        raise ValueError("City identity changed")
    return city


def _advisor_data(session, target):
    """Read the fixed advisor view without a legacy POST on cookie-only workers."""
    if getattr(session, "_daedalus_cookies_only", False) is True:
        # Use the existing protected same-world GET transport; do not
        # reauthenticate, read stored cookies, or switch to legacy POST.
        html = session.get(f"view=militaryAdvisor&currentCityId={target}")
        marker = re.search(r"ajax\.Responder,\s*(?=\[)", html)
        if marker is None:
            raise ValueError("Advisor response unavailable")
        raw, _ = json.JSONDecoder(strict=False).raw_decode(html[marker.end():])
        return raw
    url = ("view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city"
           f"&currentCityId={target}&actionRequest={actionRequest}&ajax=1")
    return json.loads(session.post(url, retry_on_failure=False), strict=False)


def incoming_amount(session, target, name, resource):
    """Conservative matching: duplicate owned city names share reservations."""
    raw = _advisor_data(session, target)
    rows = raw[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
    if not isinstance(rows, list) or len(rows) > 250:
        raise ValueError("Incoming cargo unavailable")
    result = 0
    for row in rows:
        returning = row["event"]["isFleetReturning"]
        if type(returning) is not bool:
            raise ValueError("Movement direction unavailable")
        dest = row["origin" if returning else "target"]
        label = dest.get("name")
        if not isinstance(label, str) or not label:
            raise ValueError("Movement destination unavailable")
        if decodeUnicodeEscape(label) != name:
            continue
        player = dest.get("avatarName")
        if player is None:
            player = ""
        if not isinstance(player, str):
            raise ValueError("Movement destination unavailable")
        # A matching city name with no attested player is ambiguous. Never
        # silently omit its cargo; duplicate names are conservatively counted.
        if player and decodeUnicodeEscape(player).casefold() != session.username.casefold():
            continue
        cargo = row.get("resources")
        if not isinstance(cargo, list) or len(cargo) > 6:
            raise ValueError("Incoming cargo unavailable; inspect movements")
        for entry in cargo:
            key = entry["cssClass"].split()
            if len(key) < 2 or key[1] not in (*materials_names_tec, "gold"):
                raise ValueError("Unknown incoming resource")
            if key[1] == materials_names_tec[resource]:
                value = entry["amount"]
                if not isinstance(value, str):
                    raise ValueError("Invalid incoming quantity")
                number = re.sub(r"[, .\u00a0]", "", value)
                if not re.fullmatch(r"[0-9]{1,13}", number):
                    raise ValueError("Invalid incoming quantity")
                result += _amount(int(number))
    return _amount(result)


def _target(session, target, resource):
    names = _owned(session)
    if target not in names:
        raise ValueError("Destination no longer owned")
    incoming = incoming_amount(session, target, names[target], resource)
    city = _city(session, target)
    return names, city, _free_space(city["freeSpaceForResources"][resource]), incoming


def preview_fill(session, draft):
    target, resource, freighters = draft["destination_city"], draft["resource"], draft["useFreighters"]
    if type(target) is not int or resource not in RESOURCES or type(freighters) is not bool:
        raise ValueError("Invalid warehouse fill draft")
    i = RESOURCES.index(resource)
    try:
        names = _owned(session)
        if target not in names:
            raise ValueError("Destination no longer owned")
        city = _city(session, target)
        free = _free_space(city["freeSpaceForResources"][i])
        stock_at_target = _amount(city["availableResources"][i])
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_destination_unavailable") from exc
    try:
        incoming = incoming_amount(session, target, names[target], i)
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_incoming_unavailable") from exc
    budget = max(0, free-incoming)
    remaining = budget
    rows = []
    for cid in sorted(set(names)-{target}):
        try:
            stock = _amount(_city(session, cid)["availableResources"][i])
        except (Exception, SystemExit) as exc:
            raise FillPreviewError("fill_source_unavailable") from exc
        amount = min(stock, remaining)
        remaining -= amount
        rows.append({"city_id": cid, "city_name": names[cid], "stock": stock, "amount": amount})
    try:
        caps = pedirInfo.getShipCapacity(session)
        capacity = _amount(caps[int(freighters)])
        total = _amount((getTotalFreighters if freighters else getTotalShips)(session))
        available = _amount((getAvailableFreighters if freighters else getAvailableShips)(session))
        if available > total or (budget != remaining and (not capacity or not total)):
            raise ValueError("No usable fleet")
    except (Exception, SystemExit) as exc:
        raise FillPreviewError("fill_fleet_unavailable") from exc
    return {"destination_city": target, "destination_name": names[target],
            "stock": stock_at_target, "free_space": free, "incoming": incoming,
            "budget": budget, "amount": budget-remaining, "sources": rows,
            "capacity": capacity, "total_ships": total, "available_ships": available}


def prepare_fill(session, destination_city, resource, useFreighters=False, reviewed_sources=None):
    if type(destination_city) is not int or type(useFreighters) is not bool or resource not in RESOURCES:
        raise ValueError("Invalid warehouse fill")
    requireOwnCity(session, destination_city, "destination_city")
    if not isinstance(reviewed_sources, list) or not 0 <= len(reviewed_sources) <= 99:
        raise ValueError("Warehouse fill requires a reviewed allocation")
    seen = set()
    for row in reviewed_sources:
        if (not isinstance(row, dict) or set(row) != {"city_id", "amount"} or type(row["city_id"]) is not int
                or row["city_id"] == destination_city or row["city_id"] in seen or not _amount(row["amount"])):
            raise ValueError("Invalid warehouse fill source")
        requireOwnCity(session, row["city_id"], "source_city")
        seen.add(row["city_id"])
    return {"destination_city": destination_city, "resource": resource, "useFreighters": useFreighters,
            "reviewed_sources": reviewed_sources}


@task("fillCityWarehouse", prepare=prepare_fill, report_error=False)
def fill(session, destination_city, resource, useFreighters=False, reviewed_sources=None):
    """Send at most the reviewed quantities, never refill automatically."""
    config = prepare_fill(session, destination_city, resource, useFreighters, reviewed_sources)
    index = RESOURCES.index(resource)
    setInfoSignal(session, f"Fill warehouse: {resource} (one time)")
    sent = 0
    for row in config["reviewed_sources"]:
        source, remaining = row["city_id"], row["amount"]
        while remaining:
            names, target, free, incoming = _target(session, destination_city, index)
            if source not in names:
                raise ValueError("Source no longer owned")
            if free <= incoming:
                session.setStatus(f"Storage budget exhausted; submitted {sent:,}")
                return
            total = (getTotalFreighters if useFreighters else getTotalShips)(session)
            if type(total) is not int or total <= 0:
                raise ValueError("Selected fleet unavailable")
            ships = waitForArrival(session, useFreighters)
            capacity = pedirInfo.getShipCapacity(session)[int(useFreighters)]
            if type(capacity) is not int or capacity <= 0 or type(ships) is not int or ships <= 0:
                raise ValueError("Fleet unavailable")
            names, target, free, incoming = _target(session, destination_city, index)
            if source not in names:
                raise ValueError("Source no longer owned")
            stock = _amount(_city(session, source)["availableResources"][index])
            qty = min(remaining, stock, max(0, free-incoming), ships*capacity)
            if qty <= 0:
                break
            cargo = [0]*5
            cargo[index] = qty
            before_incoming = incoming

            def guard():
                nonlocal before_incoming
                current_names, current, current_free, current_incoming = _target(session, destination_city, index)
                if (source not in current_names or str(current["islandId"]) != str(target["islandId"])
                        or qty > max(0, current_free-current_incoming)):
                    raise ValueError("Storage or ownership changed; review before retrying")
                before_incoming = current_incoming

            sendGoods(session, str(source), str(destination_city), target["islandId"],
                      math.ceil(qty/capacity), cargo, useFreighters, before_send=guard)
            sent += qty
            remaining -= qty
            session.setStatus(f"Submitted {sent:,} {resource}; checking incoming cargo")
            # Don't send another load against a potentially stale advisor. The
            # accepted load must be visible as incoming before we proceed.
            for attempt in range(3):
                _, _, _, observed = _target(session, destination_city, index)
                if observed >= before_incoming + qty:
                    break
                if attempt < 2:
                    time.sleep(2)
            else:
                session.setStatus(f"Submitted {sent:,}; incoming cargo unconfirmed. Review before retrying.")
                return
    session.setStatus(f"Warehouse fill finished; submitted {sent:,} {resource}")
