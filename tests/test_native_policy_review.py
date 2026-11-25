"""Account-specific observations and strict policy drafts."""
from unittest.mock import Mock

import pytest

from daedalus.accounts import Account
from daedalus.native_policy_review import (
    observe_policy,
    policy_draft,
    policy_summary,
    validate_policy_observation,
)
from daedalus.reviewed_batch import BATCH_REVIEW_TASKS

ACCOUNT = Account("alpha", "s1-en", "Mine", "Mine", True)
ACADEMY = {"city_id": 101, "city_name": "Athens", "crystal": 300000, "cooldown": False, "can_experiment_now": True}
TAVERN = {"city_id": 101, "city_name": "Athens", "wine": 500, "serving_level": 2, "wine_per_hour": 10, "has_tavern": True, "serving_options": [[0,0],[1,5],[2,10],[3,15]]}
MIRACLE = {"city_id": 101, "temple_city": "Athens", "island_id": "4", "wonder": "1", "wonder_name": "Wonder", "level": 3, "available": False, "available_in_seconds": 60}
SHRINE = {"city_id": 101, "city_name": "Athens", "position": 1, "favor": 200}
UPGRADE = {"unit_id": "301", "name": "Unit", "upgrade_type": "offensive", "description": "Attack", "current_level": 1, "max_level": 4}


@pytest.mark.parametrize(("task","draft","method","data"),[
    ("research", {"cities_ids":["101"],"qty":1}, "academies", {"academies":[ACADEMY]}),
    ("research", {"study_choice":{"index":1,"name":"Study","research_type":"science"}}, "academies", {"studies":[{"index":1,"name":"Study","research_type":"science"}]}),
    ("tavernManager", {"cities_ids":[101],"run_hours":2,"notification_mode":2}, "taverns", {"taverns":[TAVERN]}),
    ("activateMiracle", {"wonder":"1","iterations":2}, "miracles", {"miracles":[MIRACLE]}),
    ("activateShrine", {"godids":[1,2],"mode":1,"times":2}, "shrine_status", {"shrine":SHRINE}),
    ("UpgradeUnits", {"jobs":[{"city_id":101,"upgrades":[{"unitId":"301","upgradeType":"offensive","target":3}]}]}, "workshop_upgrades", {"upgrades":[UPGRADE]}),
])
def test_policy_is_observed_and_batchable(task,draft,method,data):
    ipc=Mock()
    getattr(ipc,method).return_value=data
    clean=policy_draft(task,draft)
    result=observe_policy(ipc,ACCOUNT,task,clean)
    assert validate_policy_observation(task,clean,result)==result
    assert policy_summary(task,clean,result)
    assert task in BATCH_REVIEW_TASKS
    getattr(ipc,method).assert_called_once_with(ACCOUNT,*([101] if task=="UpgradeUnits" else []))
    assert len(ipc.mock_calls)==1


def test_foreign_academy_and_changed_upgrade_rejected():
    ipc=Mock()
    ipc.academies.return_value={"academies":[{**ACADEMY,"city_id":999}]}
    with pytest.raises(ValueError):
        observe_policy(ipc,ACCOUNT,"research",policy_draft("research",{"cities_ids":[101],"qty":1}))
    ipc.workshop_upgrades.return_value={"upgrades":[{**UPGRADE,"current_level":3}]}
    with pytest.raises(ValueError):
        observe_policy(ipc,ACCOUNT,"UpgradeUnits",{"jobs":[{"city_id":101,"upgrades":[{"unitId":"301","upgradeType":"offensive","target":3}]}]})
    with pytest.raises(ValueError):
        policy_draft("activateShrine",{"godids":[1,1],"mode":1,"times":2})


def test_fixed_tavern_revalidated():
    from daedalus.tavern_choices import fixed_tavern_review
    draft={"run_hours":0,"fixed_servings":fixed_tavern_review([TAVERN],100)}
    ipc=Mock()
    ipc.taverns.return_value={"taverns":[TAVERN]}
    assert observe_policy(ipc,ACCOUNT,"tavernManager",draft)=={"fixed_servings":draft["fixed_servings"]}
    ipc.taverns.return_value={"taverns":[{**TAVERN,"serving_level":1,"wine_per_hour":5}]}
    with pytest.raises(ValueError):
        observe_policy(ipc,ACCOUNT,"tavernManager",draft)
