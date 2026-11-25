from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import wait

WORKER_TASK_KINDS = {
    "modifyProduction": ("resource", "tradegood"),
    "modifyAcademyWorkers": ("academy",),
    "modifyTempleWorkers": ("temple",),
}


def _read_worker_slider(session, city, kind):
    """Use the same game views as the original interactive configurators."""
    city_id = str(city["id"])
    island_id = str(city["islandId"])
    position = None
    if kind in ("resource", "tradegood"):
        url = (f"view={kind}&type={kind}&islandId={island_id}&cityId={city_id}"
               f"&backgroundView=island&currentIslandId={island_id}"
               f"&actionRequest={actionRequest}&ajax=1")
        key = "js_ResourceSlider"
    else:
        slot = next((slot for slot in city["position"] if slot.get("building") == kind), None)
        if slot is None:
            raise ValueError("This city does not have the requested building")
        position = int(slot["position"])
        url = (f"view={kind}&cityId={city_id}&position={position}&backgroundView=city"
               f"&currentCityId={city_id}&actionRequest={actionRequest}&ajax=1")
        key = "js_AcademySlider" if kind == "academy" else "js_TempleSlider"
    response = json.loads(session.post(url), strict=False)
    return response[2][1][key]["slider"], position


def _submit_worker_assignment(session, city_id, island_id, kind, position, target, *, reviewed=False):
    """Shared original IkaBot mutation, no transport replay for reviewed plans."""
    if kind in ("resource", "tradegood"):
        worker_key = "rw" if kind == "resource" else "tw"
        params = {
            "islandId": island_id, "cityId": city_id, "type": kind, "screen": kind,
            "action": "IslandScreen", "function": "workerPlan",
            worker_key: target, "templateView": kind,
            "actionRequest": actionRequest, "ajax": "1",
        }
    elif kind == "academy":
        params = {
            "action": "IslandScreen", "function": "workerPlan",
            "screen": "academy", "position": position, "cityId": city_id,
            "s": target, "backgroundView": "city", "currentCityId": city_id,
            "templateView": "academy", "actionRequest": actionRequest, "ajax": "1",
        }
    elif kind == "temple":
        params = {
            "action": "CityScreen", "function": "assignPriests", "cityId": city_id,
            "position": position, "priests": target, "backgroundView": "city",
            "currentCityId": city_id, "templateView": "temple",
            "actionRequest": actionRequest, "ajax": "1",
        }
    else:
        raise ValueError("Unknown worker assignment")
    if reviewed:
        return session.post(params=params, retry_on_failure=False)
    return session.post(params=params)


def preview_native_workers(session, task_name, city_id, percentage, project=None, overcharge=False):
    """One owned city and one actual game worker slider; no allocation is made."""
    kinds = WORKER_TASK_KINDS.get(task_name)
    if (kinds is None or type(city_id) is not int or not 0 < city_id < 10**12
            or type(percentage) is not int or not 0 <= percentage <= 100
            or type(overcharge) is not bool):
        raise ValueError("Invalid worker settings")
    production = task_name == "modifyProduction"
    if production:
        if project not in kinds or (overcharge and percentage != 100):
            raise ValueError("Invalid production project or overcharge")
        kind = project
    else:
        if project is not None or overcharge:
            raise ValueError("Unexpected production settings")
        kind = kinds[0]
    pedirInfo.ids_cache = None
    own_id = requireOwnCity(session, city_id, "Worker city")
    city = getCityById(session, own_id)
    if str(city["id"]) != own_id:
        raise ValueError("Worker city mismatch")
    island_id = int(city["islandId"])
    if not 0 < island_id < 10**12:
        raise ValueError("Invalid worker island")
    slider, position = _read_worker_slider(session, city, kind)
    maximum = slider["max_value"]
    extra = slider["overcharge"] if production else 0
    if (type(maximum) is not int or not 0 <= maximum <= 10**6
            or type(extra) is not int or not 0 <= extra <= 10**6
            or (position is not None and not 0 <= position <= 80)):
        raise ValueError("Invalid worker capacity")
    # The upstream module only establishes max_value/overcharge. A current
    # count is optional and must never be inferred from a capacity.
    current = slider.get("value")
    if type(current) is not int or not 0 <= current <= 2*10**6:
        current = None
    target = maximum * percentage // 100 + (extra if overcharge else 0)
    expected = {"island_id": island_id, "position": position, "maximum": maximum,
                "extra": extra, "current": current, "target": target}
    config = {"city_id": city_id, "percentage": percentage, "expected": expected}
    if production:
        config.update(project=kind, overcharge=overcharge)
    return {
        "task": task_name, "city_id": city_id,
        "city_name": str(city.get("cityName") or city.get("name") or "")[:100],
        "percentage": percentage, "project": project, "overcharge": overcharge,
        "maximum": maximum, "extra": extra, "current": current, "target": target,
        "ready": True, "config": config,
    }


def prepare_native_workers(session, task_name, city_id, percentage, expected, project=None, overcharge=False):
    plan = preview_native_workers(session, task_name, city_id, percentage, project, overcharge)
    if not isinstance(expected, dict) or expected != plan["config"]["expected"]:
        raise ValueError("Worker review is stale")
    # Equality alone must not accept bool in place of an integer.
    for key, value in plan["config"]["expected"].items():
        if type(expected[key]) is not type(value):
            raise ValueError("Invalid reviewed worker plan")
    return plan["config"]


def execute_native_workers(session, task_name, city_id, percentage, expected, project=None, overcharge=False):
    config = prepare_native_workers(session, task_name, city_id, percentage, expected, project, overcharge)
    reviewed = config["expected"]
    kind = project if task_name == "modifyProduction" else WORKER_TASK_KINDS[task_name][0]
    session.setStatus("Submitting reviewed worker assignment")
    _submit_worker_assignment(session, str(city_id), str(reviewed["island_id"]), kind,
                              reviewed["position"], reviewed["target"], reviewed=True)
    session.setStatus("Worker assignment submitted; verify the city")


def prepare_modify_production(session, city_id, percentage, project, overcharge, expected):
    return prepare_native_workers(session, "modifyProduction", city_id, percentage, expected, project, overcharge)


@task("modifyProduction", prepare=prepare_modify_production)
def native_modify_production(session, city_id: int, percentage: int, project: str,
                             overcharge: bool, expected: dict):
    execute_native_workers(session, "modifyProduction", city_id, percentage, expected, project, overcharge)


@configurator
def modifyProduction(session, event, stdin_fd, predetermined_input):
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
        mod_msg = "In which cities do you want to modify production?"
        city_ids, _ = ignoreCities(session, msg=mod_msg)
        
        cities_to_process = {}
        
        for city_id in city_ids:
            html = session.get(city_url + city_id)
            city = getCity(html)
            if city['islandId'] not in cities_to_process:
                cities_to_process[city['islandId']] = {'island': getIsland(session.get(island_url + city['islandId'])), 'cities': []}
            cities_to_process[city['islandId']]['cities'].append(city)

        print("You want to modify the number of workers in Wood (1), Tradegood (2) or Both (3)?")
        res_choice = read(min=1, max=3)
        resource_types_to_modify = []
        if res_choice == 1:
            resource_types_to_modify.append("resource")
        elif res_choice == 2:
            resource_types_to_modify.append("tradegood")
        elif res_choice == 3:
            resource_types_to_modify.extend(["resource", "tradegood"])

        print("What % of production do you want to use? (Default 100%)")
        percentageWorkers = read(min=0, max=100, default=100)
        if percentageWorkers == 100:
            print("Would you like to use overcharge? (y/N)")
            overcharge = read(values=["y", "Y", "n", "N", ""])
            use_overcharge = overcharge.lower() == "y"
        else:
            use_overcharge = False
            
        banner()
        # loop through each selected city
        current_city_id_for_request = getCity(session.get())['id']
        # Loop through islands first
        for islandId, island_data in cities_to_process.items():
            island = island_data['island']
            resource_name = tradegoods_names[0]
            tradegood_name = tradegoods_names[int(island["tipo"])]
            #print(f"DEBUG: Visited island {islandId}")

            # Then loop through cities on that island
            for city in island_data['cities']:
                # Change the session context to the current city
                session.post(params={
                    'action': 'header', 'function': 'changeCurrentCity',
                    'actionRequest': actionRequest, 'cityId': city['id'],
                    'oldView': 'city', 'backgroundView': 'city',
                    'currentCityId': current_city_id_for_request, 'ajax': '1'
                })
                # Update the current city ID for the next request
                current_city_id_for_request = city['id']
                #print(f"DEBUG: session.post was made, current city is {city['id']} and island is {islandId}")

                # Loop through only the resource types the user chose to modify
                for resource_type in resource_types_to_modify:
                    # Fetch data, calculate, and set workers in one sequence
                    
                    # Fetch data for the current resource type
                    url = f"view={resource_type}&type={resource_type}&islandId={islandId}&cityId={city['id']}&backgroundView=island&currentIslandId={islandId}&actionRequest={actionRequest}&ajax=1"
                    resp = session.post(url)
                    resp_json = json.loads(resp, strict=False)
                    
                    template_data = resp_json[2][1]
                    slider_data = template_data['js_ResourceSlider']['slider']
                    max_normal = slider_data['max_value']
                    total_max = slider_data['max_value'] + slider_data['overcharge']
                    #print(f"DEBUG: session.post was made, current city is {city['id']}, current island is {islandId}\nresource type is {resource_type}, max_normal is {max_normal} and total_max is {total_max}")
                    
                    # Calculate finalWorkers using the data we just fetched
                    if percentageWorkers == 100:
                        finalWorkers = total_max if use_overcharge else max_normal
                    else:
                        finalWorkers = int(max_normal / 100 * percentageWorkers)
                    
                    # Set the workers
                    _submit_worker_assignment(session, city["id"], islandId,
                                              resource_type, None, finalWorkers)

                    selected_good_name = resource_name if resource_type == "resource" else tradegood_name
                    print(f"{finalWorkers} workers set for {selected_good_name} in {city['name']}.")

                    # Ikariam silently ignores a workerPlan request that arrives too soon
                    # after another one on the same island, so space out resource/tradegood.
                    if resource_type != resource_types_to_modify[-1]:
                        wait(2, 2)

                wait(3, 4)

        print("\nAll productions have been set!")
        enter()
        
                
    except KeyboardInterrupt:
        return
    
    event.set()


@configurator
def modifyAcademyWorkers(session, event, stdin_fd, predetermined_input):
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
        city_ids, _ = ignoreCities(session, msg="In which cities do you want to set academy workers?")

        print("What % of scientists do you want to use? (Default 100%)")
        percentageWorkers = read(min=0, max=100, default=100)

        banner()
        for city_id in city_ids:
            html = session.get(city_url + city_id)
            city = getCity(html)

            academy_slot = next(
                (slot for slot in city['position'] if slot.get('building') == 'academy'),
                None
            )
            if academy_slot is None:
                print(f"No academy in {city['name']}, skipping.")
                continue

            position = academy_slot['position']
            url = f"view=academy&cityId={city['id']}&position={position}&backgroundView=city&currentCityId={city['id']}&actionRequest={actionRequest}&ajax=1"
            resp = session.post(url)
            resp_json = json.loads(resp, strict=False)
            max_scientists = resp_json[2][1]['js_AcademySlider']['slider']['max_value']

            if percentageWorkers == 100:
                finalScientists = max_scientists
            else:
                finalScientists = int(max_scientists / 100 * percentageWorkers)

            _submit_worker_assignment(session, city["id"], city["islandId"],
                                      "academy", position, finalScientists)
            print(f"{finalScientists} scientists set for Academy in {city['name']}.")

            wait(3, 4)

        print("\nAll academies have been set!")
        enter()
        
    except KeyboardInterrupt:
        return
    event.set()


@configurator
def modifyTempleWorkers(session, event, stdin_fd, predetermined_input):
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
        city_ids, _ = ignoreCities(session, msg="In which cities do you want to set priests?")

        print("What % of priests do you want to use? (Default 100%)")
        percentageWorkers = read(min=0, max=100, default=100)

        banner()
        for city_id in city_ids:
            html = session.get(city_url + city_id)
            city = getCity(html)

            temple_slot = next(
                (slot for slot in city['position'] if slot.get('building') == 'temple'),
                None
            )
            if temple_slot is None:
                print(f"No temple in {city['name']}, skipping.")
                continue

            position = temple_slot['position']
            url = f"view=temple&cityId={city['id']}&position={position}&backgroundView=city&currentCityId={city['id']}&actionRequest={actionRequest}&ajax=1"
            resp = session.post(url)
            resp_json = json.loads(resp, strict=False)
            max_priests = resp_json[2][1]['js_TempleSlider']['slider']['max_value']

            if percentageWorkers == 100:
                finalPriests = max_priests
            else:
                finalPriests = int(max_priests / 100 * percentageWorkers)

            _submit_worker_assignment(session, city["id"], city["islandId"],
                                      "temple", position, finalPriests)
            print(f"{finalPriests} priests set for Temple in {city['name']}.")

            wait(3, 4)

        print("\nAll temples have been set!")
        enter()

    except KeyboardInterrupt:
        return
    event.set()
