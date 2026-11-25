"""Native quote allocation and worker-side rechecks."""
import json
from unittest.mock import Mock

import pytest
from ikabot.function import buyResources, nativeMarket

from daedalus.market_review import allocation, market_draft, validate_market_observation

CITY={"id":"42","name":"Athens","cityName":"Athens","pos":4,"rango":3,"availableResources":[5000,1000,500,0,0]}
BUY={"ciudadDestino":"Market","jugadorAComprar":"Seller","amountAvailable":1000,"tipo":"wood",
     "precio":7,"destinationCityId":"777","cityId":"42","position":"4","type":"444","resource":"resource"}


def test_buy_allocation_total_and_observed_gold(monkeypatch):
    draft={"city":CITY,"offers":[BUY],"amount_to_buy":500}
    monkeypatch.setattr(nativeMarket,"market_snapshot",lambda *_:{"city":CITY,"offers":[BUY]})
    monkeypatch.setattr("ikabot.helpers.market.getGold",lambda *_:(10000,0))
    assert market_draft("buyResources",draft)==draft
    observation=nativeMarket.preview_native_market(Mock(),"buyResources",draft)
    assert observation["gold_total"]==3500
    assert observation["gold_available"]==10000
    assert validate_market_observation("buyResources",draft,observation)==observation
    with pytest.raises(ValueError):
        validate_market_observation("buyResources",draft,{**observation,"gold_total":1})
    with pytest.raises(ValueError):
        market_draft("buyResources",{**draft,"reviewed_market":True})
    with pytest.raises(ValueError):
        market_draft("buyResources",{**draft,"offers":[{**BUY,"cityId":"999"}]})
    monkeypatch.setattr("ikabot.helpers.market.getGold",lambda *_:(100,0))
    with pytest.raises(ValueError,match="gold unavailable"):
        nativeMarket.preview_native_market(Mock(),"buyResources",draft)


def test_buy_rejects_changed_final_price_before_transport_post(monkeypatch):
    monkeypatch.setattr(buyResources, "sendToBotDebug", Mock())
    session=Mock()
    session.post.return_value=json.dumps([[],[None,[None,'<input name="resourcePrice" value="9">']]])
    with pytest.raises(ValueError,match="quote changed"):
        buyResources.buy(session,CITY,BUY,100,1,100,reviewed=True)
    assert session.post.call_count==1
    session.post.reset_mock()
    session.post.side_effect=[json.dumps([[],[None,[None,'<input name="resourcePrice" value="7">']]]),"accepted"]
    buyResources.buy(session,CITY,BUY,100,1,100,reviewed=True)
    assert session.post.call_count==2
    assert session.post.call_args.kwargs["retry_on_failure"] is False


def test_listing_never_overwrites_existing_offers(monkeypatch):
    draft={"mode":"create_offer","city":CITY,"resource_type":0,"price":10,
           "amount_to_sell":200,"sell_market_capacity":1000}
    monkeypatch.setattr(nativeMarket,"market_snapshot",lambda *_:{"city":CITY,"price_min":3,"price_max":20,
        "sell_market_capacity":1000,"currently_on_sale":0})
    monkeypatch.setattr("ikabot.function.sellResources.getMarketInfo",lambda *_:"synthetic")
    monkeypatch.setattr("ikabot.helpers.market.onSellInMarket",lambda *_:[0,1,0,0,0])
    with pytest.raises(ValueError,match="empty market"):
        nativeMarket.preview_native_market(Mock(),"sellResources",draft)
    monkeypatch.setattr("ikabot.helpers.market.onSellInMarket",lambda *_:[0]*5)
    assert nativeMarket.preview_native_market(Mock(),"sellResources",draft)["gold_total"]==2000
    assert allocation("sellResources",draft)[1]==2000
