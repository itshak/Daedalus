from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
from ikabot.helpers.process import updateProcessList
import hashlib
import os
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read


def activateVacationMode(session, *, reviewed_city=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    city = getCity(session.get()) if reviewed_city is None else reviewed_city

    data = {
        "action": "Options",
        "function": "activateVacationMode",
        "actionRequest": actionRequest,
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "options_umod_confirm",
    }
    if reviewed_city is None:
        session.post(params=data, ignoreExpire=True)
    else:
        session.post(params=data, ignoreExpire=True, retry_on_failure=False)


def preview_native_vacation(session, city_id):
    if type(city_id) is not int or not 0 < city_id < 10**12:
        raise ValueError("Invalid owned city")
    pedirInfo.ids_cache = None
    owned = requireOwnCity(session, city_id, "Vacation account city")
    city = getCityById(session, owned)
    if str(city["id"]) != owned:
        raise ValueError("City identity changed")
    # Include legacy CLI children as well as controller-managed children.
    # updateProcessList only refreshes local process bookkeeping.
    active = [p for p in updateProcessList(session) if p.get("pid") != os.getpid()]
    fingerprint = hashlib.sha256(
        f"{session.mundo}-{session.servidor}:{session.username}:{owned}".encode()
    ).hexdigest()
    return {"city_id": city_id, "city_name": str(city["cityName"])[:100],
            "active_jobs": len(active), "ready": not active,
            "config": {"city_id": city_id, "expected": fingerprint}}


def prepare_native_vacation(session, city_id, expected):
    plan = preview_native_vacation(session, city_id)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Vacation review is stale or other account jobs are active")
    return plan["config"]


@task("vacationMode", prepare=prepare_native_vacation)
def native_vacation(session, city_id: int, expected: str):
    prepare_native_vacation(session, city_id, expected)
    city = getCityById(session, str(city_id))
    if str(city["id"]) != str(city_id):
        raise ValueError("City identity changed")
    session.setStatus("Submitting reviewed account vacation activation")
    activateVacationMode(session, reviewed_city=city)
    session.setStatus("Vacation request submitted; verify the account in game")


@configurator
def vacationMode(session, event, stdin_fd, predetermined_input):
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
        print("Activate vacation mode? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        activateVacationMode(session)

        print("Vacation mode has been activated.")
        enter()
        event.set()
        clear()
        sys.exit()
    except KeyboardInterrupt:
        event.set()
        return
