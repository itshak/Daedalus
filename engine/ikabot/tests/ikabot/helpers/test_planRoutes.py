import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.planRoutes import sendGoods, splitCargoBetweenFleets, transport_feedback


class TestSplitCargoBetweenFleets(unittest.TestCase):
    """Test the cargo split between trade ships and freighters"""

    def setUp(self):
        """Set up test fixtures"""
        self.session = Mock()

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_cargo_fits_in_trade_ships(self, mock_freighters, mock_ships, mock_capacity):
        """The whole cargo fits in the available trade ships, freighters get nothing"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 10
        mock_capacity.return_value = (500, 5000)

        toSend = [1000, 1000, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [1000, 1000, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_leftover_goes_to_freighters(self, mock_freighters, mock_ships, mock_capacity):
        """Whatever doesn't fit in the trade ships is assigned to the freighters"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 2
        mock_capacity.return_value = (500, 5000)

        toSend = [1000, 1000, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        # 2 trade ships * 500 capacity = 1000, taken by the first resource
        self.assertEqual(tradeShipCargo, [1000, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 1000, 0, 0, 0])
        self.assertEqual(
            [t + f for t, f in zip(tradeShipCargo, freighterCargo)], toSend
        )

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_partial_split_of_a_single_resource(self, mock_freighters, mock_ships, mock_capacity):
        """A single resource is split between both fleets when it doesn't fit in one"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 1
        mock_capacity.return_value = (500, 5000)

        toSend = [800, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [500, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [300, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_no_freighters_available(self, mock_freighters, mock_ships, mock_capacity):
        """Without freighters the whole cargo is sent with trade ships"""
        mock_freighters.return_value = 0
        mock_ships.return_value = 1
        mock_capacity.return_value = (500, 5000)

        toSend = [10000, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [10000, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [0, 0, 0, 0, 0])

    @patch('ikabot.helpers.planRoutes.getShipCapacity')
    @patch('ikabot.helpers.planRoutes.getAvailableShips')
    @patch('ikabot.helpers.planRoutes.getAvailableFreighters')
    def test_no_trade_ships_available(self, mock_freighters, mock_ships, mock_capacity):
        """Without trade ships the whole cargo is sent with freighters"""
        mock_freighters.return_value = 5
        mock_ships.return_value = 0
        mock_capacity.return_value = (500, 5000)

        toSend = [10000, 0, 0, 0, 0]
        tradeShipCargo, freighterCargo = splitCargoBetweenFleets(self.session, toSend)

        self.assertEqual(tradeShipCargo, [0, 0, 0, 0, 0])
        self.assertEqual(freighterCargo, [10000, 0, 0, 0, 0])


class TestShipmentOutcome(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.get.return_value = "city"
        self.checkpoint = Mock()
        self.checkpoint.reserve.return_value = "chunk"

    def run_shipment(self, checkpoint=None):
        with patch("ikabot.helpers.planRoutes.getCity", return_value={
            "id": "1", "availableResources": [100, 100, 100, 100, 100]
        }):
            sendGoods(self.session, "1", "2", "3", 1, [10, 0, 0, 0, 0],
                      checkpoint=checkpoint, route_index=0)

    def assert_single_cargo(self):
        calls = self.session.post.call_args_list
        cargo = [c for c in calls if c.kwargs["params"]["function"] == "loadTransportersWithFreight"]
        self.assertEqual(len(cargo), 1)
        self.assertIs(cargo[0].kwargs["retry_on_failure"], False)

    def test_stock_changes_before_cargo_never_reserve_or_submit(self):
        original = {"id": "1", "availableResources": [100] * 5}
        depleted = {"id": "1", "availableResources": [0, 100, 100, 100, 100]}
        with patch("ikabot.helpers.planRoutes.getCity", side_effect=[original, original, depleted]):
            with self.assertRaisesRegex(RuntimeError, "source changed"):
                sendGoods(self.session, "1", "2", "3", 1, [10, 0, 0, 0, 0],
                          checkpoint=self.checkpoint, route_index=0)
        self.checkpoint.reserve.assert_not_called()
        self.assertEqual(self.session.post.call_count, 1)
        self.assertEqual(self.session.post.call_args.kwargs["params"]["function"], "changeCurrentCity")

    def test_ambiguous_response_never_replays_and_leaves_checkpoint_unresolved(self):
        self.session.post.side_effect = ["ok", RuntimeError("lost reply")]
        with self.assertRaises(RuntimeError):
            self.run_shipment(self.checkpoint)
        self.assert_single_cargo()
        self.checkpoint.reserve.assert_called_once_with(0, [10, 0, 0, 0, 0])
        self.checkpoint.confirmed.assert_not_called()
        self.checkpoint.rejected.assert_not_called()

    def test_unknown_outcome_stops_even_without_checkpoint(self):
        self.session.post.side_effect = ["ok", '[null,null,null,[null,[{"type":99}]]]']
        with self.assertRaisesRegex(RuntimeError, "manual reconciliation"):
            self.run_shipment()
        self.assert_single_cargo()

    def test_invalid_reply_stops_even_without_checkpoint(self):
        self.session.post.side_effect = ["ok", "not a game response"]
        with self.assertRaisesRegex(RuntimeError, "manual reconciliation"):
            self.run_shipment()
        self.assert_single_cargo()

    def test_reviewed_cookie_sender_does_not_parse_default_view_as_city(self):
        self.session._daedalus_cookies_only = True
        self.session.get.return_value = "currentCityId: 7, not a city view"
        self.session._daedalus_reviewed_transport_post.side_effect = [
            "ok", '[["provideFeedback",[{"type":10}]],["updateGlobalData",{}]]']
        guard = Mock()
        with patch("ikabot.helpers.planRoutes.getAvailableShips", return_value=1), patch("ikabot.helpers.planRoutes.getCity", return_value={
            "id": "1", "availableResources": [100] * 5
        }) as parser:
            sendGoods(self.session, "1", "2", "3", 1, [10, 0, 0, 0, 0], before_send=guard)
        self.assertEqual(parser.call_count, 2)
        calls = self.session._daedalus_reviewed_transport_post.call_args_list
        self.assertEqual(calls[0].args[0]["currentCityId"], "7")
        self.assertEqual(calls[1].args[0]["cargo_resource"], 10)
        guard.assert_called_once()
        self.assertEqual(calls[1].args[0]["normalTransportersMax"], 1)
        self.session.post.assert_not_called()

    def test_named_feedback_is_not_position_dependent(self):
        self.assertEqual(transport_feedback('[["provideFeedback",[{"type":10}]],["updateGlobalData",{}]]'), "accepted")
        self.assertEqual(transport_feedback('[["updateGlobalData",{}],["provideFeedback",[{"type":10}]]]'), "accepted")

    def test_feedback_errors_and_unknown_are_never_success(self):
        for response, expected in [
            ('[["provideFeedback",[{"type":11}]]]', "transport_rejected"),
            ('[["provideFeedback",[{"type":10},{"type":11}]]]', "transport_rejected"),
            ('[["updateGlobalData",{"type":10}]]', "transport_feedback_unconfirmed"),
            ('[["provideFeedback",[{"type":99}]]]', "transport_feedback_unconfirmed"),
            ('<html>private</html>', "invalid_transport_response"),
            ('[["provideFeedback",[{"type":"10"}]]]', "invalid_transport_response"),
        ]:
            self.assertEqual(transport_feedback(response), expected)

    def test_confirmed_shipment_records_exact_cargo(self):
        self.session.post.side_effect = ["ok", '[null,null,null,[null,[{"type":10}]]]']
        self.run_shipment(self.checkpoint)
        self.assert_single_cargo()
        self.checkpoint.confirmed.assert_called_once_with("chunk", [10, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
