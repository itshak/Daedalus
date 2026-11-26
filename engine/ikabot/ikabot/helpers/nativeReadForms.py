"""Daedalus compatibility overlay for exact upstream read-only AJAX forms.

Keep these checks outside game modules. Never allow action/function fields
or arbitrary query strings into the protected read transport.
"""
import re
from urllib.parse import parse_qsl

from ikabot.config import actionRequest

PARAM_VIEWS = frozenset({
    "barracks", "shipyard", "temple", "buildingSpeedup", "workshop",
    "militaryAdvisor", "buildingGround", "deployment", "branchOffice", "branchOfficeOwnOffers",
})
URL_VIEWS = frozenset("view=" + view for view in (
    "saveCityBuildingsPositions", "researchAdvisor", "academy", "temple",
    "branchOffice", "finances", "resource", "tradegood", "takeOffer",
))


def _id(value):
    return type(value) in (int, str) and re.fullmatch(r"[1-9][0-9]{0,11}", str(value)) is not None


def _position(value):
    return type(value) in (int, str) and re.fullmatch(r"[0-9]{1,3}", str(value)) is not None


def validate_params(params, *, noIndex=False):
    view = params.get("view")
    if view == "deployment":
        if (noIndex or set(params) != {
                "view", "deploymentType", "destinationCityId", "backgroundView",
                "currentCityId", "actionRequest", "ajax"}
                or params["deploymentType"] not in ("army", "fleet")
                or not _id(params["destinationCityId"]) or not _id(params["currentCityId"])
                or params["backgroundView"] != "city" or str(params["ajax"]) != "1"
                or params["actionRequest"] != actionRequest):
            raise ValueError("Unsupported cookie-only deployment view")
        return
    common = {"view", "cityId", "currentCityId", "backgroundView", "actionRequest", "ajax"}
    extra = {
        "barracks": {"position"},
        "shipyard": {"position"},
        "temple": {"position"},
        "buildingSpeedup": {"position"},
        "buildingGround": {"position"},
        "workshop": {"position", "activeTab", "templateView"},
        "militaryAdvisor": {"oldView", "templateView"},
        "branchOffice": {"position", "activeTab", "type", "searchResource",
                         "range", "templateView", "currentTab"},
        "branchOfficeOwnOffers": {"position", "activeTab", "templateView", "currentTab"},
    }
    if (view not in extra or noIndex != (view in ("buildingGround", "branchOfficeOwnOffers"))
            or set(params) != common | extra[view]
            or not _id(params["cityId"])
            or str(params["currentCityId"]) != str(params["cityId"])
            or params["backgroundView"] != "city" or str(params["ajax"]) != "1"):
        raise ValueError("Unsupported cookie-only queue view")
    if "position" in params and not _position(params["position"]):
        raise ValueError("Invalid queue building position")
    if view == "workshop" and (params["activeTab"] not in ("tabUnits", "tabShips")
                               or params["templateView"] != "workshop"):
        raise ValueError("Unsupported workshop queue tab")
    if view == "militaryAdvisor" and (params["oldView"] != "updateGlobalData"
                                      or params["templateView"] != view):
        raise ValueError("Unsupported advisor queue view")
    if view == "branchOffice" and (
            params["activeTab"] != "bargain" or params["currentTab"] != "bargain"
            or params["templateView"] != view or str(params["type"]) not in ("333", "444")
            or str(params["searchResource"]) not in ("resource", "1", "2", "3", "4")
            or not re.fullmatch(r"[1-9][0-9]{0,2}", str(params["range"]))):
        raise ValueError("Unsupported market search view")
    if view == "branchOfficeOwnOffers" and (
            params["activeTab"] != "tab_branchOfficeOwnOffers"
            or params["currentTab"] != "tab_branchOfficeOwnOffers"
            or params["templateView"] != view):
        raise ValueError("Unsupported own-offers view")
    if view != "workshop" and params["actionRequest"] != actionRequest:
        raise ValueError("Unsupported queue view request token")


def validate_url(url, *, noIndex=False):
    # Require the exact canonical unescaped upstream form, with no duplicate
    # fields or URL syntax that could change interpretation downstream.
    if len(url) > 512 or not re.fullmatch(r"[A-Za-z0-9_=&-]+", url):
        raise ValueError("Unsupported cookie-only read URL")
    pairs = parse_qsl(url, strict_parsing=True, keep_blank_values=True)
    query = dict(pairs)
    view = query.get("view")
    if len(pairs) != len(query) or query.get("actionRequest") != actionRequest or query.get("ajax") != "1":
        raise ValueError("Unsupported cookie-only read URL")
    if view in ("resource", "tradegood"):
        fields = {"view", "type", "islandId", "backgroundView", "currentIslandId", "actionRequest", "ajax"}
        if "cityId" in query:
            fields.add("cityId")
        valid_type = ("resource",) if view == "resource" else ("tradegood", "1", "2", "3", "4")
        if (noIndex or set(query) != fields or query["type"] not in valid_type
                or not _id(query["islandId"]) or query["islandId"] != query["currentIslandId"]
                or query["backgroundView"] != "island"
                or ("cityId" in query and not _id(query["cityId"]))):
            raise ValueError("Unsupported island read URL")
        return
    fields = {"view", "cityId", "backgroundView", "currentCityId", "actionRequest", "ajax"}
    if view in ("academy", "temple", "branchOffice"):
        fields.add("position")
        if view == "academy" and "templateView" in query:
            fields.add("templateView")
            if query["templateView"] != "academy":
                raise ValueError("Unsupported academy read template")
    elif view == "researchAdvisor":
        fields.update(("oldView", "templateView"))
    elif view == "finances":
        fields.remove("cityId")
        fields.add("templateView")
    elif view == "takeOffer":
        fields.update(("destinationCityId", "oldView", "activeTab", "position",
                       "type", "resource", "templateView"))
    elif view != "saveCityBuildingsPositions":
        raise ValueError("Unsupported cookie-only read view")
    if (set(query) != fields or not _id(query.get("currentCityId"))
            or ("cityId" in query and query["currentCityId"] != query["cityId"])
            or query["backgroundView"] != "city"
            or noIndex != (view == "saveCityBuildingsPositions")):
        raise ValueError("Unsupported cookie-only read URL")
    if "position" in fields and not _position(query["position"]):
        raise ValueError("Invalid read building position")
    if view == "researchAdvisor" and (query["oldView"] != "updateGlobalData"
                                      or query["templateView"] != view):
        raise ValueError("Unsupported research advisor view")
    if view == "finances" and query["templateView"] != view:
        raise ValueError("Unsupported finance view")
    if view == "takeOffer" and (
            not _id(query["destinationCityId"]) or query["oldView"] != "branchOffice"
            or query["activeTab"] != "bargain" or query["templateView"] != "branchOffice"
            or not re.fullmatch(r"[0-9]{1,6}", query["type"])
            or query["resource"] not in ("resource", "1", "2", "3", "4")):
        raise ValueError("Unsupported market offer view")
