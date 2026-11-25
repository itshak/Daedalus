"""Structured adapter for the upstream modifyTempleWorkers menu action."""
from ikabot.helpers.decorators import task
from ikabot.function.modifyProduction import prepare_native_workers, execute_native_workers


def prepare(session, city_id, percentage, expected):
    return prepare_native_workers(session, "modifyTempleWorkers", city_id, percentage, expected)


@task("modifyTempleWorkers", prepare=prepare)
def execute(session, city_id: int, percentage: int, expected: dict):
    execute_native_workers(session, "modifyTempleWorkers", city_id, percentage, expected)
