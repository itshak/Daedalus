import unittest
import json
import importlib
from unittest.mock import Mock, patch

from ikabot.function.constructionList import (
    _getFreeSpeedupParams,
    tryFreeBuildingSpeedup,
)

construction = importlib.import_module("ikabot.function.constructionList")


class TestFreeBuildingSpeedup(unittest.TestCase):
    def _response(self, cost):
        popup = '''<a class="button" id="js_buildingSpeedupActivateBtn"
            href="?action=Premium&amp;function=buildingSpeedup&amp;cityId=14075&amp;position=10&amp;level=3&amp;backgroundView=city&amp;currentCityId=14075&amp;actionRequest=old">
            Activate (<span title="Ambrosia" class="ambrosiaIcon">{}</span>)</a>'''.format(cost)
        return json.dumps([["replaceElement", ["#buildingSpeedup", popup]]])

    def test_rejects_nonzero_ambrosia_cost(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(4), "14075", 10))

    def test_rejects_various_nonzero_ambrosia_costs(self):
        for cost in (1, 4, 20, 100, 1500):
            with self.subTest(cost=cost):
                self.assertIsNone(
                    _getFreeSpeedupParams(self._response(cost), "14075", 10)
                )

    def test_rejects_nonzero_cost_with_surrounding_whitespace(self):
        response = self._response_with_span(
            '<span title="Ambrosia" class="ambrosiaIcon">\n  20\n</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_nonzero_cost_with_reordered_span_attributes(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon" title="Ambrosia">20</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_nonzero_cost_in_raw_popup(self):
        popup = json.loads(self._response(20))[0][1][1]

        self.assertIsNone(_getFreeSpeedupParams(popup, "14075", 10))

    def test_rejects_nonzero_cost_with_non_numeric_text(self):
        response = self._response_with_span(
            '<span title="Ambrosia" class="ambrosiaIcon">20 Ambrosia</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_zero_outer_span_hiding_nonzero_inner_cost(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">0<span class="ambrosiaIcon">20</span></span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_duplicate_spans_with_mixed_zero_and_nonzero_costs(self):
        for spans in (
            '<span class="ambrosiaIcon">0</span> <span class="ambrosiaIcon">20</span>',
            '<span class="ambrosiaIcon">20</span> <span class="ambrosiaIcon">0</span>',
        ):
            with self.subTest(spans=spans):
                response = self._response_with_span(spans)

                self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_builds_guarded_zero_cost_request(self):
        params = _getFreeSpeedupParams(self._response(0), "14075", 10)

        self.assertEqual(params["action"], "Premium")
        self.assertEqual(params["function"], "buildingSpeedup")
        self.assertEqual(params["level"], "3")

    def test_rejects_zero_cost_request_for_another_position(self):
        self.assertIsNone(_getFreeSpeedupParams(self._response(0), "14075", 11))

    def _response_with_span(self, span):
        response = json.loads(self._response(0))
        response[0][1][1] = response[0][1][1].replace(
            '<span title="Ambrosia" class="ambrosiaIcon">0</span>', span
        )
        return json.dumps(response)

    def test_rejects_nested_ambrosia_spans_hiding_nonzero_cost(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">20<span class="ambrosiaIcon">0</span></span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_rejects_duplicate_ambrosia_spans_in_one_button(self):
        response = self._response_with_span(
            '<span class="ambrosiaIcon">0</span> <span class="ambrosiaIcon">0</span>'
        )

        self.assertIsNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_accepts_raw_popup_with_reordered_span_attributes(self):
        response = self._response(0)
        popup = json.loads(response)[0][1][1].replace(
            'title="Ambrosia" class="ambrosiaIcon"',
            'class="ambrosiaIcon" title="Ambrosia"',
        )

        self.assertIsNotNone(_getFreeSpeedupParams(popup, "14075", 10))

    def test_ignores_earlier_button_reference_in_ajax_response(self):
        response = json.loads(self._response(0))
        response.insert(0, ["update", ["#js_buildingSpeedupActivateBtn"]])

        self.assertIsNotNone(
            _getFreeSpeedupParams(json.dumps(response), "14075", 10)
        )

    def test_allows_popup_to_omit_replaceable_request_metadata(self):
        response = self._response(0).replace(
            "&amp;backgroundView=city&amp;currentCityId=14075&amp;actionRequest=old",
            "",
        )

        self.assertIsNotNone(_getFreeSpeedupParams(response, "14075", 10))

    def test_never_posts_premium_request_for_nonzero_cost(self):
        session = Mock()
        session.post.return_value = self._response(4)

        self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 1)

    def test_never_posts_premium_request_for_any_nonzero_cost(self):
        for cost in (1, 20, 1500):
            with self.subTest(cost=cost):
                session = Mock()
                session.post.return_value = self._response(cost)

                self.assertFalse(
                    tryFreeBuildingSpeedup(session, "14075", {"position": 10})
                )
                self.assertEqual(session.post.call_count, 1)

    def test_never_posts_premium_request_for_nested_nonzero_cost(self):
        session = Mock()
        session.post.return_value = self._response_with_span(
            '<span class="ambrosiaIcon">20<span class="ambrosiaIcon">0</span></span>'
        )

        self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 1)

    def test_posts_premium_request_for_zero_cost(self):
        session = Mock()
        session.post.side_effect = [self._response(0), self._response(0), "ok"]

        with patch.object(construction, "wait"):
            self.assertTrue(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))
        self.assertEqual(session.post.call_count, 3)
        requests = [request.kwargs["params"] for request in session.post.call_args_list]
        self.assertEqual(requests[0]["view"], "buildingSpeedup")
        self.assertEqual(requests[1]["view"], "buildingSpeedup")
        self.assertEqual(requests[2]["action"], "Premium")

    def test_rechecks_cost_after_random_wait(self):
        session = Mock()
        current_cost = [0]
        session.post.side_effect = lambda **_: self._response(current_cost[0])

        def change_cost_during_wait(*_):
            self.assertEqual(session.post.call_count, 1)
            current_cost[0] = 20

        with patch.object(construction, "wait", side_effect=change_cost_during_wait) as mocked_wait:
            self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))

        mocked_wait.assert_called_once()
        self.assertEqual(session.post.call_count, 2)
        for request in session.post.call_args_list:
            self.assertEqual(request.kwargs["params"].get("view"), "buildingSpeedup")

    def test_rejects_invalid_popup_after_random_wait(self):
        for response in (
            "invalid response",
            self._response_with_span(""),
            self._response(0).replace("cityId=14075", "cityId=99999"),
            self._response(0).replace("position=10", "position=11"),
        ):
            with self.subTest(response=response):
                session = Mock()
                session.post.side_effect = [self._response(0), response]

                with patch.object(construction, "wait"):
                    self.assertFalse(tryFreeBuildingSpeedup(session, "14075", {"position": 10}))

                self.assertEqual(session.post.call_count, 2)
                for request in session.post.call_args_list:
                    self.assertEqual(request.kwargs["params"].get("view"), "buildingSpeedup")


class TestConstructionSpeedupOptIn(unittest.TestCase):
    def test_wait_and_total_follow_real_duration_and_speedup_opt_in(self):
        for enabled, remaining, speedup_result, expected_calls, expected_wait, total in (
            (False, 600, True, 0, 610, "20M"),
            (False, 300, True, 0, 310, "15M"),
            (False, 200, True, 0, 210, "13M 20S"),
            (True, 600, True, 0, 300, "20M"),
            (True, 301, True, 0, 5, "15M 1S"),
            (True, 300, True, 1, 5, "15M"),
            (True, 200, True, 1, 5, "13M 20S"),
            (True, 200, False, 1, 5, "13M 20S"),
            (True, 0, True, 0, 5, "10M"),
        ):
            with self.subTest(enabled=enabled, remaining=remaining, speedup_result=speedup_result):
                session = Mock()
                building = {"name": "Town hall", "level": 2, "completed": 1000 + remaining}
                active = {"cityName": "Athens", "position": [building]}
                finished = {"cityName": "Athens", "position": []}
                with (
                    patch.object(construction, "CONSTRUCTION_FREE_SPEEDUP", enabled),
                    patch.object(construction.time, "time", return_value=1000),
                    patch.object(construction, "getCity", side_effect=[active, finished, finished]),
                    patch.object(construction, "tryFreeBuildingSpeedup", return_value=speedup_result) as speedup,
                    patch.object(construction, "sendToBotDebug"),
                    patch.object(construction, "wait") as wait,
                ):
                    result = construction.waitForConstruction(session, "14075", 3, [600])

                self.assertIs(result, finished)
                self.assertEqual(speedup.call_count, expected_calls)
                wait.assert_called_once_with(expected_wait)
                self.assertTrue(session.setStatus.call_args_list[0].args[0].endswith(
                    " , total " + total
                ))
                if not enabled:
                    self.assertFalse(any(
                        "speedup" in call.args[0]
                        for call in session.setStatus.call_args_list
                    ))


class TestNativeConstructionPreview(unittest.TestCase):
    """No Gameforge traffic; upstream cost calculator is a deterministic stub."""

    def setUp(self):
        self.session = Mock()
        self.session.get.return_value = "<synthetic city>"
        self.city = {
            "id": "42", "name": "Athens", "endUpgradeTime": 0,
            "availableResources": [3000, 1000, 500, 0, 0],
            "position": [
                {"position": 1, "name": "Town Hall", "building": "townHall",
                 "level": 5, "isBusy": False, "isMaxLevel": False},
                {"position": 2, "name": "Academy", "building": "academy",
                 "level": 3, "isBusy": False, "isMaxLevel": False},
            ],
        }

    @staticmethod
    def fake_costs(_session, _city, building, current, target, _reducers,
                   *, noninteractive=False):
        assert noninteractive
        assert target > current
        building["constructionTimes"] = [120] * (target - current)
        building["constructionTime"] = 120 * (target - current)
        return [1000 * (target - current), 0, 200, 0, 0]

    def _preview(self, selected=None):
        from ikabot.helpers import taskConfig

        selected = selected or [{"position": 1, "target_level": 6}]
        with (patch.object(taskConfig, "requireOwnCity", return_value="42"),
              patch.object(construction, "getCity", return_value=self.city),
              patch.object(construction, "getCostsReducers", return_value=[0] * 5),
              patch.object(construction, "getResourcesNeeded",
                           side_effect=self.fake_costs)):
            return construction.preview_native_construction(self.session, 42, selected)

    def test_preview_builds_real_calculated_queue_without_game_writes(self):
        preview = self._preview()
        self.assertTrue(preview["ready"])
        self.assertEqual(preview["costs"], [1000, 0, 200, 0, 0])
        self.assertEqual(preview["missing"], [0, 0, 0, 0, 0])
        self.assertEqual(preview["config"]["construction_queue"], [120])
        self.assertEqual(preview["config"]["buildings"][0]["upgradeTo"], 6)
        self.assertEqual(preview["config"]["shipments"], [])
        self.session.post.assert_not_called()

    def test_preview_reports_exact_shortages_without_authorizing_start(self):
        self.city["availableResources"] = [200, 0, 30, 0, 0]
        preview = self._preview()
        self.assertFalse(preview["ready"])
        self.assertEqual(preview["missing"], [800, 0, 170, 0, 0])
        self.session.post.assert_not_called()

    def test_fails_closed_on_duplicate_slots_and_stale_targets(self):
        for selected in (
            [{"position": 1, "target_level": 6},
             {"position": 1, "target_level": 7}],
            [{"position": 1, "target_level": 5}],
            [{"position": 79, "target_level": 7}],
            [{"position": 2, "target_level": 99}],
        ):
            with self.subTest(selected=selected):
                with self.assertRaises(ValueError):
                    self._preview(selected)

    def test_dispatch_revalidates_costs_and_rejects_tampered_queue(self):
        from ikabot.helpers import taskConfig

        with (patch.object(taskConfig, "requireOwnCity", return_value="42"),
              patch.object(construction, "getCity", return_value=self.city),
              patch.object(construction, "getCostsReducers", return_value=[0] * 5),
              patch.object(construction, "getResourcesNeeded",
                           side_effect=self.fake_costs)):
            preview = construction.preview_native_construction(
                self.session, 42, [{"position": 1, "target_level": 6}]
            )
            valid = construction.prepare_constructionList(self.session, **preview["config"])
            self.assertEqual(valid["buildings"], preview["config"]["buildings"])
            invalid = dict(preview["config"])
            invalid["construction_queue"] = [1]
            with self.assertRaisesRegex(ValueError, "stale"):
                construction.prepare_constructionList(self.session, **invalid)
        self.session.post.assert_not_called()
