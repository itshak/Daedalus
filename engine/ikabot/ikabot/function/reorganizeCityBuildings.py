from ikabot.helpers.decorators import configurator, task
from ikabot.helpers import pedirInfo
from ikabot.helpers.taskConfig import requireOwnCity, getCityById
import hashlib
import json
#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import time
from collections import defaultdict

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *


# palace and palaceColony occupy the same logical role — treat as equivalent
_GOVERNMENT_BUILDINGS = {'palace', 'palaceColony'}


def _normalize(building):
    return 'government' if building in _GOVERNMENT_BUILDINGS else building


def _compute_moves(template_city, target_city):
    """
    Returns a list of (from_pos, to_pos) swaps that transform the target
    city's building layout to match the template city's layout.
    Buildings that exist in the template but not in the target are skipped.
    """
    # Group template positions by normalized building type (sorted)
    template_by_type = defaultdict(list)
    for slot in template_city['position']:
        if slot['building'] != 'empty':
            template_by_type[_normalize(slot['building'])].append(slot['position'])
    for k in template_by_type:
        template_by_type[k].sort()

    # Group target positions by normalized building type (sorted)
    target_by_type = defaultdict(list)
    for slot in target_city['position']:
        if slot['building'] != 'empty':
            target_by_type[_normalize(slot['building'])].append(slot['position'])
    for k in target_by_type:
        target_by_type[k].sort()

    # Build assignment: desired_pos → original_pos
    # "the building originally at original_pos should end up at desired_pos"
    assignment = {}
    for btype, template_positions in template_by_type.items():
        available = target_by_type.get(btype, [])
        for i, desired_pos in enumerate(template_positions):
            if i >= len(available):
                break
            original_pos = available[i]
            if original_pos != desired_pos:
                assignment[desired_pos] = original_pos

    if not assignment:
        return []

    # Track current position of each building being relocated
    # key: original_pos, value: current_pos (changes as swaps are applied)
    tracker = {orig: orig for orig in assignment.values()}
    reverse_tracker = {v: k for k, v in tracker.items()}

    moves = []
    for desired_pos, original_pos in assignment.items():
        current = tracker[original_pos]
        if current == desired_pos:
            continue

        moves.append((current, desired_pos))

        # Update tracker to reflect the swap
        displaced_original = reverse_tracker.get(desired_pos)
        tracker[original_pos] = desired_pos
        reverse_tracker[desired_pos] = original_pos
        if desired_pos in reverse_tracker:
            reverse_tracker.pop(current, None)
        if displaced_original is not None:
            tracker[displaced_original] = current
            reverse_tracker[current] = displaced_original

    return moves


def _review_layout(city):
    """Validate the actual slot map, keeping only bounded nonsecret fields."""
    rows = city["position"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 81:
        raise ValueError("Invalid city layout")
    result = []
    seen = set()
    for row in rows:
        position, building = row.get("position"), row.get("building")
        level = row.get("level", 0)
        if (type(position) is not int or not 0 <= position <= 80 or position in seen
                or not isinstance(building, str) or not 0 < len(building) <= 64
                or type(level) is not int or not 0 <= level <= 150):
            raise ValueError("Invalid building position")
        seen.add(position)
        result.append({"position": position, "building": building, "level": level,
                       "busy": row.get("isBusy") is True, "type": str(row.get("type") or "")[:32]})
    return sorted(result, key=lambda row: row["position"])


def preview_native_layout(session, city_id, template_city_id):
    if (type(city_id) is not int or type(template_city_id) is not int
            or not 0 < city_id < 10**12 or not 0 < template_city_id < 10**12
            or city_id == template_city_id):
        raise ValueError("Choose two different owned cities")
    pedirInfo.ids_cache = None
    target_id = requireOwnCity(session, city_id, "Target city")
    template_id = requireOwnCity(session, template_city_id, "Template city")
    target = getCityById(session, target_id)
    template = getCityById(session, template_id)
    if str(target["id"]) != target_id or str(template["id"]) != template_id:
        raise ValueError("City identity changed")
    target_rows, template_rows = _review_layout(target), _review_layout(template)
    target_slots = {row["position"]: dict(row) for row in target_rows}
    moves = _compute_moves({"position": template_rows}, {"position": target_rows})
    if len(moves) > 80:
        raise ValueError("Too many layout moves")
    display = []
    for origin, destination in moves:
        a, b = target_slots.get(origin), target_slots.get(destination)
        if a is None or b is None or a["busy"] or b["busy"]:
            raise ValueError("Layout touches an unavailable or busy slot")
        if a["type"] and b["type"] and a["type"] != b["type"]:
            raise ValueError("Layout crosses incompatible slot types")
        display.append({"from": origin, "to": destination,
                        "building": a["building"], "displaced": b["building"]})
        target_slots[origin] = {**b, "position": origin, "type": a["type"]}
        target_slots[destination] = {**a, "position": destination, "type": b["type"]}
    expected = hashlib.sha256(json.dumps(
        [target_rows, template_rows], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {"city_id": city_id, "template_city_id": template_city_id,
            "city_name": str(target["cityName"])[:100],
            "template_name": str(template["cityName"])[:100],
            "moves": display, "ready": bool(display),
            "config": {"city_id": city_id, "template_city_id": template_city_id,
                       "expected": expected}}


def prepare_native_layout(session, city_id, template_city_id, expected):
    plan = preview_native_layout(session, city_id, template_city_id)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Layout review is stale or no moves are needed")
    return plan["config"]


@task("reorganizeCityBuildings", prepare=prepare_native_layout)
def native_layout(session, city_id: int, template_city_id: int, expected: str):
    plan = preview_native_layout(session, city_id, template_city_id)
    if not plan["ready"] or expected != plan["config"]["expected"]:
        raise ValueError("Layout review is stale or no moves are needed")
    city = str(city_id)
    session.post(
        f"view=saveCityBuildingsPositions&cityId={city}&backgroundView=city"
        f"&currentCityId={city}&actionRequest={actionRequest}&ajax=1",
        noIndex=True,
    )
    params = {"action": "SaveBuildingPositions", "backgroundView": "city",
              "currentCityId": city, "templateView": "saveCityBuildingsPositions",
              "actionRequest": actionRequest, "ajax": "1", "cityId": city}
    for index, move in enumerate(plan["moves"]):
        params[f"moves[{index}][from]"] = move["from"]
        params[f"moves[{index}][to]"] = move["to"]
    session.setStatus("Submitting reviewed building layout")
    session.post(params=params, noIndex=True, retry_on_failure=False)
    session.setStatus("Layout submitted; verify the city")


@configurator
def reorganizeCityBuildings(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd : int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        banner()
        print('Select the template city (the layout to copy from):')
        template_city = chooseCity(session)

        banner()
        print('Select the cities to reorganize:')
        target_city_ids, _ = ignoreCities(session, msg='Select target cities:')

        for city_id in target_city_ids:
            if str(city_id) == str(template_city['id']):
                continue

            html = session.get(city_url + city_id)
            target_city = getCity(html)

            moves = _compute_moves(template_city, target_city)

            if not moves:
                print('{}: layout already matches template, no changes needed.'.format(
                    target_city['cityName']))
                continue

            # Open the reorganization dialog (mimics clicking the button in-game)
            dialog_params = (
                'view=saveCityBuildingsPositions'
                '&cityId={city_id}'
                '&backgroundView=city'
                '&currentCityId={city_id}'
                '&actionRequest={actionRequest}'
                '&ajax=1'
            ).format(city_id=city_id, actionRequest=actionRequest)
            session.post(dialog_params, noIndex=True)

            # Simulate time spent looking at the layout before dragging
            time.sleep(random.uniform(2.0, 5.0))

            # Simulate drag-and-drop: ~1–3 s per move
            time.sleep(random.uniform(1.0, 3.0) * len(moves))

            params = {
                'action': 'SaveBuildingPositions',
                'backgroundView': 'city',
                'currentCityId': city_id,
                'templateView': 'saveCityBuildingsPositions',
                'actionRequest': actionRequest,
                'ajax': '1',
                'cityId': city_id,
            }
            for i, (from_pos, to_pos) in enumerate(moves):
                params['moves[{}][from]'.format(i)] = from_pos
                params['moves[{}][to]'.format(i)] = to_pos

            session.post(params=params, noIndex=True)
            print('{}: reorganized with {} move(s).'.format(
                target_city['cityName'], len(moves)))

            # Pause between cities to avoid looking like a bot
            time.sleep(random.uniform(3.0, 7.0))

        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()
