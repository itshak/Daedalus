from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re

from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.resources import *
from ikabot.helpers.varios import *


def _submit_donation(session, island_id, project, amount, *, city_id=None, reviewed=False):
    """Shared upstream donation action, with no ambiguous transport retry for native plans."""
    params = {
        "islandId": island_id,
        "type": project,
        "action": "IslandScreen",
        "function": "donate",
        "donation": amount,
        "backgroundView": "island",
        "templateView": "resource",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    if reviewed:
        params["cityId"] = city_id
        return session.post(params=params, retry_on_failure=False)
    return session.post(params=params)


def preview_native_donation(session, city_id, project, amount):
    """Read only the chosen owned city and its actual island project."""
    if (type(city_id) is not int or not 0 < city_id < 10**12
            or project not in ("resource", "tradegood")
            or type(amount) is not int or not 1 <= amount <= 10**9):
        raise ValueError("Invalid donation settings")
    pedirInfo.ids_cache = None
    owned = requireOwnCity(session, city_id, "Donation city")
    city = getCityById(session, owned)
    if str(city["id"]) != owned:
        raise ValueError("Donation city mismatch")
    island_id = str(city["islandId"])
    if not island_id.isdigit() or int(island_id) <= 0:
        raise ValueError("Invalid island")
    island = getIsland(session.get(island_url + island_id))
    resource = int(island["tipo"])
    if not 1 <= resource <= 4:
        raise ValueError("Invalid island resource")
    url = ("view={}&type={}&islandId={}&cityId={}&backgroundView=island"
           "&currentIslandId={}&actionRequest={}&ajax=1").format(
               project, "resource" if project == "resource" else resource,
               island_id, owned, island_id, actionRequest)
    response = json.loads(session.post(url), strict=False)
    background = response[0][1]["backgroundData"]
    level = int(background[project + "Level"])
    upgrading = int(background[project + "EndUpgradeTime"]) > 0
    amounts = re.findall(r'<li class="wood">(.*?)</li>', response[1][1][1])
    if len(amounts) not in (2, 3):
        raise ValueError("Project contribution data unavailable")
    required, donated = [int(re.sub(r"[^0-9]", "", value)) for value in amounts[:2]]
    stock = int(city["availableResources"][0])
    if not (0 <= stock <= 10**15 and 0 <= donated <= required <= 10**15
            and 0 <= level <= 150):
        raise ValueError("Invalid project data")
    remaining = required - donated
    return {
        "city_id": city_id,
        "city_name": str(city.get("name") or city.get("cityName") or "")[:100],
        "project": project,
        "project_name": str(tradegoods_names[0 if project == "resource" else resource])[:100],
        "level": level, "upgrading": upgrading, "stock": stock,
        "required": required, "donated": donated, "remaining": remaining,
        "amount": amount,
        "ready": not upgrading and amount <= min(stock, remaining),
        "config": {"city_id": city_id, "project": project, "amount": amount,
                   "expected_island": int(island_id), "expected_level": level,
                   "expected_donated": donated, "expected_required": required},
    }


def prepare_donate(session, city_id, project, amount, expected_island,
                   expected_level, expected_donated, expected_required):
    """Reject a stale or unaffordable one-shot plan before issuing a mutation."""
    expected = {
        "city_id": city_id, "project": project, "amount": amount,
        "expected_island": expected_island, "expected_level": expected_level,
        "expected_donated": expected_donated, "expected_required": expected_required,
    }
    if any(type(expected[key]) is not int for key in (
            "expected_island", "expected_level", "expected_donated", "expected_required")):
        raise ValueError("Invalid reviewed donation plan")
    plan = preview_native_donation(session, city_id, project, amount)
    if not plan["ready"] or plan["config"] != expected:
        raise ValueError("Donation review is stale or insufficient")
    return plan["config"]


@task("donate", prepare=prepare_donate)
def execute_native_donation(session, city_id: int, project: str, amount: int,
                            expected_island: int, expected_level: int,
                            expected_donated: int, expected_required: int):
    # Recheck again in the child immediately before the single upstream mutation.
    prepare_donate(session, city_id, project, amount, expected_island,
                   expected_level, expected_donated, expected_required)
    session.setStatus("Submitting reviewed island donation")
    _submit_donation(session, str(expected_island), project, amount,
                     city_id=str(city_id), reviewed=True)
    # A submitted request is not a verified game receipt. Never repeat it.
    session.setStatus("Donation submitted; verify the island balance")


@configurator
def donate(session, event, stdin_fd, predetermined_input):
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

        city = chooseCity(session)
        banner()

        woodAvailable = city["availableResources"][0]

        islandId = city["islandId"]
        html = session.get(island_url + islandId)
        island = getIsland(html)

        island_type = island["tipo"]
        resource_name = tradegoods_names[0]
        tradegood_name = tradegoods_names[int(island_type)]

        # get resource information
        url = "view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1".format(
            islandId, actionRequest
        )
        resp = session.post(url)
        resp = json.loads(resp, strict=False)

        resourceLevel = resp[0][1]["backgroundData"]["resourceLevel"]
        tradegoodLevel = resp[0][1]["backgroundData"]["tradegoodLevel"]
        resourceEndUpgradeTime = int(
            resp[0][1]["backgroundData"]["resourceEndUpgradeTime"]
        )
        resourceUpgrading = resourceEndUpgradeTime > 0
        tradegoodEndUpgradeTime = int(
            resp[0][1]["backgroundData"]["tradegoodEndUpgradeTime"]
        )
        tradegoodUpgrading = tradegoodEndUpgradeTime > 0

        if resourceUpgrading:
            resourceUpgradeMsg = "(upgrading, ends in:{})".format(
                daysHoursMinutes(resourceEndUpgradeTime)
            )
        else:
            resourceUpgradeMsg = ""
        if tradegoodUpgrading:
            tradegoodUpgradeMsg = "(upgrading, ends in:{})".format(
                daysHoursMinutes(tradegoodEndUpgradeTime)
            )
        else:
            tradegoodUpgradeMsg = ""

        html = resp[1][1][1]
        wood_matches = re.findall(r'<li class="wood">(.*?)</li>', html)
        
        # if there are 3 matches, the third one is the wood on inventory
        if len(wood_matches) == 3:
            wood_total_needed, wood_donated, wood_on_inventory = wood_matches
        else:
            wood_total_needed, wood_donated = wood_matches[:2]
            wood_on_inventory = 0

        # remove all characters that are not numbers
        wood_total_needed = int(re.sub(r'[^0-9]', '', wood_total_needed))
        wood_donated = int(re.sub(r'[^0-9]', '', wood_donated))

        if resourceUpgrading and tradegoodUpgrading:
            print(
                
                "Both the {} (ends in:{}) and the {} (ends in:{}) are being upgraded rigth now.\n".format(
                    resource_name,
                    daysHoursMinutes(resourceEndUpgradeTime),
                    tradegood_name,
                    daysHoursMinutes(tradegoodEndUpgradeTime),
                )
                
            )
            enter()
            event.set()
            return

        print("{} lv:{} {}".format(resource_name, resourceLevel, resourceUpgradeMsg))
        print(
            "{} / {} ({}%)\n".format(
                addThousandSeparator(wood_donated),
                addThousandSeparator(wood_total_needed),
                addThousandSeparator(int((100 * wood_donated) / wood_total_needed)),
            )
        )

        # get tradegood information
        url = "view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1".format(
            island_type, islandId, actionRequest
        )
        resp = session.post(url)

        resp = json.loads(resp, strict=False)
        html = resp[1][1][1]

        tradegood_matches = re.findall(r'<li class="wood">(.*?)</li>', html)
        
        # if there are 3 matches, the third one is the wood on inventory
        if len(tradegood_matches) == 3:
            tradegood_total_needed, tradegood_donated, wood_on_inventory = tradegood_matches
        else:
            tradegood_total_needed, tradegood_donated = tradegood_matches
            wood_on_inventory = 0

        # remove all characters that are not numbers
        tradegood_total_needed = int(re.sub(r'[^0-9]', '', tradegood_total_needed))
        tradegood_donated = int(re.sub(r'[^0-9]', '', tradegood_donated))
        if wood_on_inventory != 0:
            wood_on_inventory = int(re.sub(r'[^0-9]', '', wood_on_inventory))

        print("{} lv:{} {}".format(tradegood_name, tradegoodLevel, tradegoodUpgradeMsg))
        print(
            "{} / {} ({}%)\n".format(
                addThousandSeparator(tradegood_donated),
                addThousandSeparator(tradegood_total_needed),
                addThousandSeparator(
                    int((100 * tradegood_donated) / tradegood_total_needed)
                ),
            )
        )

        print("Wood available:{}\n".format(addThousandSeparator(woodAvailable)))
        print("Wood on inventory available:{}\n".format(addThousandSeparator(wood_on_inventory)))
        print("Total wood available for donation:{}\n".format(addThousandSeparator(woodAvailable + wood_on_inventory)))

        if resourceUpgrading is False and tradegoodUpgrading is False:
            msg = "Donate to {} (1) or {} (2)?:".format(
                resource_name, tradegood_name
            )
            donation_type = read(msg=msg, min=1, max=2)
            name = resource_name if donation_type == 1 else tradegood_name
            print("")
        else:
            if resourceUpgrading is False and tradegoodUpgrading is True:
                donation_type = 1
                name = resource_name
            else:
                donation_type = 2
                name = tradegood_name
            print("Donate to:{}\n".format(name))

        donation_type = "resource" if donation_type == 1 else "tradegood"

        amount = read(
            min=0,
            max=woodAvailable,
            default=0,
            additionalValues=["all", "half"],
            msg="Amount (number, all, half):",
        )
        if amount == "all":
            amount = woodAvailable
        elif amount == "half":
            amount = woodAvailable // 2
        elif amount == 0:
            event.set()
            return
        print("Will donate {} to the {}?".format(addThousandSeparator(amount), name))
        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        _submit_donation(session, islandId, donation_type, amount)

        print("\nDonation successful.")
        enter()
        event.set()
        return
    except KeyboardInterrupt:
        event.set()
        return