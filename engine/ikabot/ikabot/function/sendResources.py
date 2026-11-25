#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.getJson import getCity, getIsland
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.naval import getAvailableShips, getTotalShips, getAvailableFreighters, getTotalFreighters
from ikabot.helpers import pedirInfo
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.taskConfig import asBool, asId, asInt, getCityById, requireOwnCity
from ikabot.helpers.varios import addThousandSeparator, decodeUnicodeEscape


RESOURCE_KEYS = ("wood", "wine", "marble", "crystal", "sulfur")


def route_from_saved(route):
    """A route as {"from", "to", "resources"[, "island"]}; an older menu saved
    (origin city, destination city, island id, wood, wine, marble, crystal, sulfur)"""
    if isinstance(route, (list, tuple)) and len(route) == 3 + len(RESOURCE_KEYS):
        origin, destination, island_id = route[0], route[1], route[2]
        return {
            "from": origin["id"] if isinstance(origin, dict) else origin,
            "to": destination["id"] if isinstance(destination, dict) else destination,
            "island": island_id,
            "resources": list(route[3:]),
        }
    return route


def get_island(session, value, name):
    """The island with this id or "X:Y" coordinates, as returned by getIsland"""
    text = str(value).strip()
    if re.fullmatch(r"\d+\s*:\s*\d+", text):
        x, y = text.replace(" ", "").split(":")
        return getIsland(session.get("view=island&xcoord={}&ycoord={}".format(x, y)))
    return getIsland(session.get(island_url + asId(value, name)))


def _destination_id(value):
    if type(value) not in (str, int) or not re.fullmatch(r"[1-9][0-9]{0,11}", str(value)):
        raise ValueError("Invalid destination identity")
    return int(value)


def _eligible_destinations(session, island):
    island_id = _destination_id(island["id"])
    rows = []
    for city in island["cities"]:
        if (city.get("type") != "city" or city.get("state") != ""
                or city.get("Name") == session.username):
            continue
        name, owner = city.get("name"), city.get("Name")
        if not isinstance(name, str) or not isinstance(owner, str) or not name or not owner:
            raise ValueError("Invalid destination name")
        rows.append({"id": _destination_id(city["id"]),
                     "recipient": _destination_id(city["Id"]),
                     "island": island_id,
                     "name": decodeUnicodeEscape(name)[:120],
                     "owner": decodeUnicodeEscape(owner)[:120]})
    if len(rows) > 100 or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Invalid island inventory")
    return rows


def native_island_destinations(session, x, y):
    if any(type(v) is not int or not 1 <= v <= 100 for v in (x, y)):
        raise ValueError("Choose island coordinates between 1 and 100")
    # Match the upstream interactive foreign-city lookup exactly.
    import json
    html = session.get(f"view=worldmap_iso&islandX={x}&islandY={y}&oldBackgroundView=island&islandWorldviewScale=1")
    try:
        data = json.loads(re.search(r"jsonData = '(.*?)';", html).group(1), strict=False)
        island_id = _destination_id(data["data"][str(x)][str(y)][0])
    except (ValueError, AttributeError, KeyError, IndexError, TypeError):
        raise ValueError("No verified island at these coordinates") from None
    island = get_island(session, island_id, "Destination island")
    if (_destination_id(island["id"]) != island_id or
            (int(island["x"]), int(island["y"])) != (x, y)):
        raise ValueError("Island coordinates changed")
    return {"x": x, "y": y, "cities": _eligible_destinations(session, island)}


def _verify_recipient(session, route, island=None):
    if "recipient" not in route:
        return
    if island is None:
        island = get_island(session, route["island"], "Destination island")
    destination, owner, island_id = (_destination_id(route[k]) for k in ("to", "recipient", "island"))
    if not any(row["id"] == destination and row["recipient"] == owner and row["island"] == island_id
               for row in _eligible_destinations(session, island)):
        raise ValueError("Reviewed external destination changed; stop and review again")


def resource_amounts(value, name):
    if isinstance(value, dict):
        unknown = [key for key in value if key not in RESOURCE_KEYS]
        if unknown:
            raise ValueError("{} has unknown resources {}, use {}".format(name, unknown, ", ".join(RESOURCE_KEYS)))
        value = [value.get(key, 0) for key in RESOURCE_KEYS]
    if not isinstance(value, (list, tuple)) or len(value) != len(RESOURCE_KEYS):
        raise ValueError(
            "{} must be 5 amounts (wood, wine, marble, crystal, sulfur) or an object like {{\"wood\": 5000}}, got {!r}".format(name, value)
        )
    amounts = [asInt(amount, name, minimum=0) for amount in value]
    if sum(amounts) == 0:
        raise ValueError("{} sends nothing".format(name))
    return amounts


def prepare_sendResources(session, routes, useFreighters=False, transfer_id=None):
    """Checks the config of a sendResources task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    routes : list
        [{"from": city id, "to": city id, "resources": [wood, wine, marble, crystal, sulfur]}, ...];
        "island" (id or "X:Y") is needed when "to" is another player's city
    useFreighters : bool

    Returns
    -------
    config : dict
    """
    if not isinstance(routes, (list, tuple)) or not routes:
        raise ValueError('routes must be a list of {{"from": ..., "to": ..., "resources": [...]}}, got {!r}'.format(routes))
    if any(isinstance(r, dict) and "recipient" in r for r in routes):
        pedirInfo.ids_cache = None
    own_ids, _ = getIdsOfCities(session)
    checked = []
    asked = {}  # origin id -> amounts asked by all its routes
    for i, route in enumerate(routes):
        name = "routes[{}]".format(i)
        route = route_from_saved(route)
        if not isinstance(route, dict):
            raise ValueError('{} must be {{"from": ..., "to": ..., "resources": [...]}}, got {!r}'.format(name, route))
        origin = requireOwnCity(session, route.get("from"), name + ".from")
        destination = asId(route.get("to"), name + ".to")
        if destination == origin:
            raise ValueError("{} sends from city {} to itself".format(name, origin))
        amounts = resource_amounts(route.get("resources"), name + ".resources")
        checked_route = {"from": origin, "to": destination, "resources": amounts}

        if destination not in own_ids:
            if route.get("island") is None:
                raise ValueError(
                    '{}.island is needed when "to" is not your city: the id of its island or its "X:Y" coordinates'.format(name)
                )
            island = get_island(session, route["island"], name + ".island")
            if not any(str(city.get("id")) == destination for city in island["cities"] if city.get("type") == "city"):
                raise ValueError(
                    "{}.to {} is not on island {}:{}".format(name, destination, island["x"], island["y"])
                )
            checked_route["island"] = str(island["id"])
            if "recipient" in route:
                _verify_recipient(session, route, island)
                checked_route["recipient"] = str(_destination_id(route["recipient"]))
        elif "recipient" in route:
            raise ValueError("Reviewed external destination is now an owned city")
        checked.append(checked_route)
        asked[origin] = [a + b for a, b in zip(asked.get(origin, [0] * len(RESOURCE_KEYS)), amounts)]

    if transfer_id is not None:
        # A Daedalus-managed transfer must already have a protected, approved
        # checkpoint bound to this exact world/player, route and quantity.
        # Earlier confirmed cargo is subtracted later by the journal.
        from ikabot.helpers.fixedTransferJournal import FixedTransferJournal
        if any(str(route["to"]) not in own_ids for route in checked):
            raise ValueError("Unattended fixed transfers require owned recipients")
        FixedTransferJournal(
            session, transfer_id, checked, bool(useFreighters),
        )
    # Historical unmanaged tasks keep the original available-stock preflight.
    for origin, amounts in ({} if transfer_id is not None else asked).items():
        city = getCityById(session, origin)
        for key, amount, available in zip(RESOURCE_KEYS, amounts, city["availableResources"]):
            if amount > int(available):
                raise ValueError(
                    "{} has {} {}, the routes send {}".format(
                        city["name"], addThousandSeparator(int(available)), key, addThousandSeparator(amount)
                    )
                )

    result = {"routes": checked, "useFreighters": asBool(useFreighters, "useFreighters")}
    if transfer_id is not None:
        result["transfer_id"] = transfer_id
    return result


def preview_native_shipments(session, routes, useFreighters):
    """A read-only quote of current inventory, fleet and minimum load counts."""
    pedirInfo.ids_cache = None
    if type(useFreighters) is not bool or not isinstance(routes, list) or not 1 <= len(routes) <= 20:
        raise ValueError("Invalid shipment plan")
    own_ids, own_cities = getIdsOfCities(session)
    owned = set(map(str, own_ids))
    # The native surface must never accept an unverified foreign recipient.
    for route in routes:
        if str(route["to"]) not in owned and "recipient" not in route:
            raise ValueError("Discover the external recipient first")
    # Reuse the upstream validation of ownership, routes and aggregate stock.
    checked = prepare_sendResources(session, routes, useFreighters)["routes"]
    ship_capacity, freighter_capacity = getShipCapacity(session)
    capacity = freighter_capacity if useFreighters else ship_capacity
    free = getAvailableFreighters(session) if useFreighters else getAvailableShips(session)
    total = getTotalFreighters(session) if useFreighters else getTotalShips(session)
    if (type(capacity) is not int or not 0 <= capacity <= 10**8
            or type(free) is not int or type(total) is not int or not 0 <= free <= total <= 10**8):
        raise ValueError("Invalid fleet observation")
    rows = []
    for route, item in zip(routes, checked):
        cargo = sum(item["resources"])
        origin, destination = item["from"], item["to"]
        source = getCityById(session, origin)
        if str(source["id"]) != origin:
            raise ValueError("Origin identity changed")
        stock = source["availableResources"]
        if len(stock) != 5 or any(type(v) is not int or not 0 <= v <= 10**15 for v in stock):
            raise ValueError("Invalid source stock")
        if destination in owned:
            target = getCityById(session, destination)
            if str(target["id"]) != destination:
                raise ValueError("Destination identity changed")
            space = target["freeSpaceForResources"]
            if len(space) != 5 or any(type(v) is not int or not 0 <= v <= 10**15 for v in space):
                raise ValueError("Invalid destination capacity")
            name = decodeUnicodeEscape(own_cities[destination]["name"])[:120]
        else:
            island = get_island(session, item["island"], "Destination island")
            _verify_recipient(session, item, island)
            recipient = next(r for r in _eligible_destinations(session, island)
                             if str(r["id"]) == destination)
            name = f"{recipient['name']} — {recipient['owner']}"[:250]
            space = None
        first = min(cargo, free * capacity)
        if space is not None:
            first = min(first, sum(min(a, b) for a, b in zip(item["resources"], space)))
        rows.append({"from": route["from"], "to": route["to"],
                     "origin_name": decodeUnicodeEscape(own_cities[origin]["name"])[:120],
                     "destination_name": name, "resources": item["resources"],
                     "stock": stock, "destination_space": space,
                     "first_load_limit": first,
                     "minimum_loads": (cargo + total * capacity - 1) // (total * capacity)
                     if total and capacity else None})
    return {"routes": rows, "useFreighters": useFreighters, "capacity": capacity,
            "available_ships": free, "total_ships": total,
            "ready": bool(total and capacity)}


@task("sendResources", prepare=prepare_sendResources)
def do_it(session, routes, useFreighters=False, transfer_id=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    routes : list
        [{"from": city id, "to": city id, "resources": [...]}, ...], with "island" when "to"
        is another player's city
    useFreighters : bool
    """
    info = "\nSend resources\n"
    setInfoSignal(session, info)
    own_ids, own_cities = getIdsOfCities(session)
    shipments = []
    for route in map(route_from_saved, routes):
        origin = str(route["from"])
        destination = str(route["to"])
        if destination in own_ids:
            island_id = getCityById(session, destination)["islandId"]
            destination_name = decodeUnicodeEscape(own_cities[destination]["name"])
        else:
            island = getIsland(session.get(island_url + str(route["island"])))
            island_id = island["id"]
            _verify_recipient(session, route, island)
            destination_name = next(
                (city["name"] for city in island["cities"] if str(city.get("id")) == destination), destination
            )
        shipments.append(
            (
                {"id": origin, "name": decodeUnicodeEscape(own_cities[origin]["name"])},
                {"id": destination, "name": destination_name},
                island_id,
                *route["resources"],
            )
        )
    checkpoint = None
    if transfer_id is not None:
        from ikabot.helpers.fixedTransferJournal import FixedTransferJournal
        checkpoint = FixedTransferJournal(
            session, transfer_id, list(routes), useFreighters,
        )
    if any("recipient" in route for route in routes):
        executeRoutes(session, shipments, useFreighters, checkpoint=checkpoint,
                      verify_recipient=lambda index: _verify_recipient(session, routes[index]))
    else:
        executeRoutes(session, shipments, useFreighters, checkpoint=checkpoint)


@configurator
def sendResources(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        print("What type of ships do you want to use? (Default: Trade ships)")
        print("(1) Trade ships")
        print("(2) Freighters")
        shiptype = read(min=1, max=2, digit=True, empty=True)
        if shiptype == '':
            shiptype = 1
        if shiptype == 1:
            useFreighters = False
        elif shiptype == 2:
            useFreighters = True
        routes = []
        while True:

            banner()
            print("Origin city:")
            try:
                cityO = chooseCity(session)
            except KeyboardInterrupt:
                if routes:
                    print("Send shipment? [Y/n]")
                    rta = read(values=["y", "Y", "n", "N", ""])
                    if rta.lower() != "n":
                        break
                return None

            banner()
            print("Destination city")
            cityD = chooseCity(session, foreign=True)
            idIsland = cityD["islandId"]

            if cityO["id"] == cityD["id"]:
                continue

            resources_left = cityO["availableResources"]
            for route in routes:
                (origin_city, destination_city, __, *toSend) = route
                if origin_city["id"] == cityO["id"]:
                    for i in range(len(materials_names)):
                        resources_left[i] -= toSend[i]

                # the destination city might be from another player
                if cityD["isOwnCity"] and destination_city["id"] == cityD["id"]:
                    for i in range(len(materials_names)):
                        cityD["freeSpaceForResources"][i] -= toSend[i]

            banner()
            # the destination city might be from another player
            if cityD["isOwnCity"]:
                msg = ""
                for i in range(len(materials_names)):
                    if resources_left[i] > cityD["freeSpaceForResources"][i]:
                        msg += "{} more {}\n".format(
                            addThousandSeparator(cityD["freeSpaceForResources"][i]),
                            materials_names[i].lower(),
                        )

                if len(msg) > 0:
                    print("You can store just:\n{}".format(msg))

            print("Available:")
            for i in range(len(materials_names)):
                print(
                    "{}:{} ".format(
                        materials_names[i], addThousandSeparator(resources_left[i])
                    ),
                    end="",
                )
            print("")

            print("Send:")
            try:
                max_name = max([len(material) for material in materials_names])
                send = []
                for i in range(len(materials_names)):
                    material_name = materials_names[i]
                    pad = " " * (max_name - len(material_name))
                    val = askForValue(
                        "{}{}:".format(pad, material_name), resources_left[i]
                    )
                    send.append(val)
            except KeyboardInterrupt:
                continue
            if sum(send) == 0:
                continue

            banner()
            print(
                "About to send from {} to {}".format(
                    cityO["cityName"], cityD["cityName"]
                )
            )
            for i in range(len(materials_names)):
                if send[i] > 0:
                    print(
                        "{}:{} ".format(
                            materials_names[i], addThousandSeparator(send[i])
                        ),
                        end="",
                    )
            print("")

            print("Proceed? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() != "n":
                route = (cityO, cityD, idIsland, *send)
                routes.append(route)
                print("Create another shipment? [y/N]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() != "y":
                    break
    except KeyboardInterrupt:
        return None

    if not routes:
        return None

    # the task fetches the cities again: the saved config only holds their ids
    saved_routes = []
    for (origin_city, destination_city, island_id, *send) in routes:
        route = {"from": origin_city["id"], "to": destination_city["id"], "resources": send}
        if not destination_city["isOwnCity"]:
            route["island"] = island_id
        saved_routes.append(route)
    return {
        "session": session,
        "routes": saved_routes,
        "useFreighters": useFreighters,
    }
