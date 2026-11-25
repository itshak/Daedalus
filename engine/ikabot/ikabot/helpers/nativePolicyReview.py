"""Read-only policy observations using existing upstream game helpers."""
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import getCityById
from ikabot.helpers.varios import decodeUnicodeEscape


def preview_recurring(session, task, draft):
    pedirInfo.ids_cache = None
    own_ids, cities = pedirInfo.getIdsOfCities(session)
    if task == "searchForIslandSpaces":
        from ikabot.function.searchForIslandSpaces import prepare_searchForIslandSpaces
        from ikabot.function.sendResources import get_island

        prepare_searchForIslandSpaces(session, **draft)
        selected = draft["islandList"] or list(dict.fromkeys(
            cities[c]["coords"].strip().strip("[]") for c in own_ids))
        for coord in selected:
            island = get_island(session, coord, "Monitoring island")
            if f"{int(island['x'])}:{int(island['y'])}" != coord:
                raise ValueError("Island coordinates changed")
        return {"islands": selected}
    if task == "dumpWorld":
        from ikabot.function.dumpWorld import prepare_dumpWorld
        from ikabot.helpers.nativeWorldReports import ensure_capacity

        prepare_dumpWorld(session, **draft)
        ensure_capacity(session)
        return {"scope": "region" if draft["coords"] is not None else "world", "aggregate_only": True}
    if task == "donationBot":
        from ikabot.function.donationBot import prepare_donationBot

        prepare_donationBot(session, **draft)
        chosen = list(draft["cities_dict"])
    elif task == "consolidateResources":
        from ikabot.function.consolidateResources import prepare_consolidateResources

        prepare_consolidateResources(session, **draft)
        chosen = [*draft["sourceCityIds"], draft["destinationCityId"]]
        fleet_types = ("trade", "freighter") if draft["shipType"] == 3 else (
            "freighter",) if draft["shipType"] == 2 else ("trade",)
    elif task == "resourceTransportManager":
        from ikabot.function.resourceTransportManager import prepare_resourceTransportManager

        prepare_resourceTransportManager(session, **draft)
        if draft["mode"] == "consolidate":
            chosen = list(draft["origin_cities"])
            if "recipient" not in draft:
                chosen.append(draft["destination_city"])
        else:
            chosen = [draft["origin_city"], *draft["destination_cities"]]
        fleet_types = ("freighter",) if draft["useFreighters"] else ("trade",)
    else:
        raise ValueError("Unsupported policy")
    rows = []
    for city_id in chosen:
        key = str(city_id)
        if key not in own_ids:
            raise ValueError("City ownership changed")
        city = getCityById(session, key)
        if str(city["id"]) != key:
            raise ValueError("City identity changed")
        rows.append({"id": int(key), "name": decodeUnicodeEscape(cities[key]["name"])[:120],
                     "coords": cities[key]["coords"].strip().strip("[]"),
                     "stock": city["availableResources"], "space": city["freeSpaceForResources"]})
    if task == "donationBot":
        return {"cities": rows}
    from ikabot.function.sendResources import _eligible_destinations, _verify_recipient, get_island
    from ikabot.helpers.naval import getAvailableShips, getTotalShips, getAvailableFreighters, getTotalFreighters

    trade, freighter = pedirInfo.getShipCapacity(session)
    fleets = {}
    if "trade" in fleet_types:
        fleets["trade"] = {"capacity": trade, "free": getAvailableShips(session), "total": getTotalShips(session)}
    if "freighter" in fleet_types:
        fleets["freighter"] = {"capacity": freighter, "free": getAvailableFreighters(session), "total": getTotalFreighters(session)}
    external = None
    if "recipient" in draft:
        island = get_island(session, draft["island"], "Destination island")
        route = {"to": draft["destination_city"], "island": draft["island"], "recipient": draft["recipient"]}
        _verify_recipient(session, route, island)
        external = next(r for r in _eligible_destinations(session, island)
                        if r["id"] == draft["destination_city"])
    return {"cities": rows, "fleets": fleets, "external": external}
