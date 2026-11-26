"""CLI and reviewed adapters share exact upstream mutation forms, offline."""
from unittest.mock import Mock

from ikabot.config import actionRequest
from ikabot.function import buyResources, constructBuilding, reorganizeCityBuildings, stationArmy


def test_build_cli_and_reviewed_share_original_payload():
    s = Mock()
    constructBuilding._submit_building(s, "42", 4, "7", actionRequest)
    constructBuilding._submit_building(s, "42", 4, "7", actionRequest, reviewed=True)
    expected = {"action": "BuildNewBuilding", "cityId": "42", "position": 4,
                "building": "7", "backgroundView": "city", "currentCityId": "42",
                "templateView": "buildingGround", "actionRequest": actionRequest, "ajax": "1"}
    assert s.post.call_args_list[0].kwargs == {"params": expected, "noIndex": True}
    assert s.post.call_args_list[1].kwargs == {
        "params": expected, "noIndex": True, "retry_on_failure": False}


def test_layout_cli_and_reviewed_share_original_payload():
    s = Mock()
    moves = [(4, 7), (8, 9)]
    reorganizeCityBuildings._submit_layout(s, "42", moves)
    reorganizeCityBuildings._submit_layout(s, "42", moves, reviewed=True)
    expected = {"action": "SaveBuildingPositions", "backgroundView": "city",
                "currentCityId": "42", "templateView": "saveCityBuildingsPositions",
                "actionRequest": actionRequest, "ajax": "1", "cityId": "42",
                "moves[0][from]": 4, "moves[0][to]": 7,
                "moves[1][from]": 8, "moves[1][to]": 9}
    assert s.post.call_args_list[0].kwargs == {"params": expected, "noIndex": True}
    assert s.post.call_args_list[1].kwargs == {
        "params": expected, "noIndex": True, "retry_on_failure": False}


def test_original_station_sender_accepts_reviewed_cargo_without_duplicate_builder():
    for ground in (True, False):
        s = Mock()
        mode = "army" if ground else "fleet"
        cargo = {f"cargo_{mode}_301": "5", f"cargo_{mode}_301_upkeep": "3"}
        args = (s, {"id": "42"}, {"id": "43", "islandId": "3"}, ground, cargo)
        stationArmy.sendArmy(*args)
        stationArmy.sendArmy(*args, reviewed=True)
        expected = {"action": "transportOperations", "function": "deployArmy" if ground else "deployFleet",
                    "actionRequest": actionRequest, "islandId": "3", "destinationCityId": "43",
                    "deploymentType": mode, "backgroundView": "city", "currentCityId": "42",
                    "templateView": "deployment", "ajax": 1, **cargo}
        assert s.post.call_args_list[0].kwargs == {"params": expected}
        assert s.post.call_args_list[1].kwargs == {"params": expected, "retry_on_failure": False}


def test_market_selection_preserves_original_cli_form():
    s = Mock()
    buyResources.select_market_resource(s, {"id": "42", "pos": 4, "rango": 3}, 0)
    s.post.assert_called_once_with(params={
        "cityId": "42", "position": 4, "view": "branchOffice", "activeTab": "bargain",
        "type": 444, "searchResource": "resource", "range": 3, "backgroundView": "city",
        "currentCityId": "42", "templateView": "branchOffice", "currentTab": "bargain",
        "actionRequest": actionRequest, "ajax": 1})


def test_preserved_upstream_source_guards():
    import ast
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    guard = json.loads((root / "tests/fixtures/upstream_preserved_functions.json").read_text())
    for file, functions in guard["functions"].items():
        source = (root / "engine/ikabot/ikabot" / file).read_text()
        definitions = {node.name: node for node in ast.parse(source).body
                       if isinstance(node, ast.FunctionDef)}
        for name, expected in functions.items():
            actual = hashlib.sha256(ast.get_source_segment(source, definitions[name]).encode()).hexdigest()
            assert actual == expected, f"Unexpected upstream change: {file}::{name}"
