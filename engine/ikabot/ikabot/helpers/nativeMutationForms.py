"""Exact upstream reviewed forms for protected cookie workers (ADR-006).

The game modules remain responsible for ownership, affordability and review.
This layer only verifies the original request shape, city context and token.
Never expose this as a generic proxy or allow automatic mutation retries.
"""
import re
from urllib.parse import parse_qsl

from ikabot.config import actionRequest


ACTIONS = {"UpgradeExistingBuilding", "BuildNewBuilding", "SaveBuildingPositions"}
FUNCTIONS = {("CityScreen", "buildUnits"), ("CityScreen", "buildShips"),
             ("IslandScreen", "workerPlan"), ("CityScreen", "assignPriests"),
             ("IslandScreen", "donate"), ("CityScreen", "assignWinePerTick"),
             ("Advisor", "doResearch")}


def matches(url, params):
    return (isinstance(url, str) and (url.startswith("action=UpgradeExistingBuilding&")
            or url.startswith("action=Advisor&function=doResearch&"))) or (
        isinstance(params, dict) and (params.get("action") in ACTIONS
        or (params.get("action"), params.get("function")) in FUNCTIONS))


def number(value, low=0, high=10**12-1):
    return (type(value) in (int, str) and re.fullmatch(r"[0-9]{1,12}", str(value)) is not None
            and low <= int(value) <= high)


def require(condition):
    if not condition:
        raise ValueError("Unsupported reviewed cookie mutation form")


def validate(url, params, *, noIndex=False):
    common = {"action", "actionRequest", "ajax", "templateView"}
    city_fields = common | {"cityId", "currentCityId", "backgroundView"}
    if url:
        require(not params and not noIndex and len(url) <= 512
                and re.fullmatch(r"[A-Za-z0-9_=&-]+", url) is not None)
        pairs = parse_qsl(url, strict_parsing=True, keep_blank_values=True)
        form = dict(pairs)
        require(len(form) == len(pairs))
    else:
        form = params
    action, function = form.get("action"), form.get("function")
    token = form.get("actionRequest")
    require(isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,128}", token) is not None
            and str(form.get("ajax")) == "1")
    if action == "UpgradeExistingBuilding":
        require(bool(url) and set(form) == city_fields | {"position", "level", "activeTab"}
                and form["activeTab"] == "tabSendTransporter" and number(form["level"], high=150)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", form["templateView"]) is not None
                and token == actionRequest)
    elif action == "BuildNewBuilding":
        require(not url and noIndex and set(form) == city_fields | {"position", "building"}
                and form["templateView"] == "buildingGround" and number(form["building"], 1, 999999))
    elif action == "SaveBuildingPositions":
        moves = set(form) - city_fields
        require(not url and noIndex and city_fields <= set(form) and len(moves) % 2 == 0
                and 2 <= len(moves) <= 162 and token == actionRequest
                and form["templateView"] == "saveCityBuildingsPositions")
        require(moves == {f"moves[{i}][{key}]" for i in range(len(moves)//2) for key in ("from", "to")}
                and all(number(form[k], high=80) for k in moves))
        require(len({str(form[f"moves[{i}][from]"]) for i in range(len(moves)//2)}) == len(moves)//2
                and len({str(form[f"moves[{i}][to]"]) for i in range(len(moves)//2)}) == len(moves)//2)
    elif (action, function) in (("CityScreen", "buildUnits"), ("CityScreen", "buildShips")):
        base = city_fields | {"position", "function"}
        units = set(form) - base
        require(not url and not noIndex and base <= set(form) and 1 <= len(units) <= 100
                and form["templateView"] == ("barracks" if function == "buildUnits" else "shipyard")
                and token == actionRequest and all(number(k, 1, 9999999) and number(form[k], 1, 10**9) for k in units)
                and len({str(k) for k in units}) == len(units))
    elif (action, function) == ("IslandScreen", "workerPlan"):
        kind = form.get("screen")
        require(not url and not noIndex and token == actionRequest)
        if kind in ("resource", "tradegood"):
            key = "rw" if kind == "resource" else "tw"
            require(set(form) == common | {"function", "islandId", "cityId", "type", "screen", key}
                    and form["type"] == kind == form["templateView"]
                    and number(form["islandId"], 1) and number(form[key], high=10**9))
            require(number(form["cityId"], 1))
            return str(form["cityId"])
        require(kind == "academy" and set(form) == city_fields | {"function", "screen", "position", "s"}
                and form["templateView"] == "academy" and number(form["s"], high=10**9))
    elif (action, function) in (("CityScreen", "assignPriests"), ("CityScreen", "assignWinePerTick")):
        priests = function == "assignPriests"
        key = "priests" if priests else "amount"
        require(not url and not noIndex and set(form) == city_fields | {"position", "function", key}
                and form["templateView"] == ("temple" if priests else "tavern")
                and number(form[key], high=10**9) and (not priests or token == actionRequest))
    elif (action, function) == ("IslandScreen", "donate"):
        require(not url and not noIndex and set(form) == common | {"function", "islandId", "cityId", "type", "donation", "backgroundView"}
                and form["backgroundView"] == "island" and form["templateView"] == "resource"
                and form["type"] in ("resource", "tradegood") and number(form["islandId"], 1)
                and number(form["donation"], 1, 10**9) and number(form["cityId"], 1) and token == actionRequest)
        return str(form["cityId"])
    elif (action, function) == ("Advisor", "doResearch"):
        require(bool(url) and set(form) == common | {"function", "type", "backgroundView", "currentCityId"}
                and form["templateView"] == "researchAdvisor" and form["backgroundView"] == "city"
                and token == actionRequest and number(form["currentCityId"], 1)
                and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", form["type"]) is not None)
        return str(form["currentCityId"])
    else:
        require(False)
    require(number(form.get("cityId"), 1) and str(form.get("currentCityId")) == str(form["cityId"])
            and form["backgroundView"] == "city" and ("position" not in form or number(form["position"], high=80)))
    return str(form["cityId"])
