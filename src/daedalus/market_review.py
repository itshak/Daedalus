"""Strict native market intent and allocation review; never execute quotes in the controller."""
import re

MAX_AMOUNT = 10**9
MAX_GOLD = 2**53 - 1


def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 100 and not any(ord(c) < 32 or c in "<>" for c in value)


def _id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[1-9][0-9]{0,11}", value))


def market_draft(task, value):
    if not isinstance(value, dict) or task not in ("buyResources", "sellResources"):
        raise ValueError("Invalid market draft")
    if task == "buyResources":
        keys = {"city", "offers", "amount_to_buy"}
        city_key, amount_key = "city", "amount_to_buy"
    elif value.get("mode") == "sell_to_offers":
        keys = {"mode", "city_to_buy_from", "offers", "amount_to_sell", "resource_type"}
        city_key, amount_key = "city_to_buy_from", "amount_to_sell"
    elif value.get("mode") == "create_offer":
        keys = {"mode", "city", "amount_to_sell", "resource_type", "price", "sell_market_capacity"}
        city_key, amount_key = "city", "amount_to_sell"
    else:
        raise ValueError("Invalid market mode")
    if set(value) != keys or not _integer(value[amount_key], 1, MAX_AMOUNT):
        raise ValueError("Invalid market intent")
    city = value[city_key]
    if (not isinstance(city, dict) or set(city) != {"id", "name", "cityName", "pos", "rango", "availableResources"}
            or not _id(city["id"]) or not _text(city["name"]) or not _text(city["cityName"])
            or not _integer(city["pos"], 0, 80) or not _integer(city["rango"], 1, 100)
            or not isinstance(city["availableResources"], list) or len(city["availableResources"]) != 5
            or any(not _integer(n, 0, 10**15) for n in city["availableResources"])):
        raise ValueError("Invalid market city")
    if task == "sellResources" and not _integer(value["resource_type"], 0, 4):
        raise ValueError("Invalid selling resource")
    if value.get("mode") == "create_offer":
        if not _integer(value["price"], 1, MAX_AMOUNT) or not _integer(value["sell_market_capacity"], 0, 10**12):
            raise ValueError("Invalid market price or capacity")
        return value
    offers = value["offers"]
    if not isinstance(offers, list) or not 1 <= len(offers) <= 50:
        raise ValueError("Select actual market offers")
    for row in offers:
        if task == "buyResources":
            if (not isinstance(row, dict) or set(row) != {"ciudadDestino","jugadorAComprar","amountAvailable",
                        "tipo","precio","destinationCityId","cityId","position","type","resource"}
                    or not all(_text(row[k]) for k in ("ciudadDestino","jugadorAComprar","tipo"))
                    or not _id(row["destinationCityId"]) or row["cityId"] != city["id"]
                    or not isinstance(row["position"], str) or not re.fullmatch(r"[0-9]{1,3}", row["position"])
                    or not isinstance(row["type"], str) or not re.fullmatch(r"[0-9]{1,7}", row["type"])
                    or row["resource"] not in ("resource","1","2","3","4")
                    or not _integer(row["amountAvailable"],1,10**12) or not _integer(row["precio"],1,MAX_AMOUNT)):
                raise ValueError("Invalid purchase quote")
        elif (not isinstance(row, list) or len(row) != 6 or not _text(row[0]) or not _text(row[1])
              or not _integer(row[2],1,10**12) or not _integer(row[3],1,MAX_AMOUNT)
              or not _integer(row[4],0,10**4) or not _integer(row[5],1,10**12)):
            raise ValueError("Invalid sale quote")
    if any(row in offers[:i] for i,row in enumerate(offers)):
        raise ValueError("Duplicate quote")
    if task == "buyResources" and len({r["resource"] for r in offers}) != 1:
        raise ValueError("Choose one market resource")
    return value


def allocation(task, draft):
    if task == "buyResources":
        remaining = draft["amount_to_buy"]
        offers = [(r["ciudadDestino"], r["jugadorAComprar"], r["amountAvailable"], r["precio"])
                  for r in sorted(draft["offers"], key=lambda r: r["precio"])]
    elif draft["mode"] == "create_offer":
        remaining = draft["amount_to_sell"]
        offers = [(draft["city"]["name"], "", remaining, draft["price"])]
    else:
        remaining = draft["amount_to_sell"]
        offers = [tuple(r[:4]) for r in draft["offers"]]
    rows = []
    for city, player, available, price in offers:
        amount = min(remaining, available)
        if amount:
            rows.append({"city":city, "player":player, "amount":amount, "unit_price":price})
            remaining -= amount
    total = sum(r["amount"]*r["unit_price"] for r in rows)
    if remaining or not 0 < total <= MAX_GOLD:
        raise ValueError("Market allocation exceeds observed offers or safe gold range")
    return rows, total


def validate_market_observation(task, draft, observation):
    rows, total = allocation(task, draft)
    mode = "buy" if task == "buyResources" else draft["mode"]
    if (not isinstance(observation, dict) or set(observation) != {"rows","gold_total","gold_available","mode"}
            or observation["rows"] != rows or observation["gold_total"] != total
            or observation["mode"] != mode or type(observation["gold_total"]) is not int
            or (mode == "buy" and not _integer(observation["gold_available"], total, MAX_GOLD))
            or (mode != "buy" and observation["gold_available"] is not None)):
        raise ValueError("Invalid market observation")
    return observation
