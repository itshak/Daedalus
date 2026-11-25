"""Typed one-shot drafts shared by the controller and native client."""
from __future__ import annotations

WORKER_TASKS = frozenset({"modifyProduction", "modifyAcademyWorkers", "modifyTempleWorkers"})
CITY_REVIEW_TASKS = WORKER_TASKS | {"donate"}


def validated_worker_draft(task: object, draft: object) -> dict[str, object]:
    if not isinstance(task, str) or task not in WORKER_TASKS or not isinstance(draft, dict):
        raise ValueError("Unknown worker operation")
    production = task == "modifyProduction"
    keys = {"percentage", "project", "overcharge"} if production else {"percentage"}
    if (set(draft) != keys or type(draft.get("percentage")) is not int
            or not 0 <= draft["percentage"] <= 100):
        raise ValueError("Invalid worker draft")
    if production and (draft["project"] not in ("resource", "tradegood")
                       or type(draft["overcharge"]) is not bool
                       or (draft["overcharge"] and draft["percentage"] != 100)):
        raise ValueError("Invalid worker project or overcharge")
    return dict(draft)


def validate_worker_plan(task: str, city_id: int, draft: dict[str, object],
                         plan: object) -> dict[str, object]:
    """Check a bounded engine observation; never synthesize missing values."""
    if (not isinstance(plan, dict) or plan.get("task") != task
            or type(plan.get("city_id")) is not int or plan["city_id"] != city_id
            or plan.get("percentage") != draft["percentage"]
            or plan.get("project") != draft.get("project")
            or plan.get("overcharge") is not draft.get("overcharge", False)
            or plan.get("ready") is not True
            or not isinstance(plan.get("city_name"), str)
            or not 0 < len(plan["city_name"]) <= 100):
        raise ValueError("Invalid worker preview scope")
    for key in ("maximum", "extra", "target"):
        if type(plan.get(key)) is not int or not 0 <= plan[key] <= 2*10**6:
            raise ValueError("Invalid worker count")
    current = plan.get("current")
    if current is not None and (type(current) is not int or not 0 <= current <= 2*10**6):
        raise ValueError("Invalid current worker count")
    if (plan["target"] != plan["maximum"] * draft["percentage"] // 100
            + (plan["extra"] if draft.get("overcharge") else 0)
            or (task != "modifyProduction" and plan["extra"] != 0)):
        raise ValueError("Invalid worker allocation")
    config = plan.get("config")
    if not isinstance(config, dict):
        raise ValueError("Missing worker config")  # noqa: TRY004 - malformed remote data
    expected = config.get("expected")
    if (not isinstance(expected, dict)
            or set(expected) != {"island_id", "position", "maximum", "extra", "current", "target"}
            or type(expected.get("island_id")) is not int
            or not 0 < expected["island_id"] < 10**12
            or (task == "modifyProduction" and expected["position"] is not None)
            or (task != "modifyProduction" and (type(expected["position"]) is not int
                                                or not 0 <= expected["position"] <= 80))
            or any(type(expected[k]) is not type(plan[k]) or expected[k] != plan[k]
                   for k in ("maximum", "extra", "current", "target"))
            or config != {"city_id": city_id, **draft, "expected": expected}):
        raise ValueError("Invalid reviewed worker config")
    return {k: plan[k] for k in ("task", "city_id", "city_name", "percentage",
                                 "project", "overcharge", "maximum", "extra",
                                 "current", "target", "ready", "config")}
