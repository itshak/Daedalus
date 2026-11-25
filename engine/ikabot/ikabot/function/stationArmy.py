from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
import hashlib
import json
import re

from ikabot.config import *
from ikabot.helpers.naval import getAvailableShips
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addThousandSeparator
from ikabot.helpers.pedirInfo import getShipCapacity

def getCityMilitaryData(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int

    returns
    -------
    data : dict
    """
    params = {
        "view": "cityMilitary",
        "activeTab": "tabUnits",
        "cityId": city_id,
        "currentTab": "tabUnits",
        "currentCityId": city_id,
        "templateView": "cityMilitary",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    data = session.post(params=params)
    data = json.loads(data, strict=False)
    return data[1][1][1]


def extractTooltipsAndValues(data):
    tooltips =  re.findall(r'<div[^>]*class="[^"]*tooltip[^"]*"[^>]*>(.*?)</div>', data)
    values = re.findall(r"<td>\s*([^<]+)\s*</td>", data)
    return tooltips, values


def calculateTotals(tooltips, values):
    total_units = 0
    total_ships = 0

    desc_value_dict = {}

    for i, (tooltip, value) in enumerate(zip(tooltips, values)):
        value = re.sub(r'[\.,\s]|&nbsp;', '', value)
        is_digit = value.isdigit()
        int_value = int(value) if is_digit else 0

        if is_digit and int_value > 0:
            desc_value_dict.setdefault(tooltip, []).append(int_value)

            if i <= 14:
                total_units += int_value
            else:
                total_ships += int_value

    return desc_value_dict, total_units, total_ships


def getArmyAvailable(session, type_army, destination_city_id, origin_city_id, event):
    params = {
        "view": "deployment",
        "deploymentType": "army" if type_army else "fleet",
        "destinationCityId": destination_city_id,
        "backgroundView": "city",
        "currentCityId": origin_city_id,
        "actionRequest": actionRequest,
        "ajax": 1,
    }
    ship_capacity, freighter_capacity = getShipCapacity(session)

    data = session.post(params=params)
    amount_results = re.findall(r'<div class=\\"amount\\">(.*?)<\\/div>', data)

    if type_army:
        army_results = re.findall(
            r'name=\\"cargo_army_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data
        )
        weight_total_ships = int(getAvailableShips(session)) * ship_capacity if type_army else 0
        weight_results = re.findall(r'<div class=\\"weight\\">(.*?)<\\/div>', data)
    else:
        army_results = re.findall(
            r'name=\\"cargo_fleet_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data
        )

    army_available = {}
    weight_total_army = 0

    if army_results:
        for i, result in enumerate(army_results):
            army_code = result[0]
            army = "cargo_{}_{}_upkeep".format(
                "army" if type_army else "fleet", army_code
            )
            army_only = "cargo_{}_{}".format(
                "army" if type_army else "fleet", army_code
            )
            upkeep = result[1]
            quantity = amount_results[i]
            army_available[army] = upkeep
            army_available[army_only] = quantity
            if type_army and weight_results and int(weight_results[i]) > 0:
                weight_total_army += int(quantity) * int(weight_results[i])

        if type_army and weight_total_army > weight_total_ships:
            banner()
            print("Not enough ships to transport all the units!")
            enter()
            return None
        return army_available
    return None


def sendArmy(session, origin_city, destination_city, type_army, army_available):
    params = {
        "action": "transportOperations",
        "function": "deployArmy" if type_army else "deployFleet",
        "actionRequest": actionRequest,
        "islandId": destination_city["islandId"],
        "destinationCityId": destination_city["id"],
        "deploymentType": "army" if type_army else "fleet",
        "backgroundView": "city",
        "currentCityId": origin_city["id"],
        "templateView": "deployment",
        "ajax": 1,
    }

    for army in army_available:
        params[army] = army_available[army]

    session.post(params=params)


def _station_plan(session, city_id, destination_city_id, ground):
    if (type(city_id) is not int or type(destination_city_id) is not int
            or not 0 < city_id < 10**12 or not 0 < destination_city_id < 10**12
            or city_id == destination_city_id or type(ground) is not bool):
        raise ValueError("Choose two different owned cities and a deployment mode")
    pedirInfo.ids_cache = None
    origin = requireOwnCity(session, city_id, "Origin city")
    destination = requireOwnCity(session, destination_city_id, "Destination city")
    origin_city = getCityById(session, origin)
    target_city = getCityById(session, destination)
    if str(origin_city["id"]) != origin or str(target_city["id"]) != destination:
        raise ValueError("City identity changed")
    island = int(target_city["islandId"])
    if not 0 < island < 10**12:
        raise ValueError("Invalid destination island")
    # The original CLI deployment view, but no interactive prompts or mutation.
    mode = "army" if ground else "fleet"
    data = session.post(params={
        "view": "deployment", "deploymentType": mode,
        "destinationCityId": destination, "backgroundView": "city",
        "currentCityId": origin, "actionRequest": actionRequest, "ajax": 1,
    })
    amounts = re.findall(r'<div class=\\"amount\\">(.*?)<\\/div>', data)
    codes = re.findall(r'name=\\"cargo_' + mode + r'_([^\\]+)_upkeep\\"\\n\s+value=\\"([^\\"]+)\\"', data)
    weights = re.findall(r'<div class=\\"weight\\">(.*?)<\\/div>', data) if ground else []
    if len(codes) != len(amounts) or len(codes) > 100 or (ground and len(codes) != len(weights)):
        raise ValueError("Incomplete deployment inventory")
    cargo = {}
    total = weight = 0
    for index, (code, upkeep) in enumerate(codes):
        if not re.fullmatch(r"[0-9]{1,6}", code) or not re.fullmatch(r"[0-9]{1,10}", upkeep):
            raise ValueError("Invalid deployment unit")
        quantity = amounts[index]
        if not re.fullmatch(r"[0-9]{1,10}", quantity):
            raise ValueError("Invalid deployment quantity")
        key = f"cargo_{mode}_{code}"
        if key in cargo:
            raise ValueError("Repeated deployment unit")
        cargo[key] = int(quantity)
        cargo[key + "_upkeep"] = int(upkeep)
        total += int(quantity)
        if ground:
            if not re.fullmatch(r"[0-9]{1,8}", weights[index]):
                raise ValueError("Invalid deployment weight")
            weight += int(quantity) * int(weights[index])
    # An exact available-transport capacity is required for ground deployments.
    capacity = None
    if ground:
        ship_capacity, _ = getShipCapacity(session)
        free_ships = int(getAvailableShips(session))
        if type(ship_capacity) is not int or not 0 < ship_capacity <= 10**8 or not 0 <= free_ships <= 10**8:
            raise ValueError("Invalid transport capacity")
        capacity = free_ships * ship_capacity
    if total > 10**12 or weight > 10**15:
        raise ValueError("Deployment exceeds safe preview size")
    expected = hashlib.sha256(json.dumps(
        [city_id, destination_city_id, ground, island, cargo, weight],
        sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    plan = {"city_id": city_id, "destination_city_id": destination_city_id, "ground": ground,
            "city_name": str(origin_city["cityName"])[:100],
            "destination_name": str(target_city["cityName"])[:100],
            "total": total, "weight": weight if ground else None, "capacity": capacity,
            "ready": total > 0 and (not ground or weight <= capacity),
            "config": {"city_id": city_id, "destination_city_id": destination_city_id,
                       "ground": ground, "expected": expected}}
    return plan, cargo, island


def preview_native_station(session, city_id, destination_city_id, ground):
    return _station_plan(session, city_id, destination_city_id, ground)[0]


def prepare_native_station(session, city_id, destination_city_id, ground, expected):
    plan = preview_native_station(session, city_id, destination_city_id, ground)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Deployment review is stale or unavailable")
    return plan["config"]


@task("stationArmy", prepare=prepare_native_station)
def native_station(session, city_id: int, destination_city_id: int, ground: bool, expected: str):
    plan, cargo, island = _station_plan(session, city_id, destination_city_id, ground)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Deployment review is stale or unavailable")
    mode = "army" if ground else "fleet"
    session.setStatus("Submitting reviewed owned-city deployment")
    session.post(params={
        "action": "transportOperations", "function": "deployArmy" if ground else "deployFleet",
        "actionRequest": actionRequest, "islandId": str(island),
        "destinationCityId": str(destination_city_id), "deploymentType": mode,
        "backgroundView": "city", "currentCityId": str(city_id), "templateView": "deployment",
        "ajax": 1, **cargo,
    }, retry_on_failure=False)
    session.setStatus("Deployment submitted; verify military movements")


@configurator
def stationArmy(session, event, stdin_fd, predetermined_input):
    type_army = True
    try:
        banner()

        ids, cities = getIdsOfCities(session)
        army = {}
        print("Total:")
        print("{:>19}|{:>19}|{:>19}|".format("", "Units", "Ships"))

        for city_id in cities:
            city = cities[city_id]
            data = getCityMilitaryData(session, city["id"])
            desc, values = extractTooltipsAndValues(data)
            army, total_units, total_ships = calculateTotals(desc, values)

            print(
                "{:>19}|{:>19}|{:>19}|".format(
                    city["name"],
                    addThousandSeparator(total_units),
                    addThousandSeparator(total_ships),
                )
            )

        print()
        print("(0) Back")
        print("(1) Move troops")
        print("(2) Move ships")
        print("(3) Move all ground units to a city.")
        print("(4) Move all maritime units to a city.")
        print("(5) Move all units to a city.")

        selected = read(min=0, max=5, digit=True)
        if selected == 0:
            event.set()
            return
        elif selected in (1, 2):
            print("Origin city:")
            origin_city = chooseCity(session)
            print()
            print("Destination city:")
            destination_city = chooseCity(session)
            if origin_city["id"] == destination_city["id"]:
                banner()
                print("The city of origin and the destination city cannot be the same!")
                enter()
                event.set()
            else:
                type_army = selected == 1
                army_available = getArmyAvailable(
                    session, type_army, destination_city["id"], origin_city["id"], event
                )
                if army_available != None:
                    sendArmy(
                        session,
                        origin_city,
                        destination_city,
                        type_army,
                        army_available,
                    )
                    print("Army sent!")
                    enter()
                    event.set()
                else:
                    print()
                    print(
                        "No {} units available in {}.".format(
                            "ground" if type_army else "maritime", origin_city["name"]
                        )
                    )
                    enter()
                    event.set()
        elif selected in (3, 4, 5):
            print("Destination city:")
            destination_city = chooseCity(session)
            ids, cities = getIdsOfCities(session)

            if selected in (3, 5):
                type_army = True
                for city_id in cities:
                    if city_id != destination_city["id"]:
                        city = cities[city_id]
                        army_available = getArmyAvailable(
                            session,
                            type_army,
                            destination_city["id"],
                            city["id"],
                            event,
                        )
                        if army_available != None:
                            sendArmy(
                                session,
                                city,
                                destination_city,
                                type_army,
                                army_available,
                            )
                        else:
                            print(
                                "No ground units available in {}.".format(city["name"])
                            )
            if selected in (4, 5):
                type_army = False
                for city_id in cities:
                    if city_id != destination_city["id"]:
                        city = cities[city_id]
                        army_available = getArmyAvailable(
                            session,
                            type_army,
                            destination_city["id"],
                            city["id"],
                            event,
                        )
                        if army_available != None:
                            sendArmy(
                                session,
                                city,
                                destination_city,
                                type_army,
                                army_available,
                            )
                        else:
                            print(
                                "No maritime units available in {}.".format(
                                    city["name"]
                                )
                            )
            enter()
            event.set()
    except KeyboardInterrupt:
        event.set()
        return
