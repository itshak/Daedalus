"""Offline source-based barracks and shipyard training contracts."""

import importlib
import unittest
from unittest.mock import Mock, patch

training = importlib.import_module("ikabot.function.trainArmy")


class TestNativeTrainArmy(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.get.return_value = "synthetic-city-html"
        self.city = {
            "id": "42", "name": "Athens",
            "position": [
                {"position": 3, "building": "barracks"},
                {"position": 5, "building": "shipyard"},
            ],
            "availableResources": [3000, 0, 1000, 0, 2000],
            "freeCitizens": 50,
        }
        self.units = [
            {"unit_type_id": 301, "local_name": "Swordsman",
             "identifier": "swordsman",
             "costs": {"wood": 100, "sulfur": 50, "citizens": 1, "upkeep": 3}},
            {"unit_type_id": 302, "local_name": "Hoplite",
             "identifier": "phalanx",
             "costs": {"wood": 200, "sulfur": 70, "citizens": 1}},
        ]

    def _patch_sources(self):
        from ikabot.helpers import taskConfig
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(
            patch.object(taskConfig, "requireOwnCity", return_value="42")
        )
        stack.enter_context(patch.object(training, "getCity", return_value=self.city))
        stack.enter_context(patch.object(training, "getBuildingInfo", return_value=[
            ["synthetic"], ["synthetic"], ["unit catalog"]]))
        stack.enter_context(patch.object(training, "generateArmyData", return_value=self.units))
        return stack

    def test_readonly_options_use_real_unit_costs_and_owned_training_building(self):
        with self._patch_sources():
            result = training.available_trainable_units(self.session, "42", True)
        self.assertEqual(result["city"], {
            "id": "42", "cityName": "Athens", "pos": "3",
        })
        self.assertEqual(len(result["units"]), 2)
        self.assertEqual(result["units"][0]["costs"]["wood"], 100)
        self.session.post.assert_not_called()

    def test_prepare_recomputes_source_costs_and_avoids_untrusted_json_metadata(self):
        with self._patch_sources():
            plan = training.prepare_trainArmy(
                self.session,
                {"id": "42", "pos": "3", "cityName": "Athens"},
                [[{"unit_type_id": 301, "cantidad": 4}]],
                True, "n", 0, [], [],
            )
        self.assertEqual(plan["tranings"][0][0]["costs"]["wood"], 100)
        self.assertEqual(plan["tranings"][0][0]["cantidad"], 4)
        self.assertEqual(plan["replicate"], "n")
        self.assertEqual(plan["cityTrainings"], [])
        self.session.post.assert_not_called()

    def test_prepare_rejects_insufficient_resources_or_unknown_unit(self):
        for units in (
            [{"unit_type_id": 301, "cantidad": 100}],
            [{"unit_type_id": 999, "cantidad": 1}],
            [{"unit_type_id": 301, "cantidad": 1, "costs": {"wood": 0}}],
        ):
            with self.subTest(units=units), self._patch_sources():
                with self.assertRaises(ValueError):
                    training.prepare_trainArmy(
                        self.session,
                        {"id": "42", "pos": "3", "cityName": "Athens"},
                        [units], True, "n", 0, [], [],
                    )

    def test_prepare_blocks_unreviewed_replication_and_wrong_training_city(self):
        with self._patch_sources():
            with self.assertRaises(ValueError):
                training.prepare_trainArmy(
                    self.session,
                    {"id": "42", "pos": "3", "cityName": "Athens"},
                    [[{"unit_type_id": 301, "cantidad": 1}]],
                    True, "y", 1, ["42"], [],
                )
            with self.assertRaisesRegex(ValueError, "changed"):
                training.prepare_trainArmy(
                    self.session,
                    {"id": "42", "pos": "8", "cityName": "Athens"},
                    [[{"unit_type_id": 301, "cantidad": 1}]],
                    True, "n", 0, [], [],
                )
