"""Structured adapter for the upstream modifyAcademyWorkers menu action."""
from ikabot.helpers.decorators import task
from ikabot.function.modifyProduction import prepare_native_workers, execute_native_workers


def prepare(session, city_id, percentage, expected, additional_city_ids=None):
    return prepare_native_workers(session, "modifyAcademyWorkers", city_id, percentage, expected,
                                  additional_city_ids=additional_city_ids)


@task("modifyAcademyWorkers", prepare=prepare)
def execute(session, city_id: int, percentage: int, expected: dict, additional_city_ids: list = None):
    execute_native_workers(session, "modifyAcademyWorkers", city_id, percentage, expected,
                                  additional_city_ids=additional_city_ids)
