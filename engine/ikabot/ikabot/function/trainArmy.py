#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import copy
import json
import re
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import getAvailableResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.helpers.varios import addThousandSeparator


def getBuildingInfo(session, city, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainTroops : bool

    Returns
    -------
    response : dict
    """
    view = "barracks" if trainTroops else "shipyard"
    params = {
        "view": view,
        "cityId": city["id"],
        "position": city["pos"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    data = session.post(params=params)
    return json.loads(data, strict=False)


def train(session, city, trainings, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainings : list[dict]
    trainTroops : bool
    """
    templateView = "barracks" if trainTroops else "shipyard"
    function = "buildUnits" if trainTroops else "buildShips"
    payload = {
        "action": "CityScreen",
        "function": function,
        "actionRequest": "REQUESTID",
        "cityId": city["id"],
        "position": city["pos"],
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": templateView,
        "ajax": "1",
    }
    for training in trainings:
        payload[training["unit_type_id"]] = training["train"]
    session.post(params=payload)


def waitForTraining(session, city, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainTroops : bool
    """
    data = getBuildingInfo(session, city, trainTroops)
    html = data[1][1][1]
    seconds = re.search(r"\'buildProgress\', (\d+),", html)
    if seconds:
        seconds = seconds.group(1)
        seconds = int(seconds) - data[0][1]["time"]
        wait(seconds + 5)


def planTrainings(session, city, trainings, trainTroops):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trainings : list[list[dict]]
    trainTroops : bool
    """
    buildingPos = city["pos"]

    # trainings might be divided in multriple rounds
    while True:

        # total number of units to create
        total = sum([unit["cantidad"] for training in trainings for unit in training])
        if total == 0:
            return

        for training in trainings:
            waitForTraining(session, city, trainTroops)
            html = session.get(city_url + city["id"])
            city = getCity(html)
            city["pos"] = buildingPos

            resourcesAvailable = city["availableResources"].copy()
            resourcesAvailable.append(city["freeCitizens"])

            # for each unit type in training
            for unit in training:

                # calculate how many units can actually be trained based on the resources available
                unit["train"] = unit["cantidad"]

                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        limiting = resourcesAvailable[i] // unit["costs"][material_name]
                        unit["train"] = min(unit["train"], limiting)

                if "citizens" in unit["costs"]:
                    limiting = (
                        resourcesAvailable[len(materials_names_english)]
                        // unit["costs"]["citizens"]
                    )
                    unit["train"] = min(unit["train"], limiting)

                # calculate the resources that will be left
                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        resourcesAvailable[i] -= (
                            unit["costs"][material_name] * unit["train"]
                        )

                if "citizens" in unit["costs"]:
                    resourcesAvailable[len(materials_names_english)] -= (
                        unit["costs"]["citizens"] * unit["train"]
                    )

                unit["cantidad"] -= unit["train"]

            # amount of units that will be trained
            total = sum([unit["train"] for unit in training])
            if total == 0:
                msg = "It was not possible to finish the training due to lack of resources."
                
                sendToBot(session, msg)
                return

            train(session, city, training, trainTroops)


def generateArmyData(units_info):
    """
    Parameters
    ----------
    units_info : dict

    Returns
    -------
    units : list[dict]
    """
    i = 1
    units = []
    while "js_barracksSlider{:d}".format(i) in units_info:
        # {'identifier':'phalanx','unit_type_id':303,'costs':{'citizens':1,'wood':27,'sulfur':30,'upkeep':3,'completiontime':71.169695412658},'local_name':'Hoplita'}
        info = units_info["js_barracksSlider{:d}".format(i)]["slider"]["control_data"]
        info = json.loads(info, strict=False)
        units.append(info)
        i += 1
    return units

from ikabot.helpers.decorators import configurator, task

def available_trainable_units(session, city_id, train_troops):
    """Read only actual recruitable troop/ship definitions from the game view."""
    import math
    from ikabot.helpers.taskConfig import requireOwnCity

    if type(train_troops) is not bool:
        raise ValueError("Choose troops or ships")
    owned = requireOwnCity(session, city_id, "city_id")
    city = getCity(session.get(city_url + str(owned)))
    if str(city.get("id")) != str(owned):
        raise ValueError("Game returned a different city")
    name = "barracks" if train_troops else "shipyard"
    building = next((row for row in city.get("position", [])
                     if row.get("building") == name), None)
    if building is None:
        raise ValueError("The selected city lacks this training building")
    position = building.get("position")
    if type(position) is not int or not 0 <= position <= 80:
        raise ValueError("Invalid training building position")
    building_city = {"id": str(owned), "pos": str(position),
                     "cityName": str(city["name"])[:100]}
    response = getBuildingInfo(session, building_city, train_troops)
    try:
        catalog = generateArmyData(response[2][1])
    except (IndexError, KeyError, ValueError, TypeError) as exc:
        raise ValueError("Recruitable units are not available from this city") from exc
    if not isinstance(catalog, list) or not 0 < len(catalog) <= 100:
        raise ValueError("No supported trainable units in this city")
    verified = []
    ids = set()
    allowed = {"wood", "wine", "marble", "crystal", "sulfur",
               "citizens", "upkeep", "completiontime"}
    for unit in catalog:
        if not isinstance(unit, dict):
            raise ValueError("Invalid game unit details")
        unit_id = unit.get("unit_type_id")
        label = unit.get("local_name")
        costs = unit.get("costs")
        if (type(unit_id) is not int or not 0 < unit_id < 10**7
                or unit_id in ids or not isinstance(label, str)
                or not 0 < len(label) <= 100 or not isinstance(costs, dict)
                or not set(costs).issubset(allowed)):
            raise ValueError("Malformed game unit data")
        safe_costs = {}
        for key, value in costs.items():
            if (type(value) not in (int, float)
                    or not math.isfinite(value) or not 0 <= value <= 10**9):
                raise ValueError("Invalid game unit cost")
            safe_costs[key] = value
        ids.add(unit_id)
        verified.append({
            "unit_type_id": unit_id, "local_name": label,
            "identifier": str(unit.get("identifier") or "")[:60],
            "costs": safe_costs,
        })
    stock = city.get("availableResources")
    citizens = city.get("freeCitizens")
    if (not isinstance(stock, list) or len(stock) != 5
            or any(type(x) is not int or x < 0 for x in stock)
            or type(citizens) is not int or citizens < 0):
        raise ValueError("City resources are unavailable")
    return {
        "city": building_city, "train_troops": train_troops,
        "units": verified, "available": list(stock), "free_citizens": citizens,
    }


def prepare_trainArmy(session, city, tranings, trainTroops, replicate,
                      countRepeat, cityTrainings, units):
    """Rebuild non-replicated native training from real game costs before launch."""
    if (not isinstance(city, dict) or not isinstance(tranings, list)
            or len(tranings) != 1 or not isinstance(tranings[0], list)
            or not 0 < len(tranings[0]) <= 50
            or type(trainTroops) is not bool
            or replicate != "n" or countRepeat != 0
            or cityTrainings != [] or units != []):
        raise ValueError("A native troop or ship plan must be explicit and city-specific")
    catalog = available_trainable_units(session, city.get("id"), trainTroops)
    current = catalog["city"]
    if city.get("pos") != current["pos"] or city.get("cityName") != current["cityName"]:
        raise ValueError("Training building or city changed; prepare again")
    available = {unit["unit_type_id"]: unit for unit in catalog["units"]}
    budget = {
        "wood": catalog["available"][0],
        "wine": catalog["available"][1],
        "marble": catalog["available"][2],
        "crystal": catalog["available"][3],
        "sulfur": catalog["available"][4],
        "citizens": catalog["free_citizens"],
    }
    verified = []
    seen = set()
    for entry in tranings[0]:
        if not isinstance(entry, dict) or set(entry) != {"unit_type_id", "cantidad"}:
            raise ValueError("Training selections require actual unit and quantity")
        unit_id, count = entry["unit_type_id"], entry["cantidad"]
        if (type(unit_id) is not int or unit_id not in available
                or unit_id in seen or type(count) is not int
                or not 0 < count <= 100000):
            raise ValueError("Invalid or repeated training unit")
        unit = available[unit_id]
        seen.add(unit_id)
        for key in budget:
            needed = unit["costs"].get(key, 0) * count
            if needed > budget[key]:
                raise ValueError("Not enough city resources or citizens for this training")
            budget[key] -= needed
        verified.append({**unit, "cantidad": count})
    return {
        "city": current, "tranings": [verified],
        "trainTroops": trainTroops, "replicate": "n",
        "countRepeat": 0, "cityTrainings": [], "units": [],
    }


@task("trainArmy", prepare=prepare_trainArmy)
def do_trainArmy(session, city, tranings, trainTroops, replicate, countRepeat, cityTrainings, units):
    if replicate == "y":
        countRepeat = countRepeat + 1
        while countRepeat > 0:
            for cityId in cityTrainings:
                html = session.get(city_url + str(cityId))
                loop_city = getCity(html)

                lookfor = "barracks" if trainTroops else "shipyard"
                try:
                    for i in range(len(loop_city["position"])):
                        if loop_city["position"][i]["building"] == lookfor:
                            loop_city["pos"] = str(i)
                            tranings_copy = []
                            units_copy = copy.deepcopy(units)
                            tranings_copy.append(units_copy)
                            planTrainings(
                                session, loop_city, tranings_copy, trainTroops
                            )
                            break
                except Exception as e:
                    if trainTroops:
                        info = "\nI train troops in {}\n".format(
                            loop_city["cityName"]
                        )
                    else:
                        info = "\nI train fleets in {}\n".format(
                            loop_city["cityName"]
                        )
                    msg = "Error in:\n{}\nCause:\n{}".format(
                        info, traceback.format_exc()
                    )
                    sendToBot(session, msg)
            countRepeat = countRepeat - 1

    else:
        if trainTroops:
            info = "\nI train troops in {}\n".format(city["cityName"])
        else:
            info = "\nI train fleets in {}\n".format(city["cityName"])
        setInfoSignal(session, info)
        planTrainings(session, city, tranings, trainTroops)
@configurator
def trainArmy(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    print("Do you want to train troops (1) or ships (2)?")
    rta = read(min=1, max=2)
    trainTroops = rta == 1
    banner()

    if trainTroops:
        print("In what city do you want to train the troops?")
    else:
        print("In what city do you want to train the fleet?")
    city = chooseCity(session)
    banner()

    lookfor = "barracks" if trainTroops else "shipyard"
    for i in range(len(city["position"])):
        if city["position"][i]["building"] == lookfor:
            city["pos"] = str(i)
            break
    else:
        if trainTroops:
            print("Barracks not built.")
        else:
            print("Shipyard not built.")
        enter()
        return None

    data = getBuildingInfo(session, city, trainTroops)

    units_info = data[2][1]
    units = generateArmyData(units_info)

    maxSize = max([len(unit["local_name"]) for unit in units])

    tranings = []
    while True:
        units = generateArmyData(units_info)
        print("Train:")
        for unit in units:
            pad = " " * (maxSize - len(unit["local_name"]))
            amount = read(
                msg="{}{}:".format(pad, unit["local_name"]), min=0, empty=True
            )
            if amount == "":
                amount = 0
            unit["cantidad"] = amount

        # calculate costs
        cost = [0] * (len(materials_names_english) + 3)
        for unit in units:
            for i in range(len(materials_names_english)):
                material_name = materials_names_english[i].lower()
                if material_name in unit["costs"]:
                    cost[i] += unit["costs"][material_name] * unit["cantidad"]

            if "citizens" in unit["costs"]:
                cost[len(materials_names_english) + 0] += (
                    unit["costs"]["citizens"] * unit["cantidad"]
                )
            if "upkeep" in unit["costs"]:
                cost[len(materials_names_english) + 1] += (
                    unit["costs"]["upkeep"] * unit["cantidad"]
                )
            if "completiontime" in unit["costs"]:
                cost[len(materials_names_english) + 2] += (
                    unit["costs"]["completiontime"] * unit["cantidad"]
                )

        print("\nTotal cost:")
        for i in range(len(materials_names_english)):
            if cost[i] > 0:
                print(
                    "{}: {}".format(
                        materials_names_english[i], addThousandSeparator(cost[i])
                    )
                )
        if cost[len(materials_names_english) + 0] > 0:
            print(
                "Citizens: {}".format(
                    addThousandSeparator(cost[len(materials_names_english) + 0])
                )
            )
        if cost[len(materials_names_english) + 1] > 0:
            print(
                "Maintenance: {}".format(
                    addThousandSeparator(cost[len(materials_names_english) + 1])
                )
            )
        if cost[len(materials_names_english) + 2] > 0:
            print(
                "Duration: {}".format(
                    daysHoursMinutes(int(cost[len(materials_names_english) + 2]))
                )
            )

        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            return None

        tranings.append(units)

        if trainTroops:
            print("\nDo you want to train more troops when you finish? [y/N]")
        else:
            print("\nDo you want to train more fleets when you finish? [y/N]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "y":
            banner()
            if trainTroops:
                print("Train new troops (1) or repeat (2)?")
            else:
                print("Train new fleets (1) or repeat (2)?")
            rta = read(min=1, max=2)
            if rta == 1:
                continue
            else:
                print("\nRepeat how many times?")
                countRepeat = read(min=1, default=0)
                break
        else:
            countRepeat = 0
            break

    print("Do you want to replicate the training to other cities? (y/N)")
    replicate = read(values=["y", "Y", "n", "N", ""])
    cityTrainings = []
    if replicate.lower() == "y":
        ids, cities = getIdsOfCities(session)

        print("(0) Back")
        print("(1) All the wine cities")
        print("(2) All the marble cities")
        print("(3) All the cristal cities")
        print("(4) All the sulfur cities")
        print("(5) Choose City")
        print("(6) All City")

        selected = read(min=0, max=6, digit=True)
        if selected == 0:
            return None
        elif selected in [1, 2, 3, 4]:
            cityTrainings = filterCitiesByResource(
                cities, resourceMapping[selected], cityTrainings
            )
        elif selected == 5:
            loop_city = []
            while True:
                loop_city = chooseCity(session)
                if loop_city["id"] in cityTrainings:
                    print("\nYou have already selected this city!")
                    continue
                cityTrainings.append(loop_city["id"])
                print("\nDo you want to add another city? [y/N]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "y":
                    continue
                else:
                    break
        elif selected == 6:
            ids, cities = getIdsOfCities(session)
            for cityId in ids:
                cityTrainings.append(cityId)

    # calculate if the city has enough resources
    resourcesAvailable = city["availableResources"].copy()
    resourcesAvailable.append(city["freeCitizens"])

    for training in tranings:
        for unit in training:
            if unit["cantidad"] != 0:
                for i in range(len(materials_names_english)):
                    material_name = materials_names_english[i].lower()
                    if material_name in unit["costs"]:
                        resourcesAvailable[i] -= (
                            unit["costs"][material_name] * unit["cantidad"]
                        )

                if "citizens" in unit["costs"]:
                    resourcesAvailable[len(materials_names_english)] -= (
                        unit["costs"]["citizens"] * unit["cantidad"]
                    )

    not_enough = [elem for elem in resourcesAvailable if elem < 0] != []

    if not_enough:
        print("\nThere are not enough resources:")
        for i in range(len(materials_names_english)):
            if resourcesAvailable[i] < 0:
                print(
                    "{}:{}".format(
                        materials_names[i],
                        addThousandSeparator(resourcesAvailable[i] * -1),
                    )
                )

        if resourcesAvailable[len(materials_names_english)] < 0:
            print(
                "Citizens:{}".format(
                    addThousandSeparator(
                        resourcesAvailable[len(materials_names_english)] * -1
                    )
                )
            )

        print("\nProceed anyway? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            return None

    if trainTroops:
        print("\nThe selected troops will be trained.")
    else:
        print("\nThe selected fleet will be trained.")
    enter()

    return {
        "session": session,
        "city": city,
        "tranings": tranings,
        "trainTroops": trainTroops,
        "replicate": replicate.lower(),
        "countRepeat": countRepeat,
        "cityTrainings": cityTrainings,
        "units": units
    }


def filterCitiesByResource(cities, resource_id, cityTrainings):
    for cityId, cityData in cities.items():
        if cityData["tradegood"] == resource_id:
            cityTrainings.append(cityData["id"])
    return cityTrainings


resourceMapping = {
    1: "1",  # Wine
    2: "2",  # Marble
    3: "3",  # Cristal
    4: "4",  # Sulfur
}
