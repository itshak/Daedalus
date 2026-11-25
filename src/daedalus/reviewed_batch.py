"""Independent account review tickets; no shared game identifiers or replay."""
from __future__ import annotations

import re
from uuid import uuid4

from daedalus.native_policy_review import POLICY_TASKS
from daedalus.reviewed_operations import CITY_REVIEW_TASKS

REVIEW_ENDPOINTS = {
    "consolidateResources": "consolidate-start",
    "resourceTransportManager": "transport-policy-start",
    "donationBot": "donation-policy-start",
    "searchForIslandSpaces": "island-monitor-start",
    "dumpWorld": "world-report-start",
    "autoPirate": "piracy-start",
    "research": "research-start",
    "tavernManager": "tavern-start",
    "activateMiracle": "miracle-start",
    "activateShrine": "shrine-start",
    "UpgradeUnits": "workshop-start",
    "distributeResources": "distribution-start",
    "loginDaily": "daily-start",
    "buyResources": "buy-start",
    "sellResources": "sell-start",
    "trainArmy": "training-start",
    "constructionList": "construction-start",
    "sendResources": "shipment-start",
    "donate": "donation-start",
    "modifyProduction": "worker-start",
    "modifyAcademyWorkers": "worker-start",
    "modifyTempleWorkers": "worker-start",
    "reorganizeCityBuildings": "layout-start",
    "constructBuilding": "build-start",
    "stationArmy": "station-start",
    "autoBarbarians": "grind-start",
    "attackBarbarians": "attack-start",
    "vacationMode": "vacation-start",
}
BATCH_REVIEW_TASKS = frozenset(REVIEW_ENDPOINTS)
ADDITIONAL_REVIEW_TASKS = POLICY_TASKS | {"constructionList", "sendResources", "distributeResources", "loginDaily", "buyResources", "sellResources"}
assert BATCH_REVIEW_TASKS == CITY_REVIEW_TASKS | ADDITIONAL_REVIEW_TASKS
MAX_REVIEW_BATCH = 32
PREVIEW_ID_PATTERN = r"[A-Za-z0-9_-]{43}"


def validated_batch_entries(entries: object) -> list[dict[str, str]]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_REVIEW_BATCH:
        raise ValueError("Select 1 to 32 independently reviewed accounts")
    seen_accounts, seen_tickets = set(), set()
    for row in entries:
        if (not isinstance(row, dict) or set(row) != {"account_id", "task", "preview_id"}
                or not isinstance(row["account_id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", row["account_id"])
                or not isinstance(row["task"], str) or row["task"] not in BATCH_REVIEW_TASKS
                or not isinstance(row["preview_id"], str)
                or not re.fullmatch(PREVIEW_ID_PATTERN, row["preview_id"])
                or row["account_id"] in seen_accounts or row["preview_id"] in seen_tickets):
            raise ValueError("Invalid independent account review")
        seen_accounts.add(row["account_id"])
        seen_tickets.add(row["preview_id"])
    return [dict(row) for row in entries]


def dispatch_reviewed_batch(client, entries: object) -> dict[str, object]:
    """Precheck every ticket before starting any job; stop on first uncertainty.

    Each launch remains an independently durable request. No retries are made.
    A failed precheck does not consume any tickets or dispatch anything.
    """
    rows = validated_batch_entries(entries)
    checked = client.reviewed_batch_check(rows)
    blocked = checked["blocked"]
    ids = [r["account_id"] for r in rows]
    submitted = []
    halted = None
    if not blocked:
        for row in rows:
            rid = str(uuid4())
            try:
                receipt = client.start_reviewed_task(row["account_id"], row["task"],
                                                     row["preview_id"], rid)
                if (receipt.get("account_id") != row["account_id"]
                        or receipt.get("task") != row["task"]
                        or receipt.get("request_id") != rid
                        or receipt.get("status") != "started"):
                    raise ValueError("Unconfirmed receipt")
            except Exception:  # noqa: BLE001 - any ambiguous dispatch must halt the remaining batch
                halted = {"account_id": row["account_id"], "request_id": rid, "status": "unconfirmed"}
                break
            submitted.append({"account_id": row["account_id"], "request_id": rid, "status": "started"})
    return {"account_ids": ids, "submitted": submitted, "blocked": blocked, "halted": halted}


def validate_batch_check(result: object, entries: list[dict[str, str]]) -> dict[str, object]:
    ids = [r["account_id"] for r in entries]
    if (not isinstance(result, dict) or result.get("account_ids") != ids
            or not isinstance(result.get("blocked"), list)):
        raise ValueError("Invalid batch precheck")
    seen = set()
    for row in result["blocked"]:
        if (not isinstance(row, dict) or set(row) != {"account_id", "reason"}
                or row["account_id"] not in ids or row["account_id"] in seen
                or row["reason"] not in {"review_unavailable", "prerequisites", "unavailable"}):
            raise ValueError("Invalid batch precheck")
        seen.add(row["account_id"])
    return {"account_ids": ids, "blocked": result["blocked"]}
