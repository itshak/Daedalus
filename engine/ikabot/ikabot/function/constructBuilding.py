from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
import hashlib
#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import json
import re

from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addThousandSeparator


def parseBuildingCosts(html_block):
    costs = [0] * len(materials_names)
    resource_map = {
        "wood": 0,
        "wine": 1,
        "marble": 2,
        "crystal": 3,
        "glass": 3,
        "sulfur": 4,
    }
    matches = re.findall(
        r'<li\s+class="(\w+)[^"]*"[^>]*\s+title="[^"]*?:\s*([\d\s\xa0\.]+)"', html_block
    )
    for res_type, amount_str in matches:
        if res_type not in resource_map:
            continue
        idx = resource_map[res_type]
        amount_str = amount_str.replace("\xa0", "").replace(" ", "").replace(".", "")
        try:
            costs[idx] = int(amount_str)
        except ValueError:
            pass
    return costs


def splitBuildingBlocks(html):
    blocks = []
    pattern = r'<li class="building (\w+)[^"]*">((?:(?!<li class="building ).)+)</li>'
    for match in re.finditer(pattern, html, re.DOTALL):
        blocks.append({"type": match.group(1), "html": match.group(2)})
    return blocks


def _building_ground(session, city_id, position):
    """Original upstream read of building options for a slot."""
    return json.loads(session.post(params={
        "view": "buildingGround", "cityId": city_id, "position": position,
        "backgroundView": "city", "currentCityId": city_id,
        "actionRequest": actionRequest, "ajax": "1",
    }, noIndex=True), strict=False)


def _native_build_options(session, city_id, only_position=None):
    """Read the actual building-ground view for each eligible empty slot."""
    if type(city_id) is not int or not 0 < city_id < 10**12:
        raise ValueError("Invalid city")
    pedirInfo.ids_cache = None
    own = requireOwnCity(session, city_id, "Construction city")
    city = getCityById(session, own)
    if str(city["id"]) != own:
        raise ValueError("City identity changed")
    stock = city["availableResources"]
    if not isinstance(stock, list) or len(stock) != 5 or any(
            type(n) is not int or not 0 <= n <= 10**15 for n in stock):
        raise ValueError("Invalid construction stock")
    slots = city["position"]
    if not isinstance(slots, list) or len(slots) > 81:
        raise ValueError("Invalid city slots")
    busy = any(row.get("isBusy") is True for row in slots)
    options = []
    action_token = actionRequest
    for slot in slots:
        position = slot.get("position")
        surface = slot.get("type")
        if (slot.get("building") != "empty" or type(position) is not int
                or not 0 <= position <= 80 or surface not in ("sea", "land", "shore", "wall", "dockyard")
                or (only_position is not None and position != only_position)):
            continue
        response = _building_ground(session, own, position)
        for item in response:
            if item[0] == "updateGlobalData":
                action_token = item[1].get("actionRequest", actionRequest)
        if response[1][1] == "":
            continue
        markup = response[1][1][1]
        seen = set()
        for block in splitBuildingBlocks(markup):
            info = re.search(
                r'<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&',
                block["html"],
            )
            if not info:
                continue
            building_id = int(info.group(2))
            if not 0 < building_id < 10**6 or building_id in seen:
                continue
            seen.add(building_id)
            costs = parseBuildingCosts(block["html"])
            # Do not present an unparsed price as free construction.
            if len(costs) != 5 or not any(costs) or any(type(n) is not int or not 0 <= n <= 10**12 for n in costs):
                continue
            name = info.group(1)[:100]
            options.append({"position": position, "surface": surface, "building_id": building_id,
                            "name": name, "costs": costs,
                            "ready": not busy and all(a >= b for a, b in zip(stock, costs))})
            if len(options) > 500:
                raise ValueError("Too many building options")
    return {"city_id": city_id, "city_name": str(city["cityName"])[:100],
            "available": stock, "busy": busy, "options": options}, action_token


def native_build_options(session, city_id):
    return _native_build_options(session, city_id)[0]


def _native_build_plan(session, city_id, position, building_id):
    if type(position) is not int or not 0 <= position <= 80 or type(building_id) is not int or not 0 < building_id < 10**6:
        raise ValueError("Invalid building choice")
    data, action_token = _native_build_options(session, city_id, position)
    option = next((row for row in data["options"] if row["position"] == position and row["building_id"] == building_id), None)
    if option is None:
        raise ValueError("Building no longer available in the selected slot")
    expected = hashlib.sha256(json.dumps(
        {k: option[k] for k in ("position", "surface", "building_id", "costs")},
        sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {"city_id": city_id, "city_name": data["city_name"], "available": data["available"],
            "busy": data["busy"], **option,
            "missing": [max(0, n - a) for n, a in zip(option["costs"], data["available"])],
            "config": {"city_id": city_id, "position": position, "building_id": building_id,
                       "expected": expected}}, action_token


def preview_native_build(session, city_id, position, building_id):
    return _native_build_plan(session, city_id, position, building_id)[0]


def prepare_native_build(session, city_id, position, building_id, expected):
    plan = preview_native_build(session, city_id, position, building_id)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Building review is stale or unaffordable")
    return plan["config"]


def _submit_building(session, city_id, position, building_id, action_token, *, reviewed=False):
    """Single upstream building request shared by CLI and reviewed plans."""
    params = {
        "action": "BuildNewBuilding",
        "cityId": city_id,
        "position": position,
        "building": building_id,
        "backgroundView": "city",
        "currentCityId": city_id,
        "templateView": "buildingGround",
        "actionRequest": action_token,
        "ajax": "1",
    }
    if reviewed:
        return session.post(params=params, noIndex=True, retry_on_failure=False)
    return session.post(params=params, noIndex=True)


@task("constructBuilding", prepare=prepare_native_build)
def native_build(session, city_id: int, position: int, building_id: int, expected: str):
    plan, action_token = _native_build_plan(session, city_id, position, building_id)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Building review is stale or unaffordable")
    city = str(city_id)
    session.setStatus("Submitting reviewed building construction")
    _submit_building(session, city, position, str(building_id), action_token, reviewed=True)
    session.setStatus("Construction submitted; verify the city")


@configurator
def constructBuilding(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        banner()

        print("City where to build:")
        city = chooseCity(session)
        banner()

        # list of free spaces in the selected city
        free_spaces = [
            buildings
            for buildings in city["position"]
            if buildings["building"] == "empty"
        ]

        # get a list of all the posible buildings that can be built
        buildings = []
        seen_ids = set()
        # different buildings can be built in different areas
        current_action_request = actionRequest
        type_spaces = ["sea", "land", "shore", "wall", "dockyard"]
        for type_space in type_spaces:
            free_spaces_of_type = [
                free_space
                for free_space in free_spaces
                if free_space["type"] == type_space
            ]
            # Iterate through available slots for this surface type until an active/unlocked slot is found.
            # Slots like position 13 require specific research (e.g., Bureaucracy) and will return empty HTML if locked.
            for free_space_of_type in free_spaces_of_type:
                parsed_response = _building_ground(session, city["id"], free_space_of_type["position"])

                # Extract fresh actionRequest from the response
                try:
                    update_global = [item for item in parsed_response if item[0] == 'updateGlobalData']
                    if update_global:
                        current_action_request = update_global[0][1].get('actionRequest', actionRequest)
                    else:
                        current_action_request = actionRequest
                except Exception:
                    current_action_request = actionRequest
                
                buildings_response = parsed_response[1][1]
                if buildings_response == "":
                    continue
                
                html = buildings_response[1]
                blocks = splitBuildingBlocks(html)
                # Skip slot if the server returned empty content (e.g., locked slot or special restriction)
                if len(blocks) == 0:
                    continue

                for block in blocks:
                    btype = block["type"]
                    block_html = block["html"]
                    info_match = re.search(
                        r'<div title="(.+?)"\s*class="buildingimg .+?"\s*onclick="ajaxHandlerCall\(\'.*?buildingId=(\d+)&',
                        block_html,
                    )
                    if not info_match:
                        continue
                    
                    building_id = info_match.group(2)
                    building_name = info_match.group(1)
                    
                    if building_id in seen_ids:
                        continue
                    
                    seen_ids.add(building_id)
                    costs = parseBuildingCosts(block_html)
                    can_afford = all(
                        costs[i] <= city["availableResources"][i]
                        for i in range(len(materials_names))
                    )
                    
                    buildings.append(
                        {
                            "building": btype,
                            "name": building_name,
                            "buildingId": building_id,
                            "type": type_space,
                            "costs": costs,
                            "canAfford": can_afford,
                        }
                    )
                # Stop checking remaining slots of this surface type once build options are retrieved
                if len(blocks) > 0:
                    break

        if len(buildings) == 0:
            print("No building can be built.")
            enter()
            event.set()
            return

        # show list of buildings to the user with color coding
        while True:
            banner()
            print("What building do you want to build?\n")
            i = 0
            for building in buildings:
                i += 1
                color = bcolors.GREEN if building["canAfford"] else bcolors.RED
                print(
                    "({:d}) {}{}{}".format(
                        i, color, building["name"], bcolors.ENDC
                    )
                )
            print(
                "\n{}Green{} = can afford | {}Red{} = insufficient resources | (0) Exit".format(
                    bcolors.GREEN, bcolors.ENDC, bcolors.RED, bcolors.ENDC
                )
            )
            selected_building_index = read(min=0, max=i)
            if selected_building_index == 0:
                event.set()
                return
            selected_building = buildings[selected_building_index - 1]

            if not selected_building["canAfford"]:
                banner()
                print("{}Insufficient resources to build: {}{}".format(bcolors.RED, selected_building["name"], bcolors.ENDC))
                print("\nMissing resources:")
                any_missing = False
                for idx, cost in enumerate(selected_building["costs"]):
                    if cost == 0:
                        continue
                    have = city["availableResources"][idx]
                    if have >= cost:
                        continue
                    missing = cost - have
                    any_missing = True
                    print(
                        "- {}{}: {} {}(have: {}){}".format(
                            materials_names[idx],
                            bcolors.RED,
                            addThousandSeparator(missing),
                            bcolors.STONE,
                            addThousandSeparator(have),
                            bcolors.ENDC,
                        )
                    )
                if not any_missing:
                    print("You have enough resources for this building.")
                print("\nPress Enter to return to the menu...")
                enter()
                continue
            else:
                break
        building = selected_building
        banner()
        print("{}\n".format(building["name"]))
        options = [
            position_id
            for position_id in city["position"]
            if position_id["building"] == "empty"
            and position_id["type"] == building["type"]
        ]
        if len(options) == 1:
            option = options[0]
        else:
            print("In which position do you want to build?\n")
            i = 0
            for option in options:
                i += 1
                print("({:d}) {}".format(i, option["position"]))
            selected_building_index = read(min=1, max=i)
            option = options[selected_building_index - 1]
            banner()

        # build it
        buildings_response = _submit_building(
            session, city["id"], option["position"], building["buildingId"], current_action_request)
        response_data = json.loads(buildings_response, strict=False)
        msg = None
        for item in response_data:
            if item[0] == 'provideFeedback':
                for feedback in item[1]:
                    if feedback.get('text'):
                        msg = feedback['text']
                        break
                if msg:
                    break
        if not msg:
            msg = "Building process completed."
        print(msg)
        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
