#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import hashlib
import html
import json
import math
import random
import re
import threading
import time
import traceback
from decimal import *
from urllib.parse import parse_qs, urlparse

import requests
from functools import cache

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import *
from ikabot.helpers.resources import getAvailableResources
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *
from ikabot.web.session import normal_get
from ikabot.helpers.decorators import configurator, task


def _parseConstructionTime(row):
    cells = re.findall(r'<td class="costs">(.*?)</td>', row, re.DOTALL)
    if not cells:
        return None

    cell = cells[-1]
    match = re.search(r'data-(?:seconds|duration|time)=["\'](\d+)', cell)
    if match:
        return int(match.group(1))

    values = re.findall(r'title=["\']([^"\']+)', cell)
    values.append(re.sub(r"<[^>]+>", " ", html.unescape(cell)))
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for value in values:
        parts = re.findall(r"(\d+)\s*([dhms])", value.lower())
        if parts:
            return sum(int(amount) * units[unit] for amount, unit in parts)
    return None


def _formatRemainingTime(seconds):
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    values = ((days, "D"), (hours, "H"), (minutes, "M"), (seconds, "S"))
    return " ".join("{}{}".format(value, unit) for value, unit in values if value) or "0S"


def _findHtml(value, element_id):
    if isinstance(value, str):
        return value if element_id in value and "ambrosiaIcon" in value else None
    if isinstance(value, list):
        for item in value:
            result = _findHtml(item, element_id)
            if result is not None:
                return result
    if isinstance(value, dict):
        for item in value.values():
            result = _findHtml(item, element_id)
            if result is not None:
                return result
    return None


def _getFreeSpeedupParams(response, city_id, position):
    try:
        popup = _findHtml(json.loads(response, strict=False), "js_buildingSpeedupActivateBtn")
    except (TypeError, ValueError):
        popup = response if isinstance(response, str) else None
    if popup is None:
        return None

    buttons = re.findall(
        r'<a\b(?=[^>]*\bid=["\']js_buildingSpeedupActivateBtn["\'])[^>]*>.*?</a>',
        popup,
        re.DOTALL,
    )
    if len(buttons) != 1:
        return None
    button = buttons[0]

    span_pattern = r'<span\b(?=[^>]*\bclass=["\'][^"\']*\bambrosiaIcon\b[^"\']*["\'])[^>]*>'
    ambrosia_spans = re.findall(span_pattern, button)
    costs = re.findall(span_pattern + r'\s*(\d+)\s*</span>', button)
    if len(ambrosia_spans) != 1 or len(costs) != 1 or costs[0] != "0":
        return None

    href = re.search(r'href=["\']([^"\']+)', button)
    if href is None:
        return None

    query = parse_qs(urlparse(html.unescape(href.group(1))).query)
    required = {
        "action": "Premium",
        "function": "buildingSpeedup",
        "cityId": str(city_id),
        "position": str(position),
    }
    if any(query.get(key) != [value] for key, value in required.items()):
        return None
    if query.get("currentCityId", [str(city_id)]) != [str(city_id)]:
        return None
    if len(query.get("level", [])) != 1 or not query["level"][0].isdigit():
        return None

    return {
        **required,
        "level": query["level"][0],
        "backgroundView": "city",
        "currentCityId": str(city_id),
        "actionRequest": actionRequest,
        "ajax": "1",
    }


def tryFreeBuildingSpeedup(session, city_id, building):
    popup_params = {
        "view": "buildingSpeedup",
        "cityId": city_id,
        "position": building["position"],
        "backgroundView": "city",
        "currentCityId": city_id,
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    response = session.post(params=popup_params)
    speedup_params = _getFreeSpeedupParams(response, city_id, building["position"])
    if speedup_params is None:
        return False

    wait(random.randint(1, SPEEDUP_RANDOMWAIT)) # random wait
    # Recheck the current price and target after the delay before activating.
    response = session.post(params=popup_params)
    speedup_params = _getFreeSpeedupParams(response, city_id, building["position"])
    if speedup_params is None:
        return False

    session.post(params=speedup_params)
    return True


def waitForConstruction(session, city_id, final_lvl, construction_queue=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    final_lvl : int

    Returns
    -------
    city : dict
    """
    while True:

        html = session.get(city_url + city_id)
        city = getCity(html)

        construction_buildings = [
            building for building in city["position"] if "completed" in building
        ]
        if len(construction_buildings) == 0:
            break

        construction_building = construction_buildings[0]
        construction_time = construction_building["completed"]

        current_time = int(time.time())
        final_time = int(construction_time)
        seconds_to_wait = final_time - current_time
        current_remaining = max(0, seconds_to_wait)
        total_remaining = current_remaining + sum(construction_queue or [])
        status = "{}: {} -> level {} , current {} , total {}".format(
            city["cityName"],
            construction_building["name"],
            construction_building["level"] + 1,
            _formatRemainingTime(seconds_to_wait),
            _formatRemainingTime(total_remaining),
        )
        session.setStatus(status)

        if CONSTRUCTION_FREE_SPEEDUP and 0 < seconds_to_wait <= 300:
            if tryFreeBuildingSpeedup(session, city_id, construction_building):
                session.setStatus(status + " , free speedup sent")
                msg = "{}: Finished {} for 0 Ambrosia".format(
                    city["cityName"], construction_building["name"]
                )
                sendToBotDebug(session, msg, debugON_constructionList)
            else:
                session.setStatus(status + " , waiting for zero-cost speedup")
            wait(5)
            continue

        msg = "{}: I wait {:d} seconds so that {} gets to the level {:d}".format(
            city["cityName"],
            seconds_to_wait,
            construction_building["name"],
            construction_building["level"] + 1,
        )
        sendToBotDebug(session, msg, debugON_constructionList)
        if CONSTRUCTION_FREE_SPEEDUP:
            wait(max(5, seconds_to_wait - 300))
        else:
            wait(max(5, seconds_to_wait + 10))

    html = session.get(city_url + city_id)
    city = getCity(html)
    return city


def expandBuilding(session, cityId, building, waitForResources, construction_queue=None, *, reviewed=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int
    building : dict
    waitForResources : bool
    """
    reviewed_building = building["building"] if reviewed else None
    current_level = building["level"]
    if building["isBusy"]:
        current_level += 1
    levels_to_upgrade = building["upgradeTo"] - current_level
    position = building["position"]
    upgradeTo = building["upgradeTo"]
    time.sleep(
        random.randint(5, 15)
    )  # to avoid race conditions with sendResourcesNeeded

    for lv in range(levels_to_upgrade):
        city = waitForConstruction(session, cityId, upgradeTo, construction_queue)
        if reviewed:
            if str(city["id"]) != str(cityId):
                raise ValueError("Construction destination changed")
            building = next((b for b in city["position"] if b["position"] == position), None)
            if (building is None or building.get("building") != reviewed_building
                    or building.get("level") != current_level + lv or building.get("isBusy") is True):
                raise ValueError("Reviewed construction level or building changed")
        else:
            building = city["position"][position]

        if building["canUpgrade"] is False and waitForResources is True:
            while building["canUpgrade"] is False:
                time.sleep(60)
                seconds = getMinimumWaitingTime(session)
                html = session.get(city_url + cityId)
                city = getCity(html)
                building = city["position"][position]
                # if no ships are comming, exit no matter if the building can or can't upgrade
                if seconds == 0:
                    break
                wait(seconds + 5)

        if building["canUpgrade"] is False:
            if reviewed:
                raise ValueError("Reviewed construction no longer affordable")
            msg = "City:{}\n".format(city["cityName"])
            msg += "Building:{}\n".format(building["name"])
            msg += "The building could not be completed due to lack of resources.\n"
            msg += "Missed {:d} levels".format(levels_to_upgrade - lv)
            sendToBot(session, msg)
            return

        url = "action=UpgradeExistingBuilding&actionRequest={}&cityId={}&position={:d}&level={}&activeTab=tabSendTransporter&backgroundView=city&currentCityId={}&templateView={}&ajax=1".format(
            actionRequest,
            cityId,
            position,
            building["level"],
            cityId,
            building["building"],
        )
        resp = session.post(url, retry_on_failure=False) if reviewed else session.post(url)
        html = session.get(city_url + cityId)
        city = getCity(html)
        if reviewed:
            if str(city["id"]) != str(cityId):
                raise ValueError("Construction destination changed")
            building = next((b for b in city["position"] if b["position"] == position), None)
            if (building is None or building.get("building") != reviewed_building
                    or building.get("level") != current_level + lv or building.get("isBusy") is not True):
                raise ValueError("Reviewed upgrade submission not observed")
        else:
            building = city["position"][position]
        if building["isBusy"] is False:
            msg = "{}: The building {} was not extended".format(
                city["cityName"], building["name"]
            )
            sendToBot(session, msg)
            sendToBot(session, resp)
            return
        if construction_queue:
            construction_queue.pop(0)

        msg = "{}: The building {} is being extended to level {:d}.".format(
            city["cityName"], building["name"], building["level"] + 1
        )
        sendToBotDebug(session, msg, debugON_constructionList)

    city = waitForConstruction(session, cityId, upgradeTo, construction_queue)
    building = (next((b for b in city["position"] if b["position"] == position), None)
                if reviewed else city["position"][position])
    if reviewed and (building is None or building.get("level") != upgradeTo or building.get("building") != reviewed_building):
        raise ValueError("Reviewed upgrade completion not observed")
    msg = "{}: The building {} finished extending to level: {:d}.".format(
        city["cityName"], building["name"], building["level"]
    )
    sendToBotDebug(session, msg, debugON_constructionList)


def getCostsReducers(city):
    """
    Parameters
    ----------
    city : dict

    Returns
    -------
    reducers_per_material_level : dict[int, int]
    """
    reducers_per_material = [0] * len(materials_names)
    assert len(reducers_per_material) == 5

    for building in city["position"]:
        if building["name"] == "empty":
            continue
        lv = building["level"]
        if building["building"] == "carpentering":
            reducers_per_material[0] = lv
        elif building["building"] == "vineyard":
            reducers_per_material[1] = lv
        elif building["building"] == "architect":
            reducers_per_material[2] = lv
        elif building["building"] == "optician":
            reducers_per_material[3] = lv
        elif building["building"] == "fireworker":
            reducers_per_material[4] = lv
    return reducers_per_material


def getResourcesNeeded(session, city, building, current_level, final_level, simulated_reducers=None, *, noninteractive=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    building : dict
    current_level : int
    final_level : int
    simulated_reducers : list[int]

    Returns
    -------
    costs_per_material : dict[int, int]
    """
    # get html with information about buildings
    building_detail_url = "view=buildingDetail&buildingId=0&helpId=1&backgroundView=city&currentCityId={}&templateView=ikipedia&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    building_detail_response = session.post(building_detail_url)
    building_detail = json.loads(building_detail_response, strict=False)
    building_html = building_detail[1][1][1]

    # get html with information about buildings costs
    regex_building_detail = (
        r'<div class="(?:selected)? button_building '
        + re.escape(building["building"])
        + r'"\s*onmouseover="\$\(this\)\.addClass\(\'hover\'\);" onmouseout="\$\(this\)\.removeClass\(\'hover\'\);"\s*onclick="ajaxHandlerCall\(\'\?(.*?)\'\);'
    )
    match = re.search(regex_building_detail, building_html)
    building_costs_url = match.group(1)
    building_costs_url += "backgroundView=city&currentCityId={}&templateView=buildingDetail&actionRequest={}&ajax=1".format(
        city["id"], actionRequest
    )
    building_costs_response = session.post(building_costs_url)
    building_costs = json.loads(building_costs_response, strict=False)
    html_costs = building_costs[1][1][1]

    # if the user has all the resource saving studies, we save that in the session data (one less request)
    sessionData = session.getSessionData()
    if "reduccion_inv_max" in sessionData:
        costs_reduction = 14
    else:
        # get the studies
        url = "view=noViewChange&researchType=economy&backgroundView=city&currentCityId={}&templateView=researchAdvisor&actionRequest={}&ajax=1".format(
            city["id"], actionRequest
        )
        rta = session.post(url)
        rta = json.loads(rta, strict=False)
        studies = rta[2][1]["new_js_params"]
        studies = json.loads(studies, strict=False)
        studies = studies["currResearchType"]

        # look for resource saving studies
        costs_reduction = 0
        for study in studies:
            if studies[study]["liClass"] != "explored":
                continue
            link = studies[study]["aHref"]
            if "2020" in link:
                costs_reduction += 2
            elif "2060" in link:
                costs_reduction += 4
            elif "2100" in link:
                costs_reduction += 8

        # if the user has all the resource saving studies, save that in the session data
        if costs_reduction == 14:
            sessionData["reduccion_inv_max"] = True
            if not noninteractive:
                session.setSessionData(sessionData)

    # calculate cost reductions
    costs_reduction /= 100
    costs_reduction = 1 - costs_reduction

    # get buildings that reduce the cost of upgrades
    if simulated_reducers is None:
        costs_reductions = getCostsReducers(city)
    else:
        costs_reductions = simulated_reducers

    # get the type of resources that this upgrade will cost (wood, marble, etc)
    resources_types = re.findall(
        r'<th class="costs"><img src="(.*?)\.png"/></th>', html_costs
    )[:-1]

    # get the actual cost of each upgrade
    matches = re.findall(
        r'<td class="level">\d+</td>(?:\s+<td class="costs">.*?</td>)+', html_costs
    )

    # calculate the cost of the entire upgrade, taking into account all the possible reductions
    final_costs = [0] * len(materials_names)
    construction_time = 0
    construction_times = []
    levels_to_upgrade = 0
    for match in matches:
        lv = re.search(r'"level">(\d+)</td>', match).group(1)
        lv = int(lv)

        if lv <= current_level:
            continue
        if lv > final_level:
            break

        levels_to_upgrade += 1
        level_time = _parseConstructionTime(match)
        if level_time is not None:
            # Keep full durations: optional speedups may be unavailable or rejected.
            construction_time += level_time
            construction_times.append(level_time)
        # get the costs for the current level
        costs = re.findall(r'<td class="costs"><div.*>([\d,\.\s\xa0]*)</div></div></td>', match)
        # delete blank spaces (\xa0) in costs
        costs = [value.replace('\xa0', '').replace(' ', '') for value in costs]

        for i in range(len(costs)):
            # get hash from CDN images to identify the resource type
            resource_type = checkhash("https:" + resources_types[i] + ".png")

            for j in range(len(materials_names_tec)):
                name = materials_names_tec[j]
                if resource_type == name:
                    resource_index = j
                    break

            # get the cost of the current resource type
            cost = costs[i]
            cost = cost.replace(",", "").replace(".", "")
            cost = 0 if cost == "" else int(cost)

            # calculate all the reductions
            investigation_multiplier = Decimal(str(costs_reduction))
            building_reduction = Decimal(costs_reductions[resource_index]) / Decimal(100)

            # Calculate the final multiplier
            final_multiplier = investigation_multiplier - building_reduction

            # Apply the direct proportion without trying to guess the hidden base cost
            real_cost = Decimal(cost) * (final_multiplier / investigation_multiplier)

            # Always round up to ensure we never fall short by 1 unit (prevents wasted transports or failed upgrades)
            final_costs[resource_index] += math.ceil(real_cost)


        if building["building"] == "carpentering":
            costs_reductions[0] = min(50, costs_reductions[0] + 1)
        elif building["building"] == "vineyard":
            costs_reductions[1] = min(50, costs_reductions[1] + 1)
        elif building["building"] == "architect":
            costs_reductions[2] = min(50, costs_reductions[2] + 1)
        elif building["building"] == "optician":
            costs_reductions[3] = min(50, costs_reductions[3] + 1)
        elif building["building"] == "fireworker":
            costs_reductions[4] = min(50, costs_reductions[4] + 1)

    if levels_to_upgrade < final_level - current_level:
        if noninteractive:
            raise ValueError("The target building level is not available in the game")
        print(
            "This building only allows you to expand {:d} more levels".format(
                levels_to_upgrade
            )
        )
        msg = "Expand {:d} levels? [Y/n]:".format(levels_to_upgrade)
        rta = read(msg=msg, values=["Y", "y", "N", "n", ""])
        if rta.lower() == "n":
            #Skip only this building
            return [-2, -2, -2, -2, -2]

    building["constructionTime"] = construction_time
    building["constructionTimes"] = construction_times
    return final_costs


def _round_up_resources(amount):
    if amount < 1000:
        return math.ceil(amount / 100) * 100
    elif amount < 10000:
        return math.ceil(amount / 500) * 500
    else:
        return math.ceil(amount / 1000) * 1000


def sendResourcesNeeded(session, destination_city_id, city_origins, missing_resources, useFreighters=False, useRounding=False):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    destination_city_id : int
    city_origins : dict
    missing_resources : dict[int, int]
    useFreighters : bool
    useRounding : bool
    """

    info = "\nTransport resources to upload building\n"

    try:
        html = session.get(city_url + destination_city_id)
        cityD = getCity(html)

        # build combined routes per origin city so multiple resources
        # from the same city are sent in a single shipment
        combined = {}  # origin_city_id -> (cityOrigin, toSend_list)

        for i in range(len(materials_names)):
            missing = missing_resources[i]
            if missing <= 0:
                continue

            target = _round_up_resources(missing) if useRounding else missing
            remaining = target

            for cityOrigin in (city_origins.get(i) or city_origins.get(str(i), [])):
                if remaining == 0:
                    break

                available = cityOrigin["availableResources"][i]
                send = min(available, remaining)
                remaining -= send

                city_id = cityOrigin["id"]
                if city_id not in combined:
                    combined[city_id] = (cityOrigin, [0] * len(materials_names))
                combined[city_id][1][i] += send

        routes = []
        for city_id, (cityOrigin, toSend) in combined.items():
            route = (cityOrigin, cityD, cityD["islandId"], *toSend)
            routes.append(route)

        executeRoutes(session, routes, useFreighters)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
        # no s.logout() because this is a thread, not a process


def chooseResourceProviders(session, cities_ids, cities, city_id, resource, missing):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cities_ids : list[int]
    cities : dict[int, dict]
    city_id : int
    resource : int
    missing : int
    """
    send_resources_flag = True
    expand_flag = True

    banner()
    print("From what cities obtain {}?".format(materials_names[resource].lower()))

    tradegood_initials = [material_name[0] for material_name in materials_names]
    maxName = max(
        [len(cities[city]["name"]) for city in cities if cities[city]["id"] != city_id]
    )

    origin_cities = []
    total_available = 0
    for cityId in cities_ids:
        if cityId == city_id:
            continue

        html = session.get(city_url + cityId)
        city = getCity(html)

        available = city["availableResources"][resource]
        if available == 0:
            continue

        # ask the user it this city should provide resources
        tradegood_initial = tradegood_initials[int(cities[cityId]["tradegood"])]
        pad = " " * (maxName - len(cities[cityId]["name"]))
        is_producer = (int(cities[cityId]["tradegood"]) == int(resource))
        msg = "{}{} ({}): {} [{}]:".format(
            pad,
            cities[cityId]["name"],
            tradegood_initial,
            addThousandSeparator(available),
            ("y/N", "Y/n")[is_producer == True]
        )
        choice = read(msg=msg, values=["Y", "y", "N", "n", ""], default=("N", "Y")[is_producer == True])
        if choice.lower() == "n":
            continue

        # if so, save the city and calculate the total amount resources to send
        total_available += available
        origin_cities.append(city)
        # if we have enough resources, return
        if total_available >= missing:
            return origin_cities, send_resources_flag, expand_flag

    # if we reach this part, there are not enough resources to expand the building
    print("\nThere are not enough resources.")

    if len(origin_cities) > 0:
        print("\nSend the resources anyway? [Y/n]")
        choice = read(values=["y", "Y", "n", "N", ""])
        if choice.lower() == "n":
            send_resources_flag = False

    print("\nTry to expand the building anyway? [y/N]")
    choice = read(values=["y", "Y", "n", "N", ""])
    if choice.lower() == "n" or choice == "":
        expand_flag = False

    return origin_cities, send_resources_flag, expand_flag


def sendResourcesMenu(session, city_id, missing):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int
    missing : list[int, int]
    """
    cities_ids, cities = getIdsOfCities(session)
    origins = {}
    
    send_resources_flag = True
    expand_flag = True
    
    # for each missing resource, choose providers
    for resource in range(len(missing)):
        if missing[resource] <= 0:
            continue

        origin_cities, current_send_resources, current_expand = chooseResourceProviders(
            session, cities_ids, cities, city_id, resource, missing[resource]
        )
        send_resources_flag = current_send_resources
        expand_flag = current_expand
        if send_resources_flag is False and expand_flag:
            print("\nThe building will be expanded if possible.")
            enter()
            return None, expand_flag
        elif send_resources_flag is False:
            return None, expand_flag
        origins[resource] = origin_cities

    if expand_flag:
        print("\nThe resources will be sent and the building will be expanded if possible.")
    else:
        print("\nThe resources will be sent.")

    enter()

    return origins, expand_flag


def getBuildingsToExpand(session, cityId):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int

    Returns
    -------
    buildings : list of dict
    """
    html = session.get(city_url + cityId)
    city = getCity(html)

    banner()
    # show the buildings available to expand (ignore empty spaces)
    print("Which buildings do you want to expand? Separate numbers with commas (7, 1, 3, 5, ...)\n")
    print("(0)\t\texit")
    buildings = [
        building for building in city["position"] if building["name"] != "empty"
    ]
    for i in range(len(buildings)):
        building = buildings[i]

        level = building["level"]

        if building["isMaxLevel"] is True:
            color = bcolors.BLACK
        elif building["canUpgrade"] is True:
            color = bcolors.GREEN
        else:
            color = bcolors.RED
        if level < 10:
            level = " " + str(level)
        else:
            level = str(level)
        if building["isBusy"]:
            level = level + "+"
        print("({:d})\tlv:{}\t{}{}{}".format(i + 1, level, color, building["name"], bcolors.ENDC))

    selected_building_ids = read().split(",")
    selected_building_ids = [int(id.strip()) for id in selected_building_ids if id.strip().isdigit()]

    if len(selected_building_ids) == 0 or 0 in selected_building_ids:
        return None

    selected_buildings = []
    for building_id in selected_building_ids:
        building = buildings[building_id - 1]

        current_level = int(building["level"])
        # if the building is being expanded, add 1 level
        if building["isBusy"]:
            current_level += 1

        banner()
        print("building:{}".format(building["name"]))
        print("current level:{}".format(current_level))

        final_level = read(min=current_level, msg="increase to level:")
        building["upgradeTo"] = final_level
        selected_buildings.append(building)

    return selected_buildings

@cache
def checkhash(url):
    m = hashlib.md5()
    r = requests.get(url)
    for data in r.iter_content(8192):
        m.update(data)
        if m.hexdigest() == config.material_img_hash[0]:
            material = "wood"
        elif m.hexdigest() == config.material_img_hash[1]:
            material = "wine"
        elif m.hexdigest() == config.material_img_hash[2]:
            material = "marble"
        elif m.hexdigest() == config.material_img_hash[3]:
            material = "glass"
        elif m.hexdigest() == config.material_img_hash[4]:
            material = "sulfur"
        else:
            continue
    return material


def preview_native_construction(session, city_id, upgrades, supply=None):
    """Read and prepare a city-specific construction queue without game mutations.

    Upgrade planning delegates actual resource and duration calculation to
    getResourcesNeeded (the same upstream routine as the original CLI).
    Optional owned-city supply uses exact reviewed cargo and the existing
    shipment engine. At dispatch, re-read building levels, costs and routes.
    """
    from ikabot.helpers.taskConfig import requireOwnCity

    if type(city_id) is not int or not 0 < city_id < 10**12:
        raise ValueError("Invalid construction city")
    if not isinstance(upgrades, list) or not 0 < len(upgrades) <= 12:
        raise ValueError("Choose 1 to 12 actual building upgrades")

    from ikabot.helpers import pedirInfo

    if supply is not None:
        pedirInfo.ids_cache = None
    owned = requireOwnCity(session, city_id, "city_id")
    city = getCity(session.get(city_url + str(owned)))
    if int(city["id"]) != city_id:
        raise ValueError("The game returned a different construction city")
    resources = city.get("availableResources")
    if (not isinstance(resources, list) or len(resources) != 5
            or any(type(v) is not int or v < 0 for v in resources)):
        raise ValueError("Current city resource amounts are unavailable")
    stock = list(resources)
    reductions = getCostsReducers(city)
    chosen = []
    seen = set()
    costs = [0] * 5
    for upgrade in upgrades:
        if not isinstance(upgrade, dict):
            raise ValueError("Expected a building target")
        slot = upgrade.get("position")
        target = upgrade.get("target_level")
        if (type(slot) is not int or not 0 <= slot <= 80 or slot in seen
                or type(target) is not int or not 0 < target <= 150):
            raise ValueError("Invalid or duplicate building upgrade target")
        seen.add(slot)
        building = next(
            (row for row in city["position"] if row.get("position") == slot
             and row.get("building") != "empty"), None
        )
        if building is None or building.get("isBusy") is True or building.get("isMaxLevel") is True:
            raise ValueError("Chosen building is absent, already upgrading, or fully upgraded")
        current = building.get("level")
        if (type(current) is not int or not current < target <= current + 10):
            raise ValueError("Choose a higher target level, up to ten levels per preview")
        candidate = dict(building)
        candidate["upgradeTo"] = target
        updated_reductions = list(reductions)
        needed = getResourcesNeeded(
            session, city, candidate, current, target,
            updated_reductions, noninteractive=True,
        )
        if (not isinstance(needed, list) or len(needed) != 5
                or any(type(value) is not int or value < 0 for value in needed)):
            raise ValueError("Could not determine authoritative building costs")
        durations = candidate.get("constructionTimes")
        if (not isinstance(durations, list) or len(durations) != target - current
                or any(type(duration) is not int or duration <= 0 for duration in durations)):
            raise ValueError("IkaBot cannot estimate all construction durations safely")
        for i in range(5):
            costs[i] += needed[i]
            stock[i] = max(0, stock[i] - needed[i])
        reductions = updated_reductions
        chosen.append({
            "position": slot, "name": str(building["name"])[:100],
            "building": str(building["building"])[:64],
            "level": current, "isBusy": False, "upgradeTo": target,
            "constructionTime": sum(durations),
            "constructionTimes": durations,
        })
    queue = [duration for building in chosen for duration in building["constructionTimes"]]
    total_seconds = sum(queue)
    active_time = int(city.get("endUpgradeTime") or 0) - int(time.time())
    total_seconds += max(0, active_time)
    missing = [max(0, costs[i] - resources[i]) for i in range(5)]
    config = {
        "city_id": city_id, "city_name": str(city["name"])[:100],
        "buildings": chosen, "shipments": [], "expand_overall": True,
        "wait_resources": False, "construction_queue": queue,
        "total_time": total_seconds,
    }
    result = {
        "config": config, "costs": costs, "available": list(resources),
        "missing": missing, "estimated_seconds": total_seconds,
        "ready": all(amount == 0 for amount in missing),
    }
    if supply is not None:
        result = _construction_supply(session, city, result, supply)
    return result


def _construction_supply(session, city, result, supply):
    from ikabot.helpers.taskConfig import getCityById, requireOwnCity
    from ikabot.function.sendResources import preview_native_shipments

    city_id = int(city["id"])
    if (not isinstance(supply, dict) or set(supply) != {"source_ids", "useFreighters", "round_up", "supply_only"}
            or any(type(supply[k]) is not bool for k in ("useFreighters", "round_up", "supply_only"))
            or not isinstance(supply["source_ids"], list) or not 1 <= len(supply["source_ids"]) <= 20
            or any(type(v) is not int or not 0 < v < 10**12 or v == city_id for v in supply["source_ids"])
            or len(set(supply["source_ids"])) != len(supply["source_ids"])):
        raise ValueError("Choose distinct owned construction suppliers")
    space = city.get("freeSpaceForResources")
    if not isinstance(space, list) or len(space) != 5 or any(type(v) is not int or not 0 <= v <= 10**15 for v in space):
        raise ValueError("Destination storage unavailable")
    missing = result["missing"]
    target = [min(space[i], _round_up_resources(n) if supply["round_up"] else n)
              for i, n in enumerate(missing)]
    remaining = target.copy()
    routes = []
    for source_id in supply["source_ids"]:
        source = getCityById(session, requireOwnCity(session, source_id, "supplier"))
        stock = source.get("availableResources")
        if (str(source.get("id")) != str(source_id) or not isinstance(stock, list)
                or len(stock) != 5 or any(type(v) is not int or not 0 <= v <= 10**15 for v in stock)):
            raise ValueError("Supplier inventory unavailable")
        cargo = [min(n, available, 10**9) for n, available in zip(remaining, stock)]
        remaining = [n - a for n, a in zip(remaining, cargo)]
        if any(cargo):
            routes.append({"from": source_id, "to": city_id, "resources": cargo})
    totals = [a-b for a,b in zip(target, remaining)]
    short = [max(0, a-b) for a,b in zip(missing, totals)]
    shipment = preview_native_shipments(session, routes, supply["useFreighters"]) if routes else None
    if shipment is not None and any(row["destination_space"] != space for row in shipment["routes"]):
        raise ValueError("Destination storage changed during supply review")
    ready = not any(short) and bool(shipment and shipment["ready"])
    # A supply-only task requires actual cargo; a no-shortage build can use
    # the existing self-funded workflow instead of a redundant supply review.
    result["ready"] = ready
    result["supply"] = {"options": supply, "target": target, "remaining": short,
                        "shipment": shipment, "destination_space": space}
    result["config"].update(shipments=routes, expand_overall=not supply["supply_only"],
                            wait_resources=not supply["supply_only"],
                            supply_review={"options": supply, "costs": result["costs"]})
    return result


def prepare_constructionList(session, city_id, city_name, buildings, shipments,
                             expand_overall, wait_resources, construction_queue, total_time, supply_review=None):
    """Independently recompute a UI-prepared plan immediately before task launch."""
    if (not isinstance(buildings, list) or not 0 < len(buildings) <= 12
            or not isinstance(shipments, list)
            or (supply_review is None and (shipments or expand_overall is not True or wait_resources is not False))):
        raise ValueError("Construction needs an engine-reviewed, self-funded plan")
    try:
        upgrades = [
            {"position": row["position"], "target_level": row["upgradeTo"]}
            for row in buildings
        ]
    except (TypeError, KeyError) as exc:
        raise ValueError("Invalid construction building records") from exc
    if supply_review is not None and (not isinstance(supply_review, dict)
                                      or set(supply_review) != {"options", "costs"}):
        raise ValueError("Invalid construction supply review")
    result = preview_native_construction(session, city_id, upgrades,
                                         supply_review["options"]) if supply_review is not None else preview_native_construction(session, city_id, upgrades)
    if not result["ready"]:
        raise ValueError("Construction resources changed; review the shortage and preview again")
    expected = result["config"]
    supplied = {
        "city_id": city_id, "city_name": city_name, "buildings": buildings,
        "shipments": shipments, "expand_overall": expand_overall,
        "wait_resources": wait_resources, "construction_queue": construction_queue,
    }
    if supply_review is not None:
        supplied["supply_review"] = supply_review
    check = {key: val for key, val in expected.items() if key != "total_time"}
    if supplied != check or type(total_time) is not int or abs(
        total_time - expected["total_time"]
    ) > 120:
        raise ValueError("Construction plan is stale or does not match verified game state")
    return expected


def _run_supplied_construction(session, config):
    """Never replay a supply dispatch. Wait for observed resources before building."""
    from ikabot.helpers import pedirInfo
    from ikabot.helpers.taskConfig import getCityById, requireOwnCity

    prepared = prepare_constructionList(session, **config)
    routes = prepared["shipments"]
    city_id = prepared["city_id"]
    target = getCityById(session, city_id)
    island = str(target["islandId"])
    shipments = []
    for route in routes:
        source = getCityById(session, route["from"])
        shipments.append(({"id": str(source["id"]), "name": str(source["name"])},
                          {"id": str(city_id), "name": prepared["city_name"]},
                          island, *route["resources"]))

    def verify_owned(index):
        pedirInfo.ids_cache = None
        requireOwnCity(session, city_id, "destination")
        requireOwnCity(session, routes[index]["from"], "supplier")
        observed = getCityById(session, city_id)
        if str(observed["id"]) != str(city_id) or str(observed["islandId"]) != island:
            raise ValueError("Construction destination changed")

    session.setStatus("Dispatching exact reviewed construction supply")
    executeRoutes(session, shipments, prepared["supply_review"]["options"]["useFreighters"],
                  verify_recipient=verify_owned)
    if not prepared["expand_overall"]:
        session.setStatus("Construction supply dispatched; verify arrivals")
        return
    # Do not infer arrival from dispatch acceptance. Observe sufficient
    # destination stock and unchanged targets/costs before any upgrade.
    upgrades = [{"position": b["position"], "target_level": b["upgradeTo"]} for b in prepared["buildings"]]
    deadline = time.monotonic() + 24 * 60 * 60
    while True:
        pedirInfo.ids_cache = None
        fresh = preview_native_construction(session, city_id, upgrades)
        if (fresh["config"]["buildings"] != prepared["buildings"]
                or fresh["costs"] != prepared["supply_review"]["costs"]):
            raise ValueError("Construction review changed after supply dispatch")
        if fresh["ready"]:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Supplied resources not observed within 24 hours; reconcile manually")
        session.setStatus("Waiting for reviewed construction supplies to arrive")
        wait(60)
    queue = list(prepared["construction_queue"])
    for building in prepared["buildings"]:
        expandBuilding(session, str(city_id), building, False, queue, reviewed=True)
        city = getCityById(session, city_id)
        observed = next((b for b in city["position"] if b["position"] == building["position"]), None)
        if (observed is None or observed.get("building") != building["building"]
                or observed.get("level") != building["upgradeTo"] or observed.get("isBusy") is True):
            raise ValueError("Construction result not verified; stop remaining upgrades")


@task("constructionList", prepare=prepare_constructionList)
def do_it(session, city_id, city_name, buildings, shipments, expand_overall, wait_resources,
          construction_queue, total_time, supply_review: dict = None):
    if supply_review is not None:
        _run_supplied_construction(session, {"city_id": city_id, "city_name": city_name,
            "buildings": buildings, "shipments": shipments, "expand_overall": expand_overall,
            "wait_resources": wait_resources, "construction_queue": construction_queue,
            "total_time": total_time, "supply_review": supply_review})
        return
    session.setStatus(
        "{}: queued {} upgrades | total {}".format(
            city_name, len(construction_queue), _formatRemainingTime(total_time)
        )
    )
    info = "\nUpgrade building\n"
    building_log_name = buildings[0]["name"] if len(buildings) == 1 else "Multiple buildings"
    info = info + "City: {}\nBuilding: {}".format(city_name, building_log_name)
    setInfoSignal(session, info)
    
    threads = []
    for shipment in shipments:
        t = threading.Thread(
            target=sendResourcesNeeded,
            args=(
                session,
                city_id,
                shipment["origins"],
                shipment["missing"],
                shipment["useFreighters"],
                shipment["useRounding"],
            ),
        )
        t.start()
        threads.append(t)

    try:
        if expand_overall:
            for building in buildings:
                expandBuilding(
                    session, city_id, building, wait_resources, construction_queue
                )
        else:
            for t in threads:
                t.join()
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)


@configurator
def constructionList(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    wait_resources = False
    print("In which city do you want to expand buildings?")
    city = chooseCity(session)
    cityId = city["id"]
    buildings = getBuildingsToExpand(session, cityId)
    if buildings is None or len(buildings) == 0:
        return None

    #simulated resources
    simulated_resources = list(city["availableResources"])
    simulated_reducers = getCostsReducers(city)

    for b in city["position"]:
        if b["name"] != "empty" and b.get("isBusy", False):
            if b["building"] == "carpentering":
                simulated_reducers[0] = min(50, simulated_reducers[0] + 1)
            elif b["building"] == "vineyard":
                simulated_reducers[1] = min(50, simulated_reducers[1] + 1)
            elif b["building"] == "architect":
                simulated_reducers[2] = min(50, simulated_reducers[2] + 1)
            elif b["building"] == "optician":
                simulated_reducers[3] = min(50, simulated_reducers[3] + 1)
            elif b["building"] == "fireworker":
                simulated_reducers[4] = min(50, simulated_reducers[4] + 1)

    # NewList - Only Accepted
    confirmed_buildings = []
    shipments = []
    expand_overall = True

    # Sequentially upgrade each building
    for building in buildings:
        current_level = building["level"]
        if building["isBusy"]:
            current_level += 1
        final_level = building["upgradeTo"]

        current_reducers = list(simulated_reducers)

        # calculate the resources that are needed
        resourcesNeeded = getResourcesNeeded(
            session, city, building, current_level, final_level, current_reducers
        )

        if -2 in resourcesNeeded:
            print(f"\nSkipping {building['name']}.\n")
            continue

        if -1 in resourcesNeeded:
            return None

        missing = [0] * len(materials_names)
        for i in range(len(materials_names)):
            if simulated_resources[i] < resourcesNeeded[i]:
                missing[i] = resourcesNeeded[i] - simulated_resources[i]

        # show missing resources to the user
        if sum(missing) > 0:
            print("\nMaterials needed for {} (lv {:d} -> {:d}):".format(building["name"], current_level, final_level))
            for i, name in enumerate(materials_names):
                amount = resourcesNeeded[i]
                if amount == 0:
                    continue
                print("- {}: {}".format(name, addThousandSeparator(max(0, amount))))
            print("")

            print("Missing:")
            for i in range(len(materials_names)):
                if missing[i] <= 0:
                    continue
                name = materials_names[i].lower()
                print("{} of {}".format(addThousandSeparator(missing[i]), name))
            print("")

            # if the user wants, send the resources from the selected cities
            print("Automatically transport resources? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                print("Proceed anyway? [Y/n]")
                rta = read(values=["y", "Y", "n", "N", ""])
                if rta.lower() == "n":
                    print(f"\nSkipping {building['name']} due to user cancellation.\n")
                    continue  # If it cancels, we skip it and it is NOT added to confirm_buildings
            else:
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
                print("Round up transport amounts? [Y/n]")
                print("(amounts will be rounded up but capped at what each city can provide)")
                rta_round = read(values=["y", "Y", "n", "N", ""])
                useRounding = rta_round.lower() != "n"
                wait_resources = True
                origins, current_expand = sendResourcesMenu(session, cityId, missing)
                
                if not current_expand:
                    expand_overall = False
                
                if origins:
                    shipments.append({
                        "origins": origins,
                        "missing": missing,
                        "useFreighters": useFreighters,
                        "useRounding": useRounding
                    })
        else:
            print("\nMaterials needed for {} (lv {:d} -> {:d}):".format(building["name"], current_level, final_level))
            for i, name in enumerate(materials_names):
                amount = resourcesNeeded[i]
                if amount == 0:
                    continue
                print("- {}: {}".format(name, addThousandSeparator(max(0, amount))))
            print("")

            print("You have enough materials")
            print("Proceed? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                print(f"\nSkipping {building['name']} due to user cancellation.\n")
                continue  # If it cancels, we skip it and it is NOT added to confirm_buildings

        # Save the approved building and deduct it from the simulator
        confirmed_buildings.append(building)
        simulated_reducers = current_reducers

        for i in range(len(materials_names)):
            if simulated_resources[i] < resourcesNeeded[i]:
                simulated_resources[i] = 0
            else:
                simulated_resources[i] -= resourcesNeeded[i]

    # Replace list
    buildings = confirmed_buildings

    total_time = sum(building["constructionTime"] for building in buildings)
    active_time = int(city.get("endUpgradeTime", 0)) - int(time.time())
    total_time += max(0, active_time)
    construction_queue = [
        duration
        for building in buildings
        for duration in building["constructionTimes"]
    ]
    if buildings:
        print("\nTotal construction time: {}".format(daysHoursMinutes(total_time)))

    if (not buildings or len(buildings) == 0) and len(shipments) == 0:
        return None

    return {
        "session": session,
        "city_id": cityId,
        "city_name": city["cityName"],
        "buildings": buildings,
        "shipments": shipments,
        "expand_overall": expand_overall,
        "wait_resources": wait_resources,
        "construction_queue": construction_queue,
        "total_time": total_time,
    }
