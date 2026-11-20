"""Synthetic market snapshots and exact-quote dispatch validation."""

import importlib
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

market = importlib.import_module("ikabot.function.nativeMarket")

CITY = {
    "id": "42", "name": "Athens", "cityName": "Athens", "pos": 4, "rango": 3,
    "availableResources": [5000, 1000, 500, 0, 0],
}
BUY = {
    "ciudadDestino": "Trade Hub", "jugadorAComprar": "Seller",
    "amountAvailable": 1000, "tipo": "wood", "precio": 7,
    "destinationCityId": "777", "cityId": "42", "position": "4",
    "type": "444", "resource": "resource",
}
SELL = ("Trade Hub", "Buyer", 700, 9, 5, 777)


class TestLiveMarket(unittest.TestCase):
    def setUp(self):
        self.session = Mock()

    def _market_patches(self):
        ctx = ExitStack()
        self.addCleanup(ctx.close)
        ctx.enter_context(patch(
            "ikabot.helpers.taskConfig.requireOwnCity", return_value="42"
        ))
        ctx.enter_context(patch(
            "ikabot.helpers.market.getCommercialCities",
            return_value=[dict(CITY)],
        ))
        ctx.enter_context(patch(
            "ikabot.function.buyResources.getOffers", return_value=[dict(BUY)],
        ))
        ctx.enter_context(patch(
            "ikabot.function.sellResources.getOffers", return_value=[SELL],
        ))
        ctx.enter_context(patch(
            "ikabot.function.sellResources.getMarketInfo", return_value=(
                "var storageCapacity = 2500;"
                + " ".join("'upper': 25, 'lower': 3" for _ in range(5))
            ),
        ))
        ctx.enter_context(patch(
            "ikabot.helpers.market.onSellInMarket",
            return_value=[100, 0, 0, 0, 0],
        ))
        return ctx

    def test_buy_quotes_are_actual_game_rows_and_sorted(self):
        with self._market_patches():
            snapshot = market.market_snapshot(self.session, 42, 0, "buy")
        self.assertEqual(snapshot["offers"], [BUY])
        self.assertEqual(snapshot["city"]["id"], "42")
        self.assertEqual(snapshot["resource_type"], 0)

    def test_buy_preparation_validates_exact_quote_and_amount(self):
        with self._market_patches():
            good = market.prepare_buyResources(
                self.session, dict(CITY), [dict(BUY)], 500
            )
            self.assertEqual(good["amount_to_buy"], 500)
            bad = dict(BUY, precio=1)
            with self.assertRaisesRegex(ValueError, "stale"):
                market.prepare_buyResources(
                    self.session, dict(CITY), [bad], 500,
                )
            with self.assertRaisesRegex(ValueError, "exceeds"):
                market.prepare_buyResources(
                    self.session, dict(CITY), [dict(BUY)], 1001,
                )

    def test_selling_to_real_buyer_offers_checks_stock_and_price(self):
        with self._market_patches():
            prepared = market.prepare_sellResources(
                self.session, "sell_to_offers", amount_to_sell=500,
                offers=[SELL], resource_type=0, city_to_buy_from=dict(CITY),
            )
            self.assertEqual(prepared["offers"], [list(SELL)])
            with self.assertRaisesRegex(ValueError, "changed"):
                market.prepare_sellResources(
                    self.session, "sell_to_offers", amount_to_sell=500,
                    offers=[(*SELL[:3], 1, *SELL[4:])],
                    resource_type=0, city_to_buy_from=dict(CITY),
                )
            with self.assertRaisesRegex(ValueError, "exceed"):
                market.prepare_sellResources(
                    self.session, "sell_to_offers", amount_to_sell=800,
                    offers=[SELL], resource_type=0, city_to_buy_from=dict(CITY),
                )

    def test_listing_price_requires_live_bounds_and_stock(self):
        with self._market_patches():
            result = market.prepare_sellResources(
                self.session, "create_offer", amount_to_sell=300,
                price=10, resource_type=0, city=dict(CITY),
                sell_market_capacity=2500,
            )
            self.assertEqual(result["price"], 10)
            with self.assertRaisesRegex(ValueError, "permitted"):
                market.prepare_sellResources(
                    self.session, "create_offer", amount_to_sell=300,
                    price=100, resource_type=0, city=dict(CITY),
                )
            with self.assertRaisesRegex(ValueError, "capacity"):
                market.prepare_sellResources(
                    self.session, "create_offer", amount_to_sell=300,
                    price=10, resource_type=0, city=dict(CITY),
                    sell_market_capacity=1,
                )
            with self.assertRaisesRegex(ValueError, "Not enough"):
                market.prepare_sellResources(
                    self.session, "create_offer", amount_to_sell=6000,
                    price=10, resource_type=0, city=dict(CITY),
                )

    def test_unowned_market_and_unlisted_resources_fail_closed(self):
        with self._market_patches():
            with self.assertRaises(ValueError):
                market.market_snapshot(self.session, 42, 5, "buy")
            with self.assertRaises(ValueError):
                market.market_snapshot(self.session, 42, 0, "forged")
            with self.assertRaises(ValueError):
                market.prepare_buyResources(
                    self.session, dict(CITY), [
                        dict(BUY, resource="4", tipo="sulfur")
                    ], 300,
                )
