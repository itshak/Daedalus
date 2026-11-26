"""Read-only market quote views and source-verified IkaBot task configuration.

Only existing authenticated IkaBot sessions may call market_snapshot. Reading
market pages is non-mutating. Task preparation re-reads the market and rejects
quotes whose price/availability changed before dispatch.
"""

from __future__ import annotations

import re
from html import unescape


def _name(value, label):
    if not isinstance(value, str):
        raise ValueError("Invalid " + label)
    cleaned = unescape(re.sub(r"<[^>]+>", "", value)).strip()
    if not cleaned or len(cleaned) > 100:
        raise ValueError("Invalid " + label)
    return cleaned


def _amount(value, label, *, maximum=10**12, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid " + label)
    return value


def _market_city(session, city_id):
    from ikabot.helpers.market import getCommercialCities
    from ikabot.helpers.taskConfig import requireOwnCity

    owned = requireOwnCity(session, city_id, "city_id")
    cities = getCommercialCities(session)
    if not isinstance(cities, list) or len(cities) > 200:
        raise ValueError("Too many market cities")
    city = next((item for item in cities if str(item.get("id")) == str(owned)), None)
    if city is None:
        raise ValueError("This account's city has no active trading post")
    position = city.get("pos")
    trade_range = city.get("rango")
    if (type(position) is not int or not 0 <= position <= 80
            or type(trade_range) is not int or not 0 < trade_range <= 100):
        raise ValueError("Trading post details are unavailable")
    stock = city.get("availableResources")
    if (not isinstance(stock, list) or len(stock) != 5
            or any(type(q) is not int or q < 0 for q in stock)):
        raise ValueError("Market city stock unavailable")
    return city, {
        "id": str(owned), "pos": position, "rango": trade_range,
        "name": _name(city.get("name"), "city name"),
        "cityName": _name(city.get("name"), "city name"),
        "availableResources": list(stock),
    }


def market_snapshot(session, city_id, resource_type, side):
    """Return the actual selected city's public market quotes and allowed prices."""
    from ikabot.function import buyResources, sellResources
    from ikabot.helpers.market import storageCapacityOfMarket

    if (type(resource_type) is not int or not 0 <= resource_type <= 4
            or side not in {"buy", "sell_to_offers", "create_offer"}):
        raise ValueError("Choose a resource and market action")
    city, safe_city = _market_city(session, city_id)
    offers = []
    price_min = None
    price_max = None
    sell_market_capacity = None
    currently_on_sale = None

    if side == "buy":
        buyResources.select_market_resource(session, city, resource_type)
        expected_resource = "resource" if resource_type == 0 else str(resource_type)
        raw = buyResources.getOffers(session, city)
        if not isinstance(raw, list) or len(raw) > 400:
            raise ValueError("Unbounded market offers")
        for offer in raw:
            if offer.get("resource") != expected_resource:
                continue
            amount = _amount(offer.get("amountAvailable"), "quote amount")
            price = _amount(offer.get("precio"), "quote price", maximum=10**9, minimum=1)
            if amount == 0:
                continue
            offers.append({
                "ciudadDestino": _name(offer.get("ciudadDestino"), "seller city"),
                "jugadorAComprar": _name(offer.get("jugadorAComprar"), "seller"),
                "amountAvailable": amount,
                "tipo": _name(offer.get("tipo"), "resource"),
                "precio": price,
                "destinationCityId": str(_amount(
                    int(offer.get("destinationCityId")), "seller city ID",
                    maximum=10**12, minimum=1,
                )),
                "cityId": str(_amount(
                    int(offer.get("cityId")), "market city ID",
                    maximum=10**12, minimum=1,
                )),
                "position": str(_amount(int(offer.get("position")), "market position",
                                        maximum=80)),
                "type": str(_amount(int(offer.get("type")), "market offer type",
                                    maximum=10**6)),
                "resource": expected_resource,
            })
        offers.sort(key=lambda item: item["precio"])

    elif side == "sell_to_offers":
        raw = sellResources.getOffers(session, city, resource_type)
        if not isinstance(raw, list) or len(raw) > 400:
            raise ValueError("Unbounded market offers")
        for entry in raw:
            if not isinstance(entry, (list, tuple)) or len(entry) != 6:
                raise ValueError("Malformed market buyer quote")
            city_name, player, qty, price, distance, destination = entry
            amount = _amount(qty, "buyer quote amount")
            if amount == 0:
                continue
            offers.append([
                _name(city_name, "buyer city"),
                _name(player, "buyer"),
                amount,
                _amount(price, "buyer price", maximum=10**9, minimum=1),
                _amount(distance, "buyer distance", maximum=10**4),
                _amount(destination, "buyer city ID", maximum=10**12, minimum=1),
            ])
        offers.sort(key=lambda row: -row[3])

    else:
        from ikabot.helpers.market import onSellInMarket
        html = sellResources.getMarketInfo(session, city)
        bounds = re.findall(r"\'upper\': (\d+),\s*\'lower\': (\d+)", html)
        if len(bounds) != 5:
            raise ValueError("The market did not return trusted price bounds")
        price_max, price_min = [int(n) for n in bounds[resource_type]]
        _amount(price_min, "minimum price", maximum=10**9, minimum=1)
        _amount(price_max, "maximum price", maximum=10**9, minimum=price_min)
        sell_market_capacity = _amount(
            storageCapacityOfMarket(html), "market storage capacity",
        )
        sale = onSellInMarket(html)
        if not isinstance(sale, list) or len(sale) != 5:
            raise ValueError("Current offers unavailable")
        currently_on_sale = _amount(sale[resource_type], "already offered")

    if len(offers) > 200:
        raise ValueError("Too many marketplace offers to safely review at once")
    return {
        "city": safe_city, "resource_type": resource_type, "side": side,
        "offers": offers, "price_min": price_min, "price_max": price_max,
        "sell_market_capacity": sell_market_capacity,
        "currently_on_sale": currently_on_sale,
    }


def prepare_buyResources(session, city, offers, amount_to_buy, reviewed_market=False):
    """Require game-matched quotes, exact prices and enough units before purchase."""
    if (not isinstance(city, dict) or not isinstance(offers, list)
            or not 0 < len(offers) <= 50):
        raise ValueError("Choose a market city and actual offers")
    qty = _amount(amount_to_buy, "purchase amount", minimum=1)
    resources = {offer.get("resource") for offer in offers if isinstance(offer, dict)}
    if len(resources) != 1:
        raise ValueError("All selected offers must sell the same resource")
    resource = next(iter(resources))
    index = 0 if resource == "resource" else int(resource)
    snapshot = market_snapshot(session, city.get("id"), index, "buy")
    found = []
    for offer in offers:
        if offer not in snapshot["offers"] or offer in found:
            raise ValueError("A purchase quote is stale; refresh the market")
        found.append(offer)
    if qty > sum(offer["amountAvailable"] for offer in found):
        raise ValueError("Requested quantity exceeds the selected available offers")
    if any(city.get(key) != snapshot["city"][key] for key in (
        "id", "pos", "rango", "name", "cityName"
    )):
        raise ValueError("Market city has changed; refresh the quotes")
    return {
        "city": snapshot["city"],
        "offers": sorted(found, key=lambda offer: offer["precio"]),
        "amount_to_buy": qty,
        **({"reviewed_market": True} if reviewed_market is True else {}),
    }


def prepare_sellResources(
    session, mode, amount_to_sell=None, offers=None, resource_type=None,
    city_to_buy_from=None, price=None, sell_market_capacity=None, city=None, reviewed_market=False,
):
    """Read market again and reject outdated buyer offers or listing prices."""
    if mode not in {"sell_to_offers", "create_offer"}:
        raise ValueError("Choose an IkaBot market selling mode")
    amount = _amount(amount_to_sell, "selling amount", minimum=1)
    resource = _amount(resource_type, "selling resource index", maximum=4)
    if mode == "sell_to_offers":
        if not isinstance(city_to_buy_from, dict) or not isinstance(offers, list):
            raise ValueError("Choose a real market city and buyer offers")
        if not 0 < len(offers) <= 50:
            raise ValueError("Choose at least one available buyer quote")
        snapshot = market_snapshot(
            session, city_to_buy_from.get("id"), resource, "sell_to_offers"
        )
        chosen = []
        for offer in offers:
            if (not isinstance(offer, (list, tuple)) or len(offer) != 6
                    or list(offer) not in snapshot["offers"]
                    or list(offer) in chosen):
                raise ValueError("A buyer offer has changed; refresh the market")
            chosen.append(list(offer))
        if amount > min(
            snapshot["city"]["availableResources"][resource],
            sum(row[2] for row in chosen),
        ):
            raise ValueError("The selected buyer offers exceed current game stock")
        return {
            "mode": mode, "amount_to_sell": amount, "offers": chosen,
            "resource_type": resource, "city_to_buy_from": snapshot["city"],
            **({"reviewed_market": True} if reviewed_market is True else {}),
        }

    if not isinstance(city, dict):
        raise ValueError("Choose a city to list market goods")
    snapshot = market_snapshot(session, city.get("id"), resource, "create_offer")
    min_price, max_price = snapshot["price_min"], snapshot["price_max"]
    asking = _amount(price, "listing price", maximum=10**9, minimum=1)
    if not min_price <= asking <= max_price:
        raise ValueError("The market listing price is outside the current permitted range")
    if amount > snapshot["city"]["availableResources"][resource]:
        raise ValueError("Not enough game resources to list that amount")
    if sell_market_capacity is not None and sell_market_capacity != snapshot["sell_market_capacity"]:
        raise ValueError("The market capacity has changed; refresh before listing")
    if reviewed_market is True:
        from ikabot.function.sellResources import getMarketInfo
        from ikabot.helpers.market import onSellInMarket

        if (snapshot["currently_on_sale"] != 0 or amount > snapshot["sell_market_capacity"]
                or any(onSellInMarket(getMarketInfo(session, snapshot["city"])))):
            raise ValueError("Reviewed listing requires empty market and immediate capacity")
    return {
        "mode": mode, "amount_to_sell": amount, "price": asking,
        "resource_type": resource,
        "sell_market_capacity": snapshot["sell_market_capacity"],
        "city": snapshot["city"],
        **({"reviewed_market": True} if reviewed_market is True else {}),
    }

def preview_native_market(session, task, draft):
    from ikabot.helpers.market import getGold

    if task == "buyResources":
        prepared = prepare_buyResources(session, **draft, reviewed_market=True)
        amount = prepared["amount_to_buy"]
        offers = [(r["ciudadDestino"], r["jugadorAComprar"], r["amountAvailable"], r["precio"])
                  for r in prepared["offers"]]
        mode = "buy"
        gold = getGold(session, prepared["city"])[0]
    elif task == "sellResources":
        prepared = prepare_sellResources(session, **draft, reviewed_market=True)
        amount = prepared["amount_to_sell"]
        mode = prepared["mode"]
        gold = None
        offers = ([(prepared["city"]["name"], "", amount, prepared["price"])] if mode == "create_offer"
                  else [tuple(r[:4]) for r in prepared["offers"]])
    else:
        raise ValueError("Unsupported market operation")
    rows = []
    for city, player, available, price in offers:
        qty = min(amount, available)
        if qty:
            rows.append({"city":city,"player":player,"amount":qty,"unit_price":price})
            amount -= qty
    total = sum(r["amount"]*r["unit_price"] for r in rows)
    if amount or not 0 < total <= 2**53-1 or (mode == "buy" and (type(gold) is not int or gold < total)):
        raise ValueError("Market allocation or gold unavailable")
    return {"rows": rows, "gold_total": total, "gold_available": gold, "mode":mode}
