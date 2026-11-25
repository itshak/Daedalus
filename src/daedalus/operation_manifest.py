"""Reviewed platform coverage, not a claim of full upstream or live acceptance.

The upstream AST inventory is separate: new names must be assigned a policy
here rather than silently becoming executable. The HTTP capability response
includes this versioned information for both clients.
"""
from __future__ import annotations

from daedalus.reviewed_operations import CITY_REVIEW_TASKS

MANIFEST_VERSION = 1

_BACKGROUND_NATIVE = frozenset({
    "activateMiracle", "activateShrine", "alertAttacks", "alertLowWine",
    "autoPirate", "buyResources", "consolidateResources", "constructionList",
    "distributeResources", "donationBot", "dumpWorld", "loginDaily", "research",
    "resourceTransportManager", "searchForIslandSpaces", "sellResources",
    "sendResources", "tavernManager", "trainArmy", "UpgradeUnits",
})
_NATIVE = _BACKGROUND_NATIVE | CITY_REVIEW_TASKS
_READ_VIEWS = {
    "viewArmy": "military",
    "shipMovements": "military",
    "getStatus": "overview",
    "killTasks": "activity",
}
_LOCAL_BOUNDARIES = frozenset({
    "importExportCookie", "developer", "loadCustomModule", "update",
    "checkForUpdate", "webServer", "proxyConf", "decaptchaConf",
    "updateTelegramData", "updateDiscordData", "testTelegramBot", "testDiscordBot",
    "show_proxy",
})
_PENDING = frozenset({
    "vacationMode",
})
AUXILIARY_OPERATIONS = frozenset({"checkForUpdate", "show_proxy"})
ALL_REVIEWED_NAMES = _NATIVE | set(_READ_VIEWS) | _LOCAL_BOUNDARIES | _PENDING | {"logs"}


def operation_workflow(name: str) -> dict[str, object]:
    """Return explicitly reviewed coverage and execution policy for one name."""
    if name in _NATIVE:
        review = ("ticket" if name in CITY_REVIEW_TASKS else
                  "engine_preview_web_ticket" if name == "constructionList" else "native_draft")
        return {
            "desktop": "native", "web": "native", "review": review,
            "coverage": "partial", "scopes": (
                ["current", "selected", "all"] if name in {"alertAttacks", "alertLowWine"}
                else ["current"]
            ),
            "live_accepted": False,
        }
    if name in _READ_VIEWS:
        return {"desktop": "existing_view", "web": "existing_view",
                "view": _READ_VIEWS[name], "review": "read_or_managed_task",
                "coverage": "partial", "scopes": ["current", "selected", "all"],
                "live_accepted": False}
    if name == "logs":
        return {"desktop": "existing_view", "web": "pending", "view": "activity",
                "review": "read_only", "coverage": "partial", "scopes": ["current"],
                "live_accepted": False}
    if name in _LOCAL_BOUNDARIES:
        # Only import/session recovery already has a protected local workflow.
        # Do not claim other privileged admin implementations or approval.
        return {"desktop": "protected_local" if name == "importExportCookie" else "pending",
                "web": "protected_local", "review": "admin_review",
                "coverage": "boundary_pending", "scopes": [], "live_accepted": False}
    return {"desktop": "pending", "web": "pending", "review": "unavailable",
            "coverage": "pending", "scopes": [], "live_accepted": False}


def coverage_manifest() -> dict[str, object]:
    return {"version": MANIFEST_VERSION, "operations": {
        name: operation_workflow(name) for name in sorted(ALL_REVIEWED_NAMES, key=str.casefold)
    }}
