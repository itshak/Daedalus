#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import random
import re
import time
from decimal import *

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.naval import *
from ikabot.helpers.varios import wait, getCurrentCityId
from ikabot.helpers.fillProgress import mark
from ikabot.helpers.pedirInfo import getShipCapacity


def transport_feedback(response):
    """Read named game feedback, independent of command ordering.

    Never infer success from a generic state update or arbitrary nested type.
    The raw response and localized server text must not cross the IPC boundary.
    """
    try:
        rows = json.loads(response, strict=False)
    except (ValueError, TypeError):
        return "invalid_transport_response"
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        return "invalid_transport_response"
    feedback = []
    for entry in rows:
        if not isinstance(entry, list) or not entry or entry[0] != "provideFeedback":
            continue
        if len(entry) != 2 or not isinstance(entry[1], list) or len(entry[1]) > 100:
            return "invalid_transport_response"
        for item in entry[1]:
            if not isinstance(item, dict) or type(item.get("type")) is not int:
                return "invalid_transport_response"
            feedback.append(item["type"])
    if 11 in feedback:
        return "transport_rejected"
    if feedback and all(kind == 10 for kind in feedback):
        return "accepted"
    return "transport_feedback_unconfirmed"


def sendGoods(session, originCityId, destinationCityId, islandId, ships, send, useFreighters=False, checkpoint=None, route_index=None, verify_recipient=None, before_send=None):
    """This function will execute one route
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    originCityId : int
        integer representing the ID of the origin city
    destinationCityId : int
        integer representing the ID of the destination city
    islandId : int
        integer representing the ID of the destination city's island
    ships : int
        integer representing the amount of ships needed to execute the route
    send : list
        array of resources to send
    """
    cookie_review = (before_send is not None
                     and getattr(session, "_daedalus_cookies_only", False) is True)
    # this can fail if a random request is made in between this two posts
    while True:
        if cookie_review:
            # The default view may be the advisor or island, not a city.
            mark(session, "checking_current_city")
            currId = getCurrentCityId(session)
        else:
            html = session.get()
            currId = getCity(html)["id"]
        city = getCity(session.get(city_url + originCityId))
        if cookie_review:
            # The guard reads the destination city and advisor. Those views can
            # change selected-city context. Complete them before selecting origin.
            before_send()
            currId = getCurrentCityId(session)

        # Change from the city the bot is sitting right now to the city we want to load resources from
        data = {
            "action": "header",
            "function": "changeCurrentCity",
            "actionRequest": actionRequest,
            "oldView": "city",
            "cityId": originCityId,
            "backgroundView": "city",
            "currentCityId": currId,
            "ajax": "1",
        }

        if cookie_review:
            mark(session, "switching_city")
            session._daedalus_reviewed_transport_post(data)
        else:
            session.post(params=data)

        # Request to send the resources from the origin to the target
        data = {
            "action": "transportOperations",
            "function": "loadTransportersWithFreight",
            "destinationCityId": destinationCityId,
            "islandId": islandId,
            "oldView": "",
            "position": "",
            "avatar2Name": "",
            "city2Name": "",
            "type": "",
            "activeTab": "",
            "transportDisplayPrice": "0",
            "premiumTransporter": "0",
            "capacity": "5",
            "max_capacity": "5",
            "jetPropulsion": "0",
            "backgroundView": "city",
            "currentCityId": originCityId,
            "templateView": "transport",
            "currentTab": "tabSendTransporter",
            "actionRequest": actionRequest,
            "ajax": "1",
        }
        
        if useFreighters is False:
            shiptype = "transporters"
            data[shiptype] = ships
            if cookie_review:
                available = getAvailableShips(session)
                if type(available) is not int or available < ships:
                    raise RuntimeError("Reviewed fleet changed; review before retry")
                data["normalTransportersMax"] = available
        else:
            shiptype = "usedFreightersShips"
            data[shiptype] = ships
            data["transporters"] = "0"
        if verify_recipient is not None:
            verify_recipient(route_index)
        # Re-read after changing the selected city and recipient verification.
        # Never silently omit a resource that vanished after the route planner
        # chose the chunk: its checkpoint would otherwise record phantom cargo.
        city = getCity(session.get(city_url + originCityId))
        if (str(city.get("id")) != str(originCityId)
                or not isinstance(send, (list, tuple)) or len(send) != 5
                or any(type(n) is not int or n < 0 for n in send)
                or not any(send)
                or not isinstance(city.get("availableResources"), list)
                or len(city["availableResources"]) != 5
                or any(type(n) is not int or n < wanted
                       for n, wanted in zip(city["availableResources"], send))):
            raise RuntimeError("Transport source changed; review remaining cargo before retrying")
        for i, amount in enumerate(send):
            if amount:
                key = "cargo_resource" if i == 0 else "cargo_tradegood{:d}".format(i)
                data[key] = amount

        if before_send is not None and not cookie_review:
            before_send()
        # Reserve before transport POST; unknown outcomes remain uncertain.
        chunk_id = checkpoint.reserve(route_index, send) if checkpoint else None
        # The server may have accepted the cargo before a response was lost.
        # Never replay this non-idempotent POST at the transport layer.
        mark(session, "submitting")
        resp = (session._daedalus_reviewed_transport_post(data) if cookie_review
                else session.post(params=data, retry_on_failure=False))
        mark(session, "checking_transport_response")
        if cookie_review:
            feedback = transport_feedback(resp)
            if feedback != "accepted":
                mark(session, feedback)
                raise RuntimeError("Reviewed transport not confirmed; reconcile before retry")
            break
        try:
            outcome = json.loads(resp, strict=False)[3][1][0]["type"]
        except (ValueError, TypeError, KeyError, IndexError):
            raise RuntimeError("Unrecognized transport outcome needs manual reconciliation") from None
        if outcome == 10:
            if checkpoint:
                checkpoint.confirmed(chunk_id, send)
            break
        if outcome == 11:
            if before_send is not None:
                raise RuntimeError("Reviewed transport rejected; review before retrying")
            if checkpoint:
                checkpoint.rejected(chunk_id, send)
            wait(getMinimumWaitingTime(session))
        else:
            raise RuntimeError("Unrecognized transport outcome needs manual reconciliation")
        time.sleep(5)


def executeRoutes(session, routes, useFreighters=False, checkpoint=None, verify_recipient=None):
    """This function will execute all the routes passed to it, regardless if there are enough ships available to do so
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    routes : list
        a list of tuples, each of which represent a route. A route is defined like so : (originCity,destinationCity,islandId,wood,wine,marble,crystal,sulfur). originCity and destintionCity should be passed as City objects
    """
    ship_capacity, freighter_capacity = getShipCapacity(session)
    for route_index, route in enumerate(routes):
        (origin_city, destination_city, island_id, *toSend) = route
        if checkpoint:
            toSend = checkpoint.remaining(route_index, list(toSend))
        destination_city_id = destination_city["id"]

        while sum(toSend) > 0:
            session.setStatus(
                f' Sending {toSend[0]}W, {toSend[1]}V, {toSend[2]}M, {toSend[3]}C, {toSend[4]}S | {origin_city["name"]} ---> {destination_city["name"]} '
            )
            ships_available = waitForArrival(session, useFreighters)
            if useFreighters is False:
                storageCapacityInShips = ships_available * ship_capacity
            else:
                storageCapacityInShips = ships_available * freighter_capacity

            html = session.get(city_url + str(origin_city["id"]))
            origin_city = getCity(html)
            html = session.get(city_url + str(destination_city_id))
            destination_city = getCity(html)
            foreign = str(destination_city["id"]) != str(destination_city_id)
            if foreign is False:
                storageCapacityInCity = destination_city["freeSpaceForResources"]

            send = []
            for i in range(len(toSend)):
                if foreign is False:
                    min_val = min(
                        origin_city["availableResources"][i],
                        toSend[i],
                        storageCapacityInShips,
                        storageCapacityInCity[i],
                    )
                else:
                    min_val = min(
                        origin_city["availableResources"][i],
                        toSend[i],
                        storageCapacityInShips,
                    )
                send.append(min_val)
                storageCapacityInShips -= send[i]
                if checkpoint is None:
                    toSend[i] -= send[i]

            resources_to_send = sum(send)
            if resources_to_send == 0:
                # no space available
                # wait an hour and try again
                wait(60 * 60)
                continue

            if useFreighters is False:
                available_ships = int(
                    math.ceil((Decimal(resources_to_send) / Decimal(ship_capacity)))
                )
            else:
                available_ships = int(
                    math.ceil((Decimal(resources_to_send) / Decimal(freighter_capacity)))
                )
            sendGoods(
                session,
                origin_city["id"],
                destination_city_id,
                island_id,
                available_ships,
                send,
                useFreighters,
                checkpoint=checkpoint, route_index=route_index,
                **({"verify_recipient": verify_recipient} if verify_recipient is not None else {}),
            )
            if checkpoint:
                toSend = [remaining - transferred
                          for remaining, transferred in zip(toSend, send)]
            time.sleep(random.randint(5, 15))


def splitCargoBetweenFleets(session, toSend):
    """This function splits a cargo between trade ships and freighters. Trade ships are filled first because they are faster, and whatever doesn't fit in the currently available trade ships is assigned to the freighters. If only one of the two fleets has ships available, the whole cargo is assigned to it
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    toSend : list
        array of resources to send

    Returns
    -------
    (tradeShipCargo, freighterCargo) : tuple
        two arrays of resources, the first one to be sent with trade ships and the second one with freighters
    """
    tradeShipCargo = [0] * len(toSend)
    freighterCargo = [0] * len(toSend)

    if getAvailableFreighters(session) == 0:
        return list(toSend), freighterCargo

    ship_capacity, _ = getShipCapacity(session)
    tradeShipSpace = getAvailableShips(session) * ship_capacity
    if tradeShipSpace == 0:
        return tradeShipCargo, list(toSend)

    for i in range(len(toSend)):
        tradeShipCargo[i] = min(toSend[i], tradeShipSpace)
        tradeShipSpace -= tradeShipCargo[i]
        freighterCargo[i] = toSend[i] - tradeShipCargo[i]

    return tradeShipCargo, freighterCargo


def get_random_wait_time():
    return random.randint(0, 20) * 3


def getMinimumWaitingTime(session):
    """This function returns the time needed to wait for the closest fleet to arrive. If all ships are unavailable, this represents the minimum time needed to wait for any ships to become available. A random waiting time between 0 and 10 seconds is added to the waiting time to avoid race conditions between multiple concurrently running processes.
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    timeToWait : int
        the minimum waiting time for the closest fleet to arrive
    """
    html = session.get()
    idCiudad = re.search(r"currentCityId:\s(\d+),", html).group(1)
    url = "view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1".format(
        idCiudad, actionRequest
    )
    if getattr(session, "_daedalus_cookies_only", False) is True:
        from ikabot.function.fillCityWarehouse import _advisor_data
        postdata = _advisor_data(session, idCiudad)
    else:
        posted = session.post(url)
        postdata = json.loads(posted, strict=False)
    militaryMovements = postdata[1][1][2]["viewScriptParams"][
        "militaryAndFleetMovements"
    ]
    current_time = int(postdata[0][1]["time"])
    delivered_times = []
    for militaryMovement in [mv for mv in militaryMovements if mv["isOwnArmyOrFleet"]]:
        remaining_time = int(militaryMovement["eventTime"]) - current_time
        delivered_times.append(remaining_time)
    if delivered_times:
        return min(delivered_times) + get_random_wait_time()
    else:
        return 0


def waitForArrival(session, useFreighters=False):
    """This function will return the number of available ships, and if there aren't any, it will wait for the closest fleet to arrive and then return the number of available ships
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    ships : int
        number of available ships
    """
    if useFreighters is False: available_ships = getAvailableShips(session)
    elif useFreighters is True: available_ships = getAvailableFreighters(session)
    while available_ships == 0:
        minimum_waiting_time_for_ship = getMinimumWaitingTime(session)
        wait(minimum_waiting_time_for_ship)
        if useFreighters is False: available_ships = getAvailableShips(session)
        elif useFreighters is True: available_ships = getAvailableFreighters(session)
    return available_ships
